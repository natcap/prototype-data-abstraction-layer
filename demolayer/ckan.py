import logging

import commondatamodel
import pygeoprocessing
import requests
import yaml
from ckanapi import RemoteCKAN  # mamba install ckanapi
from osgeo import osr

LOGGER = logging.getLogger(__name__)
CKAN_API_URL = 'https://data.naturalcapitalproject.stanford.edu'
WGS84_SRS = osr.SpatialReference()
WGS84_SRS.ImportFromEPSG(4326)
WGS84_WKT = WGS84_SRS.ExportToWkt()

CATALOG_DATA = {
    'HOMEPAGE': CKAN_API_URL,
    'API_KEY_REQUIRED': False,
}


# Objective: try out working with the CKAN API on our site to get a raster
# layer and also a vector layer of watersheds that has been filtered to a
# subset.
#    --> on-the-fly clipping of both seems important.
#    --> for vectors, let's try a FlatGeoBuf of hydrobasins vector (highest
#        level, level 12.  Alternatively, use the shorelines FGB because it has
#        lots of features (just shy of a million linestrings)
#
# 1: use existing search to get datasets for a specific type (e.g. DEM).
# 2: Extend results to allow a dataset to be subsetted.
#   --> Local caching?
#   --> VRTs?
#   --> What about vectors?
#
# Additional things to consider later on:
#   * how to integrate datatypes recorded in the InVEST model spec
#   * delayed loading and/or how to handle datasets that will need to be
#     fetched from a remote source.
#   * how to handle authentication across multiple sources (or maybe GDAL does
#     this implicitly?)


# map InVEST abstract type to the search query that matches
INVEST_TYPES = {
    'DEM': 'tags:DEM',
    'K_FACTOR': 'tags:SOIL+ERODIBILITY',
    'LULC': 'tags:LULC',
    # 'PRECIP': '',  # We don't yet have precip on the data hub
}
# Sanity check: make sure the INVEST types above match the enum in the common
# data model.
assert set(INVEST_TYPES.keys()) == set(commondatamodel.INVEST_TYPES)
ROWS_PER_SEARCH = 10


def _warp_bbox_to_wgs84(gmm_spatial_dict):
    if gmm_spatial_dict['crs'] == 'EPSG:4326':
        bbox = gmm_spatial_dict['bounding_box']
        return [bbox[attr] for attr in ('xmin', 'ymin', 'xmax', 'ymax')]
    else:
        source_srs = osr.SpatialReference()
        source_srs.SetFromUserInput(gmm_spatial_dict['crs'])
        projection_wkt = source_srs.ExportToWkt()
        source_bbox = gmm_spatial_dict['bounding_box']
        return pygeoprocessing.transform_bounding_box(
            source_bbox, projection_wkt, WGS84_WKT)


class InVESTDataset(object):
    def __init__(self, ckan_object, spatial_filter=None):
        self._ckan_data = ckan_object

        # Assume spatial filter is in the form (xmin, ymin, xmax, ymax)
        self.spatial_filter = spatial_filter

        # locate and load the geometamaker yaml file
        gmm_data = None
        for resource in self._ckan_data['resources']:
            if resource['description'] == 'Geometamaker YML':
                yml_text = requests.get(resource['url']).text
                gmm_data = yaml.load(yml_text, Loader=yaml.CLoader)
                assert isinstance(gmm_data, dict)

        self._gmm_data = gmm_data


def search(invest_type, bbox=None):
    """Search CKAN for the dataset of the target InVEST type.

    Args:
        invest_type (str): The InVEST datatype to search for.
            Case-insensitive.
        bbox (tuple, list): The bounding box to use, as a 4-tuple of (minx,
            miny, maxx, maxy).  If ``None``, spatial search will not be used.

    Returns:
        ``None``

    Yields:
        TODO
    """
    LOGGER.info(
        f"Searching CKAN with invest_type:{invest_type}; bbox:{bbox}")
    with RemoteCKAN(CKAN_API_URL) as catalog:
        offset = 0
        count = None
        while True:
            query_string = INVEST_TYPES[invest_type.upper()]

            extras = {}
            if bbox:
                extras['ext_bbox'] = ','.join((str(coord) for coord in bbox))

            result = catalog.action.package_search(
                fq=query_string,
                start=offset,
                extras=extras,
            )
            if not count:
                count = result['count']
            for dataset in result['results']:
                # Skip collections for now
                if dataset['type'] != 'dataset':
                    offset += 1
                    continue

                gmm_data = None
                for resource in dataset['resources']:
                    if resource['description'] == 'Geometamaker YML':
                        yml_text = requests.get(resource['url']).text
                        gmm_data = yaml.load(yml_text, Loader=yaml.CLoader)
                        assert isinstance(gmm_data, dict)
                    elif resource['url'].endswith('.tif'):
                        layer_url = resource['url']
                    elif layer_url.endswith('.zip'):
                        layer_url = f"zip+{resource['url']}"

                if gmm_data:
                    try:
                        wgs84_bbox = _warp_bbox_to_wgs84(gmm_data['spatial'])
                    except KeyError:
                        offset += 1
                        continue

                yield commondatamodel.RasterLayer(
                    source_catalog_dataset_url=(
                        f'{CKAN_API_URL}/dataset/{dataset["name"]}'),
                    layer_url=layer_url,
                    source_rest_data=dataset,
                    name=dataset['title'],
                    invest_type=invest_type,
                    license={
                        'id': dataset.get('license_id'),
                        'title': dataset.get('license_title'),
                        'url': dataset.get('license_url'),
                    },
                    description=dataset['notes'],
                    wgs84_extent=wgs84_bbox,
                )
                offset += 1

            if offset >= count:
                break


if __name__ == '__main__':
    #with RemoteCKAN(CKAN_API_URL) as catalog:
    #    results = catalog.action.package_search(rows=ROWS_PER_SEARCH,
    #                                            q=INVEST_TYPES['DEM'])
    for dataset in search('dem'):
        print(dataset.name)



# OK, what is a facet?? clearly a solr concept.
# Actually, not strictly solr, it's more of a general search concept.
# A facet is a way to group things, sort of like tags.
# For our purposes, I'm reading this as synonymous with tags.

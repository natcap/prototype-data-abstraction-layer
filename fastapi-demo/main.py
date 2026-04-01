import json
import requests
from enum import Enum
from typing import Annotated, Optional

from ckanapi import RemoteCKAN
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field, validator


app = FastAPI()

# Production:
#CKAN_API_URL = 'https://data.naturalcapitalalliance.stanford.edu'
#PLACE_VOCAB_ID = '08e541f5-0f71-4931-bfc8-30bf66801146'
#COLLECTION_VOCAB_ID = 'coming-soon'

# Staging:
CKAN_API_URL = 'https://data-staging.naturalcapitalproject.org'
PLACE_VOCAB_ID = '10db4d07-a510-4838-ad1b-2adcf4a212f4'
COLLECTION_VOCAB_ID = 'coming-soon'

# Dev:
#CKAN_API_URL = 'https://localhost:8443'
#PLACE_VOCAB_ID = '7320b3ba-1ee9-4fc4-90b3-0240c3aa72df'
#COLLECTION_VOCAB_ID = '852876fe-49eb-4b88-95d9-44b35facf7ce'


class DataType(str, Enum):
    """Class for dataset formats InVEST can request."""
    raster = 'raster'
    vector = 'vector'
    table = 'table'


class LicenseInfo(BaseModel):
    """Class for a dataset's license information."""
    id: str | None = None
    title: str | None = None
    url: str | None = None


# Mapping of DataTypes to the values stored in the `sources_res_formats` extra
# of datasets on the Hub
HUB_DATATYPE_MAP = {
    DataType.raster: 'tif',
    DataType.vector: 'shp',
    DataType.table: 'csv'
}

# Mapping of DataTypes to relevant file extensions, for extracting the correct
# Resource from a Data Hub Package
EXTENSION_MAP = {
    DataType.vector: ['SHP', 'GEOJSON'],
    DataType.raster: ['TIF', 'TIFF'],
    DataType.table: ['CSV']
}

def _resource_type_matches(url, datatype):
    """Check a Resource file extension against the expected datatype."""
    extension = url.rsplit('.', 1)[-1].upper()
    if extension in EXTENSION_MAP[datatype]:
        return True

def _tag_search_string_and(tags):
    """Format a search string for tags using AND syntax.

    All tags must be wrapped in double quotes in case they contain whitespace.
    """
    tag_str = '" AND "'.join(tag for tag in tags)
    return f'tags:("{tag_str}")'


def _tag_search_string_or(tags):
    """Format a search string for tags using OR syntax.

    All tags must be wrapped in double quotes in case they contain whitespace.
    """
    tag_str = '" OR "'.join(tag for tag in tags)
    return f'tags:("{tag_str}")'


class SearchParams(BaseModel):
    """Class for an InVEST input search."""
    tags: list[str]
    """List of keywords from a shared vocabulary between InVEST and the Data Hub."""
    datatype: DataType
    """The file format. One of: raster, vector, or csv."""
    extent: Optional[list[float]] = None
    """A 4-element iterable of [minx, miny, maxx, maxy] in EPSG:4326"""
    sibling: str | None = None
    """The relation tag linking two inputs."""

    @validator('extent')
    def validate_extent_length(cls, v):
        assert len(v) == 4, 'extent must be a list of length 4'
        return v


class DatasetSearchResult(BaseModel):
    """Class containing details of a Data Hub dataset."""
    dataset_url: str
    """The URL of the dataset, to be used as an InVEST input."""
    source_catalog_url: str
    """The URL to the Package containing the dataset on the Hub."""
    name: str
    """The dataset name."""
    description: str
    """The dataset description."""
    extent: Optional[list[float]] = None
    """A 4-element iterable of [minx, miny, maxx, maxy] in EPSG:4326"""
    tags: list[str]
    """All non-vocabulary tags associated with the dataset."""
    places: list[str]
    """Place vocabulary tags associated with the dataset."""
    collection: list[str]
    """The Collections the dataset is a part of.

    To be used as the `sibling` input in a related search, when relevant.
    """
    license: LicenseInfo
    """Dict containing the license id, title, and url."""
    author: str
    """The dataset author."""
    created: str
    """The dataset's ``metadata_created`` date."""
    last_updated: str
    """The dataset's ``metadata_modified`` date."""


class SearchResponse(BaseModel):
    """Class for search results, including both result count and datasets."""
    count: int
    """The number of returned search results."""
    datasets: list[DatasetSearchResult]
    """List of DatasetSearchResult objects representing relevant search results."""


@app.get("/search_dataset/")
def search_dataset(filter_query: Annotated[SearchParams, Query()]) -> SearchResponse:
    """Search for datasets on the Data Hub that match the provided criteria."""
    # For dev: need to set verify=False when working with the dev CKAN container
    session = requests.Session()
    session.verify = False

    # Skip collections for now:
    fq_list = ['type:dataset']
    extras = {}

    fq_list.append(f'extras_sources_res_formats:{HUB_DATATYPE_MAP[filter_query.datatype]}')
    fq_list.append(_tag_search_string_or(filter_query.tags))

    if filter_query.sibling:
        fq_list.append(f'extras_collection:"{filter_query.sibling.upper()}"')

    if filter_query.extent:
        extras['ext_bbox'] = ','.join((str(coord) for coord in filter_query.extent))

    datasets = []
    with RemoteCKAN(CKAN_API_URL, session=session) as catalog:
        offset = 0
        count = None
        while True:
            result = catalog.action.package_search(
                fq_list=fq_list,
                start=offset,
                extras=extras,
                sort='score desc' # Most relevant results first
            )
            if not count:
                count = result['count']

            for dataset in result['results']:
                bbox = None
                index = 0
                while index < len(dataset['extras']):
                    extra = dataset['extras'][index]
                    if extra['key'] == 'spatial':
                        spatial = extra['value']
                        spatial_dict = json.loads(spatial)
                        coords = spatial_dict['coordinates']
                        bbox = [coords[0][0][0], coords[0][1][1],
                                coords[0][2][0], coords[0][0][1]]
                        break
                    index += 1

                dataset_url = None
                index = 0
                while index < len(dataset['resources']):
                    res = dataset['resources'][index]
                    if _resource_type_matches(res['url'], filter_query.datatype):
                        dataset_url = res['url']
                        break
                    index += 1
                if not dataset_url:
                    # If no matching resource can be determined for some reason, skip
                    offset += 1
                    continue

                datasets.append(DatasetSearchResult(
                    dataset_url=dataset_url,
                    source_catalog_url=f'{CKAN_API_URL}/dataset/{dataset["name"]}',
                    name=dataset.get('title'),
                    description=dataset.get('notes'),
                    extent=bbox,
                    tags=[tag['name'] for tag in dataset['tags']
                          if not tag['vocabulary_id']],
                    places=[tag['name'] for tag in dataset['tags']
                            if tag['vocabulary_id'] == PLACE_VOCAB_ID],
                    collection=[tag['name'] for tag in dataset['tags']
                            if tag['vocabulary_id'] == COLLECTION_VOCAB_ID],
                    license=LicenseInfo(
                        id=dataset.get('license_id'),
                        title=dataset.get('license_title'),
                        url=dataset.get('license_url'),
                    ),
                    author=dataset.get('author'),
                    created=dataset.get('metadata_created'),
                    last_updated=dataset.get('metadata_modified'))
                )
                offset += 1
            if offset >= count:
                break

    return SearchResponse(
        count=len(datasets),
        datasets=datasets
    )

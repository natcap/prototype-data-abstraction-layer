from dhal_api.models import DataType


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


def resource_type_matches(url, datatype):
    """Check a Resource file extension against the expected datatype."""
    extension = url.rsplit('.', 1)[-1].upper()
    if extension in EXTENSION_MAP[datatype]:
        return True


def tag_search_string_and(tags):
    """Format a search string for tags using AND syntax.

    All tags must be wrapped in double quotes in case they contain whitespace.
    """
    tag_str = '" AND "'.join(tag for tag in tags)
    return f'tags:("{tag_str}")'


def tag_search_string_or(tags):
    """Format a search string for tags using OR syntax.

    All tags must be wrapped in double quotes in case they contain whitespace.
    """
    tag_str = '" OR "'.join(tag for tag in tags)
    return f'tags:("{tag_str}")'

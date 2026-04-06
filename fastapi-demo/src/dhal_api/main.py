import logging
import json
import requests
from typing import Annotated

import ckanapi.errors
from ckanapi import RemoteCKAN
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from dhal_api import utils
from dhal_api.models import (
    DataType, LicenseInfo, SearchParams, DatasetSearchResult, SearchResponse
)


LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="Natural Capital Alliance Data Hub Abstraction Layer",
    description="API for querying the NatCap Data Hub from InVEST.",
    version="0.1.0"
)

# Production:
#CKAN_API_URL = 'https://data.naturalcapitalalliance.stanford.edu'
#PLACE_VOCAB_ID = '08e541f5-0f71-4931-bfc8-30bf66801146'
#COLLECTION_VOCAB_ID = 'coming-soon'

# Staging:
#CKAN_API_URL = 'https://data-staging.naturalcapitalproject.org'
#PLACE_VOCAB_ID = '10db4d07-a510-4838-ad1b-2adcf4a212f4'
#COLLECTION_VOCAB_ID = 'coming-soon'

# Dev:
CKAN_API_URL = 'https://localhost:8443'
PLACE_VOCAB_ID = '7320b3ba-1ee9-4fc4-90b3-0240c3aa72df'
COLLECTION_VOCAB_ID = '852876fe-49eb-4b88-95d9-44b35facf7ce'


class CKANException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@app.exception_handler(CKANException)
def ckan_exception_handler(request: Request, exc: CKANException) -> JSONResponse:
    """Handle exceptions thrown by RemoteCKAN."""
    return JSONResponse(status_code=exc.status_code,
                        content={
                            "error_code": exc.status_code,
                            "error_message": exc.message
                        })


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unexpected exceptions."""
    LOGGER.error(f"Exception: {str(exc)}")
    return JSONResponse(status_code=500,
                        content={
                            "error_code": 500,
                            "error_message": exc.__str__()
                        })


@app.get("/search_dataset/")
def search_dataset(filter_query: Annotated[SearchParams, Query()]) -> SearchResponse:
    """Search for datasets on the Data Hub that match the provided criteria."""
    session = requests.Session()
    # For dev: need to set verify=False when working with the dev CKAN container
    session.verify = False

    q = utils.tag_search_string_or(filter_query.tags)

    # Skip collections for now:
    fq_list = ['type:dataset']
    fq_list.append(
        f'extras_sources_res_formats:{utils.HUB_DATATYPE_MAP[filter_query.datatype]}')
    if filter_query.sibling:
        fq_list.append(f'extras_collection:"{filter_query.sibling.upper()}"')

    extras = {}
    if filter_query.extent:
        extras['ext_bbox'] = ','.join((str(coord) for coord in filter_query.extent))

    datasets = []
    with RemoteCKAN(CKAN_API_URL, session=session) as catalog:
        offset = 0
        count = None

        ckan_query_dict = {
            'q': q,
            'fq_list': fq_list,
            'start': offset,
            'extras': extras,
            'sort': 'score desc' # Most relevant results first
        }

        while True:
            try:
                result = catalog.action.package_search(**ckan_query_dict)
            except ckanapi.errors.CKANAPIError as e:
                LOGGER.exception(
                    "Exception on RemoteCKAN catalog.action.package_search:"
                    f" {e}; search parameters: {ckan_query_dict}")
                raise CKANException(status_code=500, message=f"{e}")

            if 'count' not in result or 'results' not in result:
                # This shouldn't happen, but check just in case!
                LOGGER.error(f"CKAN returned unexpected payload: {result}")
                raise CKANException(status_code=404,
                                    message="An error occurred in the CKAN search.")

            if not count:
                count = result.get('count', 0)

            for dataset in result.get('results', []):
                bbox = None
                index = 0
                while index < len(dataset.get('extras', [])):
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
                while index < len(dataset.get('resources', [])):
                    res = dataset['resources'][index]
                    if utils.resource_type_matches(res['url'], filter_query.datatype):
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

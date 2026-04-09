from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


class SearchParams(BaseModel):
    """Class for an InVEST input search."""
    tags: list[str]
    """List of keywords from a shared vocabulary between InVEST and the Data Hub."""
    datatype: DataType
    """The file format. One of: raster, vector, or table."""
    extent: Optional[list[float]] = None
    """A 4-element iterable of [minx, miny, maxx, maxy] in EPSG:4326.
    Extent must not include inf or -inf.
    """
    sibling: str | None = None
    """The relation tag linking two inputs."""

    @field_validator('extent')
    def validate_extent_length(cls, v):
        assert len(v) == 4, 'extent must be a list of length 4'
        return v

    @field_validator('extent')
    def validate_extent_infinity(cls, v):
        # CKAN spatial search 404s on infinity, after a long wait.
        assert float('inf') not in v and -float('inf') not in v, (
                'extent cannot include infinity')
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
    """The Collections the dataset is a part of. To be used as the
    `sibling` input in a related search, when relevant.
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

import enum
import typing
from dataclasses import dataclass


class InVESTInputType(enum.Enum):
    DEM = 'digital elevation model'
    K_FACTOR = 'soil erodibility'
    LULC = 'land use land cover'


INVEST_TYPES = set(
    k for k in dir(InVESTInputType) if not k.startswith('_'))


@dataclass
class RasterLayer():
    source_catalog_dataset_url: str
    layer_url: str
    source_rest_data: str
    name: str
    invest_type: InVESTInputType
    license: str
    description: str
    wgs84_extent: typing.List


@dataclass
class VectorLayer():
    source_catalog_dataset_url: str
    source_rest_data: str
    name: str
    license: str
    description: str
    wgs84_extent: typing.List

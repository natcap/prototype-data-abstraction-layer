# run this script after starting the server via `fastapi dev`
import pprint
import requests

params = { 
    'tags': ['LULC'],
    'datatype': 'raster',
    'extent': [
        -126.56250000000001,
        25.190029755362676,
        -92.10937500000001,
        45.60250901510299,
    ], 
#    'sibling': 'ESA CCI' # WIP: handle related datasets
}

resp = requests.get(
    'http://127.0.0.1:8000/search_dataset/', params=params, verify=False)
resp.raise_for_status()
data = resp.json()
pprint.pp(data)

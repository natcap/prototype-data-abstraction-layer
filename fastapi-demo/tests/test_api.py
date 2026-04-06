import json
import os
import unittest
from unittest.mock import Mock, patch

from ckanapi.errors import CKANAPIError
from fastapi.testclient import TestClient

from dhal_api.main import app


DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')

client = TestClient(app, raise_server_exceptions=False)


class APITests(unittest.TestCase):

    def test_search_dataset(self):
        """Simple test case where CKAN returns one Package."""
        with open(f'{DATA_DIR}/ckan_response_data_simple.json') as f:
            success_resp = json.load(f)
        with patch('dhal_api.main.RemoteCKAN.call_action') as mock_ckan:
            mock_ckan.return_value = success_resp

            params = {
                "tags": ["DEM"],
                "datatype": "raster"
            }
            resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)

        with open(f'{DATA_DIR}/formatted_success_payload_simple.json') as test_resp:
            expected_data = json.load(test_resp)
            self.assertEqual(data, expected_data)

    def test_search_dataset_no_results(self):
        """Test response when no matching datasets found."""
        with patch('dhal_api.main.RemoteCKAN.call_action') as mock_ckan:
            mock_ckan.return_value = {'count': 0, 'results': []}

            params = {
                "tags": ["DEM"],
                "datatype": "vector"
            }
            resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data, {'count': 0, 'datasets': []})

    def test_search_dataset_filter_result(self):
        """CKAN returns Package where relevant Resource cannot be determined."""
        with open(f'{DATA_DIR}/ckan_response_data_filter.json') as f:
            success_resp = json.load(f)
        with patch('dhal_api.main.RemoteCKAN.call_action') as mock_ckan:
            mock_ckan.return_value = success_resp

            params = {
                "tags": ["COASTLINE"],
                "datatype": "vector"
            }
            resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)

        with open(f'{DATA_DIR}/formatted_success_payload_filter.json') as test_resp:
            expected_data = json.load(test_resp)
            self.assertEqual(data, expected_data)

    def test_search_dataset_bad_query_missing_key(self):
        """Test API handles bad query parameters: missing required key."""
        params = {
            "tags": ["DEM"],
        }
        resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 422)
        assert 'datatype' in resp.json()['detail'][0]['loc']

    def test_search_dataset_bad_query_invalid_extent(self):
        """Test API handles bad query parameters: extent list len < 4."""
        params = {
            "tags": ["DEM"],
            "datatype": "raster",
            "extent": [-126.56, 25.19, -92.11]
        }
        resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 422)
        assert 'extent' in resp.json()['detail'][0]['loc']

    def test_search_dataset_bad_query_infinity_extent(self):
        """Test API handles bad query parameters: extent includes infinity."""
        params = {
            "tags": ["DEM"],
            "datatype": "raster",
            "extent": [float('inf'), -126.56, 25.19, -92.11]
        }
        resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 422)
        assert 'extent' in resp.json()['detail'][0]['loc']

    def test_handle_ckan_payload_missing_count_results(self):
        """Handle case where CKAN payload lacks `count` or `results`."""
        with patch('dhal_api.main.RemoteCKAN.call_action') as mock_ckan:
            mock_ckan.return_value = {'error': 'Something went wrong'}

            params = {
                "tags": ["DEM"],
                "datatype": "raster"
            }
            resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("error_message", data.keys())

    def test_handle_ckan_error(self):
        """Test handling CKANAPIError."""
        with patch('dhal_api.main.RemoteCKAN.call_action') as mock_ckan:
            mock_ckan.side_effect = Exception(CKANAPIError)

            params = {
                "tags": ["DEM"],
                "datatype": "raster"
            }
            resp = client.get("/search_dataset/", params=params)

        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertIn("error_message", data.keys())

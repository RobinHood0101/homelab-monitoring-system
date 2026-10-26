import unittest
from unittest.mock import patch

import requests

import app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @patch("app.requests.get", side_effect=requests.ConnectionError("sensor API unavailable"))
    def test_missing_sensor_data_is_shown_as_unavailable(self, _request):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Keine Live-Sensordaten", response.get_data(as_text=True))
        self.assertNotIn("23.0", response.get_data(as_text=True))

    @patch("app.requests.get", side_effect=requests.ConnectionError("sensor API unavailable"))
    def test_health_endpoint_reports_sensor_api_failure(self, _request):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "unavailable"})


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app


class SensorApiTests(unittest.TestCase):
    def setUp(self):
        self.cached_reading = app.cached_reading
        self.cached_at = app.cached_at
        app.cached_reading = None
        app.cached_at = 0

    def tearDown(self):
        app.cached_reading = self.cached_reading
        app.cached_at = self.cached_at

    def test_validates_sensor_json(self):
        reading = app._validate_reading(
            '{"temperature_celsius":24.3,"humidity_percent":48.5}'
        )
        self.assertEqual(reading, {
            "temperature_celsius": 24.3,
            "humidity_percent": 48.5,
        })

    def test_rejects_non_finite_sensor_values(self):
        with self.assertRaises(app.SensorReadError):
            app._validate_reading(
                '{"temperature_celsius":NaN,"humidity_percent":48.5}'
            )

    @patch(
        "app._read_remote_sensor",
        return_value={"temperature_celsius": 24.3, "humidity_percent": 48.5},
    )
    def test_status_uses_live_sensor_reading(self, _read_sensor):
        status = app.get_sensor_status()
        self.assertEqual(status["temperature_celsius"], 24.3)
        self.assertEqual(status["humidity_percent"], 48.5)
        self.assertTrue(status["connected"])
        self.assertEqual(status["sensor"], "DHT22")

    @patch("app._read_remote_sensor", side_effect=app.SensorReadError("SSH unavailable"))
    def test_sensor_failure_is_not_replaced_with_fake_data(self, _read_sensor):
        with self.assertRaises(HTTPException) as raised:
            app.get_sensor_status()
        self.assertEqual(raised.exception.status_code, 503)

        response = app.metrics()
        exposition = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("homelab_sensor_connected 0.0", exposition)
        self.assertIn("homelab_temperature_celsius NaN", exposition)
        self.assertNotIn("23.0", exposition)

    def test_health_score_penalizes_out_of_range_readings(self):
        self.assertEqual(app._health_score(22.0, 45.0), 100.0)
        self.assertLess(app._health_score(35.0, 80.0), 100.0)


if __name__ == "__main__":
    unittest.main()

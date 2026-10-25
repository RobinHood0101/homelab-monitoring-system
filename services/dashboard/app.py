import os
from typing import Any

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__, template_folder='templates', static_folder='static')

SENSOR_API_URL = os.getenv('SENSOR_API_URL', 'http://localhost:8000')


def get_sensor_status() -> dict[str, Any]:
    try:
        response = requests.get(f'{SENSOR_API_URL}/api/status', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {
            'temperature': 23.0,
            'humidity': 48.0,
            'light': 650,
            'door_open': False,
            'motion_detected': False,
            'cpu_usage': 35.0,
            'memory_usage': 52.0,
            'disk_usage': 68.0,
            'uptime_seconds': 4200,
            'health_score': 94.0,
            'mode': 'light',
            'lcd_status': 'OK',
        }


@app.get('/')
def dashboard_index():
    status = get_sensor_status()
    theme = 'dark' if status.get('mode') == 'dark' else 'light'
    return render_template('index.html', status=status, theme=theme)


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok', 'sensor_api': SENSOR_API_URL})


if __name__ == '__main__':
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    app.run(host=host, port=int(os.getenv('DASHBOARD_PORT', '8080')), debug=False)

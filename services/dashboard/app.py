import os

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__, template_folder='templates', static_folder='static')

SENSOR_API_URL = os.getenv('SENSOR_API_URL', 'http://localhost:8000')


def get_sensor_status():
    response = requests.get(f'{SENSOR_API_URL}/api/status', timeout=10)
    response.raise_for_status()
    return response.json()


@app.get('/')
def dashboard_index():
    try:
        status = get_sensor_status()
    except requests.RequestException:
        app.logger.exception('Could not retrieve a live sensor reading')
        return render_template('unavailable.html'), 503
    return render_template('index.html', status=status)


@app.get('/api/health')
def health():
    try:
        get_sensor_status()
    except requests.RequestException:
        app.logger.exception('Sensor API health check failed')
        return jsonify({'status': 'unavailable'}), 503
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    app.run(host=host, port=int(os.getenv('DASHBOARD_PORT', '8080')), debug=False)

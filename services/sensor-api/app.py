from __future__ import annotations

import math
import os
import time
from threading import Lock

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from starlette.responses import Response

app = FastAPI(title='Homelab Sensor API', version='1.0.0')

TEMPERATURE = Gauge('homelab_temperature_celsius', 'Current room temperature in Celsius')
HUMIDITY = Gauge('homelab_humidity_percent', 'Current humidity percentage')
LIGHT = Gauge('homelab_light_lux', 'Current ambient light in lux')
DOOR = Gauge('homelab_door_open', 'Door status: 1 when open, 0 when closed')
MOTION = Gauge('homelab_motion_detected', 'Motion status: 1 when detected, 0 when idle')
CPU = Gauge('homelab_cpu_usage_percent', 'Current CPU usage percentage')
MEMORY = Gauge('homelab_memory_usage_percent', 'Current memory usage percentage')
DISK = Gauge('homelab_disk_usage_percent', 'Current disk usage percentage')
UPTIME = Gauge('homelab_uptime_seconds', 'Host uptime in seconds')
HEALTH = Gauge('homelab_health_score', 'Overall health score from 0 to 100')

state_lock = Lock()

class SensorState:
    def __init__(self):
        self.temperature = 23.0
        self.humidity = 48.0
        self.light = 620
        self.door_open = False
        self.motion_detected = False
        self.cpu = 35.0
        self.memory = 52.0
        self.disk = 68.0
        self.uptime_start = time.time()

    def tick(self):
        t = time.time()
        cycle = t / 30.0
        self.temperature = 23.0 + math.sin(cycle) * 4.0 + (self.cpu / 25.0) - 1.0
        self.humidity = 48.0 + math.cos(cycle * 1.5) * 10.0
        self.light = max(120, min(1200, 700 + math.sin(cycle * 2.0) * 250 + (30 if self.motion_detected else 0)))
        self.cpu = max(15.0, min(95.0, 35.0 + math.sin(cycle * 1.7) * 25.0 + (self.door_open * 8.0)))
        self.memory = max(30.0, min(90.0, 52.0 + math.cos(cycle * 1.1) * 12.0))
        self.disk = max(45.0, min(95.0, 68.0 + math.sin(cycle * 0.9) * 8.0))
        self.uptime = max(0.0, time.time() - self.uptime_start)
        self.health = self.calculate_health_score()

    def calculate_health_score(self):
        score = 100.0
        score -= max(0.0, self.cpu - 80.0) * 0.6
        score -= max(0.0, self.memory - 80.0) * 0.5
        score -= max(0.0, self.disk - 80.0) * 0.7
        score -= max(0.0, self.temperature - 30.0) * 1.2
        score -= max(0.0, 60.0 - self.light) * 0.02
        if self.door_open:
            score -= 8.0
        if self.motion_detected:
            score -= 2.0
        return max(0.0, min(100.0, round(score, 1)))

    def snapshot(self):
        return {
            'temperature': round(self.temperature, 1),
            'humidity': round(self.humidity, 1),
            'light': int(self.light),
            'door_open': self.door_open,
            'motion_detected': self.motion_detected,
            'cpu_usage': round(self.cpu, 1),
            'memory_usage': round(self.memory, 1),
            'disk_usage': round(self.disk, 1),
            'uptime_seconds': int(self.uptime),
            'health_score': self.health,
            'mode': 'dark' if self.light < 500 else 'light',
            'lcd_status': 'WARNING' if self.temperature > 30 or self.cpu > 80 or self.disk > 85 else 'OK',
        }

sensor_state = SensorState()


def update_metrics():
    with state_lock:
        sensor_state.tick()
        payload = sensor_state.snapshot()

    TEMPERATURE.set(payload['temperature'])
    HUMIDITY.set(payload['humidity'])
    LIGHT.set(payload['light'])
    DOOR.set(1 if payload['door_open'] else 0)
    MOTION.set(1 if payload['motion_detected'] else 0)
    CPU.set(payload['cpu_usage'])
    MEMORY.set(payload['memory_usage'])
    DISK.set(payload['disk_usage'])
    UPTIME.set(payload['uptime_seconds'])
    HEALTH.set(payload['health_score'])


@app.on_event('startup')
def startup_event():
    update_metrics()


@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.get('/api/status')
def get_status():
    with state_lock:
        payload = sensor_state.snapshot()
    return payload


@app.get('/api/lcd')
def lcd_status():
    with state_lock:
        payload = sensor_state.snapshot()
    return {'status_line': f"TEMP: {payload['temperature']}C HUM: {payload['humidity']}%" , 'warning': payload['lcd_status'] == 'WARNING'}


@app.get('/metrics')
def metrics():
    update_metrics()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('SENSOR_API_PORT', '8000')))

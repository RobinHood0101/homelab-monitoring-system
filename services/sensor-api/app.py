from __future__ import annotations

import json
import logging
import math
import os
import shlex
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import paramiko
from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from starlette.responses import Response

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("homelab.sensor_api")

app = FastAPI(title="Homelab Sensor API", version="2.0.0")

TEMPERATURE = Gauge("homelab_temperature_celsius", "Temperature measured by the JoyPi DHT22")
HUMIDITY = Gauge("homelab_humidity_percent", "Relative humidity measured by the JoyPi DHT22")
HEALTH = Gauge("homelab_health_score", "Environmental health score from 0 to 100")
SENSOR_CONNECTED = Gauge("homelab_sensor_connected", "Whether a current DHT22 reading is available")
LAST_SUCCESS = Gauge("homelab_sensor_last_success_unixtime", "Unix timestamp of the last successful DHT22 reading")
TEMPERATURE.set(float("nan"))
HUMIDITY.set(float("nan"))
HEALTH.set(float("nan"))
SENSOR_CONNECTED.set(0)
LAST_SUCCESS.set(0)

state_lock = Lock()
cached_reading: dict[str, Any] | None = None
cached_at = 0.0
CACHE_SECONDS = float(os.getenv("SENSOR_CACHE_SECONDS", "10"))


class SensorReadError(Exception):
    pass


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SensorReadError(f"Missing required setting: {name}")
    return value


def _validate_reading(raw: str) -> dict[str, float]:
    try:
        payload = json.loads(raw)
        temperature = float(payload["temperature_celsius"])
        humidity = float(payload["humidity_percent"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SensorReadError("JoyPi returned invalid sensor JSON") from exc

    if not math.isfinite(temperature) or not -40 <= temperature <= 80:
        raise SensorReadError("JoyPi returned an invalid temperature")
    if not math.isfinite(humidity) or not 0 <= humidity <= 100:
        raise SensorReadError("JoyPi returned invalid humidity")
    return {
        "temperature_celsius": round(temperature, 1),
        "humidity_percent": round(humidity, 1),
    }


def _read_remote_sensor() -> dict[str, float]:
    host = _required_setting("JOYPI_SSH_HOST")
    username = _required_setting("JOYPI_SSH_USER")
    key_path = _required_setting("JOYPI_SSH_KEY")
    known_hosts_path = _required_setting("JOYPI_KNOWN_HOSTS")
    python_path = os.getenv("JOYPI_PYTHON", "python3").strip()
    agent_path = _required_setting("JOYPI_AGENT_PATH")
    key_passphrase = os.getenv("JOYPI_SSH_KEY_PASSPHRASE") or None
    port = int(os.getenv("JOYPI_SSH_PORT", "22"))
    timeout = float(os.getenv("JOYPI_SSH_TIMEOUT_SECONDS", "8"))

    client = paramiko.SSHClient()
    try:
        client.load_host_keys(known_hosts_path)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=key_path,
            passphrase=key_passphrase,
            look_for_keys=False,
            allow_agent=False,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
        )
        command = f"{shlex.quote(python_path)} {shlex.quote(agent_path)} --json"
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        output = stdout.read().decode("utf-8").strip()
        error_output = stderr.read().decode("utf-8").strip()
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            detail = error_output or f"remote command exited with status {exit_status}"
            raise SensorReadError(f"JoyPi sensor reader failed: {detail}")
        return _validate_reading(output)
    except (OSError, paramiko.SSHException) as exc:
        raise SensorReadError(f"SSH connection to JoyPi failed: {exc}") from exc
    finally:
        client.close()


def _health_score(temperature: float, humidity: float) -> float:
    temperature_penalty = max(0.0, abs(temperature - 22.0) - 3.0) * 4.0
    humidity_penalty = max(0.0, 35.0 - humidity, humidity - 60.0) * 1.5
    return round(max(0.0, min(100.0, 100.0 - temperature_penalty - humidity_penalty)), 1)


def get_sensor_status() -> dict[str, Any]:
    global cached_reading, cached_at

    with state_lock:
        if cached_reading is not None and time.monotonic() - cached_at < CACHE_SECONDS:
            return cached_reading.copy()
        try:
            reading = _read_remote_sensor()
        except (SensorReadError, ValueError) as exc:
            TEMPERATURE.set(float("nan"))
            HUMIDITY.set(float("nan"))
            HEALTH.set(float("nan"))
            SENSOR_CONNECTED.set(0)
            logger.error("Could not read the JoyPi DHT22: %s", exc)
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        temperature = reading["temperature_celsius"]
        humidity = reading["humidity_percent"]
        health = _health_score(temperature, humidity)
        warning = temperature > 30 or temperature < 15 or humidity > 70 or humidity < 20
        status = {
            **reading,
            "sensor": "DHT22",
            "connected": True,
            "health_score": health,
            "status": "WARNING" if warning else "OK",
            "read_at": datetime.now(timezone.utc).isoformat(),
        }
        cached_reading = status
        cached_at = time.monotonic()

        TEMPERATURE.set(temperature)
        HUMIDITY.set(humidity)
        HEALTH.set(health)
        SENSOR_CONNECTED.set(1)
        LAST_SUCCESS.set(time.time())
        return status.copy()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    get_sensor_status()
    return {"status": "ready"}


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    return get_sensor_status()


@app.get("/metrics")
def metrics() -> Response:
    try:
        get_sensor_status()
    except HTTPException:
        pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("SENSOR_API_PORT", "8000")))

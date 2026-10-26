#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time


def read_dht22():
    import adafruit_dht
    import board

    pin_number = int(os.getenv("DHT22_GPIO", "4"))
    pin = getattr(board, f"D{pin_number}", None)
    if pin is None:
        raise ValueError(f"BCM GPIO {pin_number} is not available on this board")

    sensor = adafruit_dht.DHT22(pin, use_pulseio=False)
    try:
        last_error = None
        for attempt in range(3):
            try:
                temperature = sensor.temperature
                humidity = sensor.humidity
                if temperature is None or humidity is None:
                    raise RuntimeError("DHT22 returned an empty reading")
                return {
                    "temperature_celsius": round(float(temperature), 1),
                    "humidity_percent": round(float(humidity), 1),
                }
            except RuntimeError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2)
        raise RuntimeError(f"DHT22 read failed after 3 attempts: {last_error}")
    finally:
        sensor.exit()


def main():
    parser = argparse.ArgumentParser(description="Read the JoyPi DHT22 sensor")
    parser.add_argument("--json", action="store_true", help="print one JSON reading")
    parser.parse_args()

    try:
        print(json.dumps(read_dht22(), separators=(",", ":")))
    except Exception as exc:
        print(f"DHT22 read failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

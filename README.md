# Smart Homelab Monitoring System

This project implements the Smart Homelab Monitoring System described in the PDF: a distributed monitoring stack for a home lab with Linux and Windows endpoints, sensor data from a JoyPi, a local status display, and dashboards + alerts for operational visibility.

## Included components

- Sensor API for temperature, humidity, light, motion, and door state
- Prometheus metrics collection
- Grafana dashboards and datasource provisioning
- Loki + Promtail log collection
- Dashboard web page with health score and environment overview
- Alert rules for temperature, disk usage, and sensor API availability

## Quick start

1. Start the stack:
   docker compose up --build
2. Open the dashboard:
   http://localhost:8081/
3. Open Grafana:
   http://localhost:3000/
   Username: admin
   Password: admin
4. Open Prometheus:
   http://localhost:9090/

## Project structure

- services/sensor-api — Python FastAPI service exposing Prometheus metrics and JSON status
- services/dashboard — Flask dashboard with a home-lab overview and health score
- services/prometheus — Prometheus config and alert rules
- services/grafana — Grafana provisioning and dashboards
- services/loki — Loki configuration
- services/promtail — log collection config

## Main features

- Real-time overview of CPU, RAM, disk, and environment data
- Light / dark mode based on ambient light level
- Homelab health score for a simple overall system status
- Alerts triggered from Prometheus rules
- Log ingestion via Loki and visualization in Grafana
- LCD-style status indicator simulated in the API output

## Notes

This is a working starter implementation of the concept from the PDF. The bundled Node Exporter runs without mounting `/` so it can start under Docker Desktop on Windows; its metrics are from the Docker Linux environment, not the Windows host. To monitor Windows host metrics, install `windows_exporter` on Windows and add `host.docker.internal:9182` as a Prometheus scrape target. On a Linux host, configure a host-mounted Node Exporter for full host metrics. The simulated sensor values can be replaced with readings from a real JoyPi sensor board.

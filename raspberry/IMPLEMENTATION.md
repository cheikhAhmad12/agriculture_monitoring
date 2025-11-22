# Raspberry Pi implementation overview

This document summarizes what the Raspberry-side code does, how it is structured, and how data flows between modules.

## Goals
- Provide a drone-side pipeline that:
  - Connects to ArduPilot/Navio2 (DroneKit) for telemetry.
  - Loads RGB + NIR captures, computes NDVI, and publishes a summary.
  - Publishes telemetry even when NDVI is not run.
- Provide an irrigation controller that:
  - Listens for watering commands over MQTT.
  - Converts requested liters into valve open durations based on each valve’s flow rate.
  - Drives GPIO pins (or dry-run for development) and publishes valve status periodically.

## Folder structure
- `raspberry/main.py`: CLI entrypoint for both roles (`drone-cycle`, `irrigation`).
- `raspberry/config/default_config.yaml`: All configurable values (MQTT, camera paths, valve pins/flows, thresholds).
- `raspberry/requirements.txt`: Python dependencies for the Pi.
- `raspberry/drone/`
  - `autopilot.py`: Thin wrapper around DroneKit connect/read telemetry. Falls back to mocked payload if unavailable.
  - `camera.py`: Loads RGB and NIR images, resizes, prepares arrays.
  - `analysis.py`: Computes NDVI, summarizes stats (mean/min/max, stress ratio).
  - `service.py`: Orchestrates a capture cycle: NDVI + telemetry published over MQTT.
- `raspberry/irrigation/`
  - `controller.py`: MQTT listener for irrigation commands; schedules valve activation threads; publishes status.
- `raspberry/utils/`
  - `config_loader.py`: Loads YAML with dotted-key access.
  - `mqtt_client.py`: Small MQTT JSON wrapper (paho-mqtt).
  - `gpio.py`: GPIO abstraction with dry-run support; valve model + loader.

## Data flow
1) **Drone cycle (`drone-cycle`)**
   - Inputs: RGB path, NIR path.
   - NDVI pipeline: `camera.py` -> `analysis.py` -> summary dict.
   - Telemetry: `autopilot.py` reads ArduPilot via connection string (e.g., `udp:0.0.0.0:14550`). If not connected, returns `{"status": "disconnected"}`.
   - Output MQTT topic (configurable): `mqtt.topics.analysis` with `{timestamp, telemetry, ndvi:{mean,min,max,stress_ratio}}`.
   - Telemetry-only publishing: `service.publish_telemetry_only()` can be reused if needed.

2) **Irrigation controller (`irrigation`)**
   - Subscribes to `mqtt.topics.irrigation_command`.
   - Expected payload: `{"parcel_id": "<id>", "liters": <float>}`.
   - Looks up valve config by `parcel_id`, computes duration `seconds = (liters / flow_lpm) * 60`.
   - Enforces `max_parallel_valves`; runs each valve on its own thread.
   - Uses GPIO (BCM mode) unless `--dry-run` is passed; publishes status periodically to `mqtt.topics.irrigation_status`.

3) **Waypoint-triggered NDVI (`drone-waypoint-listener`)**
   - Registers a handler for `MISSION_ITEM_REACHED` via `autopilot.add_waypoint_reached_handler`.
   - On each waypoint event, spawns a thread to run `run_capture_and_publish` with configured/default capture paths.
   - Keeps the process alive while waiting for events; MQTT loop must be running (handled in CLI).

## Configuration highlights (`config/default_config.yaml`)
- `mqtt`: broker host/port, credentials, client_id, topics for telemetry/analysis/irrigation.
- `drone.autopilot_connection`: MAVLink/DroneKit endpoint from Navio2 ArduPilot (e.g., `udp:0.0.0.0:14550`).
- `drone.camera`: capture locations and resize dimensions for NDVI.
- `drone.ndvi.stress_threshold`: NDVI cutoff below which pixels count toward `stress_ratio`.
- `irrigation.valves`: list of valves with `id` (parcel name), `gpio_pin` (BCM), and `flow_lpm` (liters/min).
- `irrigation.max_parallel_valves`: limit concurrent activations to protect power/pressure.
- `irrigation.publish_interval_seconds`: how often to broadcast valve status.

## MQTT contract (defaults)
- Publish:
  - `agriculture/drone/analysis`: `{timestamp, telemetry, ndvi}`
  - `agriculture/drone/telemetry`: `{timestamp, telemetry}`
  - `agriculture/irrigation/status`: `{timestamp, valves:{id:{is_open,last_opened_at,last_closed_at}}}`
- Subscribe:
  - `agriculture/irrigation/command`: `{parcel_id, liters}`
Adjust the `topics` block in YAML to fit your broker conventions.

## Commands (examples)
```bash
# Drone: process one RGB/NIR pair and publish NDVI summary
python -m raspberry.main --config raspberry/config/default_config.yaml \
  drone-cycle --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg

# Drone: wait for waypoint reached events and trigger NDVI
python -m raspberry.main --config raspberry/config/default_config.yaml \
  drone-waypoint-listener --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg

# Irrigation: listen for MQTT commands (dry-run for dev)
python -m raspberry.main --config raspberry/config/default_config.yaml irrigation --dry-run
```

## Assumptions and notes
- Camera acquisition itself is external; this code consumes saved RGB+NIR files.
- DroneKit/ArduPilot connection string must match your Navio2 setup; telemetry gracefully degrades if not connected.
- GPIO writes require running on a Pi with `RPi.GPIO`; use `--dry-run` on laptops.
- Flow rates (`flow_lpm`) must reflect real hardware to compute accurate open durations.
- No persistence layer is included; MQTT/cloud ingestion is expected downstream.

## What to adapt for your deployment
1. Update `config/default_config.yaml` with your MQTT broker, topic names, and Navio2 connection string.
2. Point `drone.camera` paths to where your capture process writes images.
3. Set real valve GPIO pins and flow rates; tune `max_parallel_valves` to your pump capacity.
4. Add TLS settings in `mqtt` if your broker requires it.

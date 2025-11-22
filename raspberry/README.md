# Raspberry Pi stack (drone + irrigation)

This folder provides the Raspberry Pi side of the agriculture monitoring project.

## Components
- `main.py`: CLI entrypoint for both Raspberry roles.
- `drone/`: NDVI pipeline and autopilot telemetry wrapper.
- `irrigation/`: Valve controller that consumes irrigation commands from MQTT.
- `utils/`: Config loader, MQTT wrapper, GPIO abstraction.
- `config/default_config.yaml`: Tweak network, camera, and valve definitions.
- `requirements.txt`: Python dependencies to install on the Pi.

## Quickstart
1. Install dependencies on the Pi (ideally in a virtualenv):
   ```bash
   pip install -r raspberry/requirements.txt
   ```
2. Adjust `raspberry/config/default_config.yaml` to your Wi-Fi mesh IPs, MQTT broker, image paths, and GPIO pins.

### Drone cycle
Compute NDVI from a pair of captures (RGB + NIR) and publish telemetry + summary to MQTT.
```bash
python -m raspberry.main --config raspberry/config/default_config.yaml \
  drone-cycle --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg
```
The code tries to read telemetry from ArduPilot/ Navio2 via the `autopilot_connection` string. If `dronekit` or hardware is absent it publishes a mocked telemetry payload.

### Drone waypoint listener
Trigger NDVI automatically when ArduPilot reports a waypoint reached (MISSION_ITEM_REACHED).
```bash
python -m raspberry.main --config raspberry/config/default_config.yaml \
  drone-waypoint-listener --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg
```
If `--rgb/--nir` are omitted, paths from the YAML config are used.

### Irrigation controller
Listens for MQTT commands `{"parcel_id": "...", "liters": 100}` on the topic configured as `mqtt.topics.irrigation_command`. Converts liters to open duration using each valve's `flow_lpm` and actuates the GPIO pin.
```bash
python -m raspberry.main --config raspberry/config/default_config.yaml irrigation --dry-run
```
- Omit `--dry-run` on the real Pi to drive `RPi.GPIO`.
- Periodic status is published to `mqtt.topics.irrigation_status`.

## MQTT topic contract
- `agriculture/drone/analysis`: `{ timestamp, telemetry, ndvi: {mean,min,max,stress_ratio} }`
- `agriculture/drone/telemetry`: `{ timestamp, telemetry }`
- `agriculture/irrigation/command`: inbound `{ parcel_id, liters }`
- `agriculture/irrigation/status`: `{ timestamp, valves: {id: {is_open, last_opened_at, last_closed_at}} }`

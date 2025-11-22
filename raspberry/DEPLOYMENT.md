# Deploying on the Raspberry Pi (field notes)

This is a straight, Pi-focused checklist—no fluff. Edit your config, run the scripts, and let ArduPilot handle the flying.

## 1) Configure on the Pi
```bash
cp raspberry/config/default_config.yaml /home/pi/agri-config.yaml
nano /home/pi/agri-config.yaml
```
Set these in the YAML:
- MQTT: `mqtt.broker`, `mqtt.port`, credentials; add `mqtt.tls: true` and `mqtt.cafile` if your broker is TLS.
- ArduPilot link: `drone.autopilot_connection` (e.g. `udp:0.0.0.0:14550` from Navio2).
- Captures: `drone.camera.rgb_path` / `nir_path` to match where you save images.
- Valves: `irrigation.valves[*].gpio_pin` and `flow_lpm`; adjust `max_parallel_valves` to protect your pump.

## 2) Capture RGB + NIR (example)
If you’re using Picamera2, save paired images like this (adapt camera indexes to your hardware):
```python
# save_rgb_nir.py
from picamera2 import Picamera2
from libcamera import Transform

pi = Picamera2()
pi.configure(pi.create_still_configuration(transform=Transform(hflip=1)))
pi.start()
pi.capture_file("/home/pi/data/captures/rgb.jpg")
# For a second NIR camera, repeat with Picamera2(1) and save nir.jpg
pi.close()
```
Run it:
```bash
python save_rgb_nir.py
```

## 3) Run NDVI on-demand
```bash
python -m raspberry.main --config /home/pi/agri-config.yaml \
  drone-cycle --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg
```
Publishes `{timestamp, telemetry, ndvi}` to the MQTT analysis topic.

## 4) Run NDVI on waypoint arrival
```bash
python -m raspberry.main --config /home/pi/agri-config.yaml \
  drone-waypoint-listener --rgb /home/pi/data/captures/rgb.jpg --nir /home/pi/data/captures/nir.jpg
```
Process stays up, listens for `MISSION_ITEM_REACHED`, runs NDVI each time.

## 5) Irrigation controller
Dry-run first:
```bash
python -m raspberry.main --config /home/pi/agri-config.yaml irrigation --dry-run
```
Send a test MQTT command to the irrigation command topic:
```json
{"parcel_id": "parcel-1", "liters": 50}
```
When wiring is confirmed, drop `--dry-run` to drive GPIO relays.

## 6) Keep it running with systemd (optional)
Example unit for the waypoint listener:
```
[Unit]
Description=Agri Drone NDVI Waypoint Listener
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/Desktop/levelUp/agriculture_monitoring
ExecStart=/usr/bin/python -m raspberry.main --config /home/pi/agri-config.yaml drone-waypoint-listener
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
Save to `/etc/systemd/system/agri-drone.service`, then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now agri-drone.service
```
Make a similar unit for irrigation if you want it persistent.

## 7) Quick checklist
- `pip install -r raspberry/requirements.txt` (on the Pi/virtualenv).
- YAML updated: broker, TLS, camera paths, Navio2 endpoint.
- RGB/NIR files present at the configured paths.
- MQTT topics reachable from the Pi.
- Valve pins/flow set; dry-run OK; hardware run tested.
- (Optional) systemd units enabled.

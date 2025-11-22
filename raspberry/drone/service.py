import json
import logging
import pathlib
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from ..utils.mqtt_client import MQTTClient
from .analysis import run_ndvi_pipeline
from .autopilot import AutopilotClient


class DroneService:
    def __init__(
        self,
        config: dict,
        mqtt_client: MQTTClient,
        autopilot: AutopilotClient,
    ):
        self.config = config
        self.mqtt = mqtt_client
        self.autopilot = autopilot
        self.topics = config["mqtt"]["topics"]
        self.drone_cfg = config["drone"]

    def run_capture_and_publish(self, rgb_path: str, nir_path: str):
        resize = (
            int(self.drone_cfg["camera"]["width"]),
            int(self.drone_cfg["camera"]["height"]),
        )
        ndvi_summary = run_ndvi_pipeline(
            pathlib.Path(rgb_path),
            pathlib.Path(nir_path),
            resize=resize,
            stress_threshold=float(self.drone_cfg["ndvi"]["stress_threshold"]),
        )
        telemetry = self.autopilot.read_telemetry()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry": telemetry,
            "ndvi": ndvi_summary,
        }
        logging.info("Publishing NDVI analysis to %s", self.topics["analysis"])
        self.mqtt.publish(self.topics["analysis"], payload)
        logging.debug("Payload: %s", json.dumps(payload, indent=2))

    def publish_telemetry_only(self):
        telemetry = self.autopilot.read_telemetry()
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "telemetry": telemetry}
        logging.info("Publishing telemetry to %s", self.topics["telemetry"])
        self.mqtt.publish(self.topics["telemetry"], payload)

    def start_waypoint_ndvi_listener(self, rgb_path: Optional[str] = None, nir_path: Optional[str] = None):
        """
        Register a waypoint-reached handler that triggers NDVI processing.
        Uses config camera paths if none are provided.
        """
        rgb = rgb_path or self.drone_cfg["camera"]["rgb_path"]
        nir = nir_path or self.drone_cfg["camera"]["nir_path"]

        def _handle(seq: Optional[int]):
            logging.info("Triggering NDVI capture on waypoint seq=%s", seq)
            # Offload heavy work to avoid blocking autopilot callback thread.
            threading.Thread(target=self.run_capture_and_publish, args=(rgb, nir), daemon=True).start()

        registered = self.autopilot.add_waypoint_reached_handler(_handle)
        if not registered:
            logging.error("Waypoint listener not started because autopilot is disconnected.")
            return

        logging.info("Waiting for waypoint events to trigger NDVI (RGB=%s, NIR=%s)...", rgb, nir)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopping waypoint NDVI listener...")

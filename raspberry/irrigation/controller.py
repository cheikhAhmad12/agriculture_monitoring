import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from ..utils.gpio import GPIOAdapter, Valve, load_valves
from ..utils.mqtt_client import MQTTClient


class IrrigationController:
    def __init__(self, config: dict, mqtt_client: MQTTClient, gpio: GPIOAdapter):
        self.config = config
        self.topics = config["mqtt"]["topics"]
        self.valves: Dict[str, Valve] = load_valves(config["irrigation"]["valves"])
        self.gpio = gpio
        self.mqtt = mqtt_client
        self._active_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        for valve in self.valves.values():
            self.gpio.setup_output(valve.gpio_pin)

    def _publish_status(self):
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "valves": {
                valve_id: {
                    "is_open": valve._is_open,
                    "last_opened_at": valve._last_opened_at,
                    "last_closed_at": valve._last_closed_at,
                }
                for valve_id, valve in self.valves.items()
            },
        }
        logging.debug("Publishing valve status to %s", self.topics["irrigation_status"])
        self.mqtt.publish(self.topics["irrigation_status"], status, retain=False)

    def _run_valve(self, valve: Valve, seconds: float):
        try:
            valve.open_for_seconds(self.gpio, seconds)
        finally:
            with self._lock:
                self._active_threads.pop(valve.valve_id, None)
            self._publish_status()

    def _start_valve_thread(self, valve: Valve, seconds: float):
        with self._lock:
            if len(self._active_threads) >= int(self.config["irrigation"]["max_parallel_valves"]):
                logging.warning("Reached max_parallel_valves. Ignoring request for %s", valve.valve_id)
                return
            if valve.valve_id in self._active_threads:
                logging.info("Valve %s already active; skipping duplicate command.", valve.valve_id)
                return
            thread = threading.Thread(target=self._run_valve, args=(valve, seconds), daemon=True)
            self._active_threads[valve.valve_id] = thread
            thread.start()
            logging.info("Started irrigation thread for %s (%.1fs)", valve.valve_id, seconds)

    def _handle_command(self, payload: dict):
        try:
            valve_id = payload["parcel_id"]
            liters = float(payload["liters"])
        except (KeyError, ValueError, TypeError):
            logging.error("Invalid irrigation command payload: %s", payload)
            return
        valve: Optional[Valve] = self.valves.get(str(valve_id))
        if not valve:
            logging.error("Unknown valve/parcel id %s", valve_id)
            return
        seconds = (liters / valve.flow_lpm) * 60.0
        logging.info(
            "Received irrigation command parcel=%s liters=%.2f -> duration=%.1fs",
            valve_id,
            liters,
            seconds,
        )
        self._start_valve_thread(valve, seconds)

    def _status_loop(self):
        interval = float(self.config["irrigation"]["publish_interval_seconds"])
        while True:
            self._publish_status()
            time.sleep(interval)

    def start(self):
        self.mqtt.subscribe(self.topics["irrigation_command"], self._handle_command)
        self.mqtt.loop_start()
        status_thread = threading.Thread(target=self._status_loop, daemon=True)
        status_thread.start()
        logging.info("Irrigation controller started. Awaiting MQTT commands on %s", self.topics["irrigation_command"])
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopping irrigation controller...")

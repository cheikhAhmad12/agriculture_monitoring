import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional


class GPIOUnavailable(Exception):
    pass


class GPIOAdapter:
    """Wrapper so code runs both on Raspberry Pi and on dev machines."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._gpio = None
        if dry_run:
            logging.info("GPIO running in dry-run mode.")
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as exc:  # pragma: no cover - hardware specific
            logging.warning("RPi.GPIO not available (%s), switching to dry-run.", exc)
            self.dry_run = True
            return

        self._gpio = GPIO
        self._gpio.setmode(GPIO.BCM)
        self._gpio.setwarnings(False)

    def setup_output(self, pin: int):
        if self.dry_run:
            logging.debug("Dry-run: setup_output(%s)", pin)
            return
        if not self._gpio:
            raise GPIOUnavailable("GPIO backend not initialized")
        self._gpio.setup(pin, self._gpio.OUT)

    def write(self, pin: int, value: bool):
        if self.dry_run:
            logging.debug("Dry-run: write pin=%s value=%s", pin, value)
            return
        if not self._gpio:
            raise GPIOUnavailable("GPIO backend not initialized")
        self._gpio.output(pin, self._gpio.HIGH if value else self._gpio.LOW)

    def cleanup(self):
        if self.dry_run:
            return
        if self._gpio:
            self._gpio.cleanup()


@dataclass
class Valve:
    valve_id: str
    gpio_pin: int
    flow_lpm: float  # liters per minute
    _is_open: bool = False
    _last_opened_at: Optional[float] = None
    _last_closed_at: Optional[float] = None

    def open_for_seconds(self, gpio: GPIOAdapter, seconds: float):
        logging.info("Opening valve %s on pin %s for %.1fs", self.valve_id, self.gpio_pin, seconds)
        gpio.write(self.gpio_pin, True)
        self._is_open = True
        self._last_opened_at = time.time()
        time.sleep(max(0.0, seconds))
        gpio.write(self.gpio_pin, False)
        self._is_open = False
        self._last_closed_at = time.time()
        logging.info("Closed valve %s", self.valve_id)


def load_valves(raw_valves: list) -> Dict[str, Valve]:
    valves: Dict[str, Valve] = {}
    for entry in raw_valves:
        valve = Valve(
            valve_id=str(entry["id"]),
            gpio_pin=int(entry["gpio_pin"]),
            flow_lpm=float(entry["flow_lpm"]),
        )
        valves[valve.valve_id] = valve
    return valves

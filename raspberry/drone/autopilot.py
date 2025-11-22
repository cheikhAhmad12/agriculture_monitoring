import logging
from typing import Optional, Callable


class AutopilotClient:
    """Thin wrapper on top of dronekit so code can run off-hardware."""

    def __init__(self, connection_string: str, wait_ready: bool = False):
        self.connection_string = connection_string
        self._vehicle = None
        self._waypoint_listener = None
        try:
            from dronekit import connect  # type: ignore
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.warning("dronekit not installed or unavailable (%s); telemetry will be mocked.", exc)
            return
        try:
            self._vehicle = connect(connection_string, wait_ready=wait_ready, timeout=10)
            logging.info("Connected to autopilot on %s", connection_string)
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.error("Failed to connect to autopilot on %s: %s", connection_string, exc)
            self._vehicle = None
        if self._vehicle:
            logging.debug("Autopilot connected, listeners can be registered.")

    def read_telemetry(self) -> dict:
        """Return a small telemetry snapshot."""
        if not self._vehicle:
            return {"status": "disconnected"}
        v = self._vehicle
        try:
            return {
                "status": "ok",
                "lat": getattr(getattr(v, "location", None), "global_relative_frame", getattr(v, "location", None)).lat
                if getattr(v, "location", None)
                else None,
                "lon": getattr(getattr(v, "location", None), "global_relative_frame", getattr(v, "location", None)).lon
                if getattr(v, "location", None)
                else None,
                "alt": getattr(getattr(v, "location", None), "global_relative_frame", getattr(v, "location", None)).alt
                if getattr(v, "location", None)
                else None,
                "groundspeed": getattr(v, "groundspeed", None),
                "airspeed": getattr(v, "airspeed", None),
                "battery": getattr(getattr(v, "battery", None), "level", None),
                "heading": getattr(v, "heading", None),
                "mode": str(getattr(v, "mode", "")),
            }
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.error("Error reading telemetry: %s", exc)
            return {"status": "error", "error": str(exc)}

    def close(self):
        if self._vehicle:
            try:
                self._vehicle.close()
            except Exception:
                pass

    def add_waypoint_reached_handler(self, handler: Callable[[Optional[int]], None]) -> bool:
        """
        Register a callback for MISSION_ITEM_REACHED messages.
        Handler receives the reached mission item seq (int or None).
        Returns True if registration succeeded, False otherwise.
        """
        if not self._vehicle:
            logging.warning("Cannot register waypoint handler: autopilot not connected.")
            return False

        def _listener(vehicle, name, message):  # pragma: no cover - hardware dependent
            seq = getattr(message, "seq", None)
            logging.info("Waypoint reached (seq=%s)", seq)
            try:
                handler(seq)
            except Exception as exc:
                logging.error("Error in waypoint handler: %s", exc)

        try:
            self._vehicle.add_message_listener("MISSION_ITEM_REACHED", _listener)
            self._waypoint_listener = _listener
            logging.info("Waypoint reached handler registered.")
            return True
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.error("Failed to register waypoint handler: %s", exc)
            return False

import argparse
import logging
import pathlib

from .drone.autopilot import AutopilotClient
from .drone.service import DroneService
from .irrigation.controller import IrrigationController
from .utils.config_loader import ConfigLoader
from .utils.gpio import GPIOAdapter
from .utils.mqtt_client import MQTTClient, MQTTSettings


def _build_mqtt(cfg: dict, client_id_suffix: str = "") -> MQTTClient:
    mqtt_cfg = cfg["mqtt"]
    client_id = mqtt_cfg.get("client_id", "agriculture-drone")
    if client_id_suffix:
        client_id = f"{client_id}-{client_id_suffix}"
    settings = MQTTSettings(
        broker=mqtt_cfg["broker"],
        port=int(mqtt_cfg.get("port", 1883)),
        username=mqtt_cfg.get("username", ""),
        password=mqtt_cfg.get("password", ""),
        client_id=client_id,
        keepalive=int(mqtt_cfg.get("keepalive", 60)),
        tls=bool(mqtt_cfg.get("tls", False)),
        cafile=mqtt_cfg.get("cafile"),
    )
    return MQTTClient(settings)


def run_drone(args):
    cfg = ConfigLoader(args.config).data
    mqtt_client = _build_mqtt(cfg, client_id_suffix="drone")
    mqtt_client.loop_start()
    autopilot = AutopilotClient(cfg["drone"]["autopilot_connection"], wait_ready=False)
    service = DroneService(cfg, mqtt_client, autopilot)
    service.run_capture_and_publish(args.rgb, args.nir)


def run_drone_waypoint_listener(args):
    cfg = ConfigLoader(args.config).data
    mqtt_client = _build_mqtt(cfg, client_id_suffix="drone")
    mqtt_client.loop_start()
    autopilot = AutopilotClient(cfg["drone"]["autopilot_connection"], wait_ready=False)
    service = DroneService(cfg, mqtt_client, autopilot)
    service.start_waypoint_ndvi_listener(rgb_path=args.rgb, nir_path=args.nir)


def run_irrigation(args):
    cfg = ConfigLoader(args.config).data
    mqtt_client = _build_mqtt(cfg, client_id_suffix="irrigation")
    gpio = GPIOAdapter(dry_run=args.dry_run)
    controller = IrrigationController(cfg, mqtt_client, gpio)
    controller.start()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raspberry Pi services for the agriculture monitoring project.")
    parser.add_argument(
        "--config",
        default=pathlib.Path(__file__).parent / "config" / "default_config.yaml",
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG, INFO, WARNING...).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    drone = sub.add_parser("drone-cycle", help="Process RGB/NIR capture, compute NDVI, and publish over MQTT.")
    drone.add_argument("--rgb", required=True, help="Path to RGB image capture.")
    drone.add_argument("--nir", required=True, help="Path to NIR image capture.")
    drone.set_defaults(func=run_drone)

    drone_wp = sub.add_parser(
        "drone-waypoint-listener",
        help="Listen for ArduPilot waypoint reached events and trigger NDVI publish automatically.",
    )
    drone_wp.add_argument("--rgb", help="Path to RGB image capture (defaults to config camera.rgb_path).")
    drone_wp.add_argument("--nir", help="Path to NIR image capture (defaults to config camera.nir_path).")
    drone_wp.set_defaults(func=run_drone_waypoint_listener)

    irr = sub.add_parser("irrigation", help="Start irrigation controller and listen for MQTT commands.")
    irr.add_argument("--dry-run", action="store_true", help="Skip real GPIO writes (for dev/test).")
    irr.set_defaults(func=run_irrigation)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()

import json
import logging
import ssl
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import paho.mqtt.client as mqtt


MessageHandler = Callable[[dict], None]


@dataclass
class MQTTSettings:
    broker: str
    port: int
    username: str
    password: str
    client_id: str
    keepalive: int
    tls: bool = False
    cafile: Optional[str] = None


class MQTTClient:
    """Minimal MQTT wrapper with JSON payloads."""

    def __init__(self, settings: MQTTSettings):
        self.settings = settings
        self._client = mqtt.Client(client_id=settings.client_id, clean_session=True)
        if settings.username:
            self._client.username_pw_set(settings.username, settings.password)
        if settings.tls:
            self._client.tls_set(ca_certs=settings.cafile, cert_reqs=ssl.CERT_REQUIRED)
        self._message_handler: Optional[MessageHandler] = None
        self._connected_event = threading.Event()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("MQTT connected to %s:%s", self.settings.broker, self.settings.port)
            self._connected_event.set()
        else:
            logging.error("MQTT connection failed (rc=%s)", rc)

    def _on_message(self, client, userdata, msg):
        if not self._message_handler:
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            logging.warning("MQTT: discarded non-JSON payload on %s", msg.topic)
            return
        self._message_handler(payload)

    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False):
        if not self._connected_event.is_set():
            logging.debug("MQTT publish waited for connection...")
            self._connected_event.wait(timeout=5)
        logging.debug("MQTT publishing to %s: %s", topic, payload)
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def subscribe(self, topic: str, handler: MessageHandler, qos: int = 0):
        self._message_handler = handler
        self._client.subscribe(topic, qos=qos)

    def loop_start(self):
        self._client.connect(self.settings.broker, self.settings.port, self.settings.keepalive)
        self._client.loop_start()

    def loop_forever(self):
        self._client.connect(self.settings.broker, self.settings.port, self.settings.keepalive)
        self._client.loop_forever()

    def disconnect(self):
        self._client.disconnect()

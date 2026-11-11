"""КлимаКлас шлюз за Raspberry Pi.

Сензорите в училището пращат измервания по MQTT към локалния Mosquitto брокер.
Шлюзът ги записва в локална SQLite опашка и ги препраща към облачния API.
Ако интернетът спре, нищо не се губи – данните чакат в опашката и се изпращат после.

    KK_API_URL=https://klimaklas.example.bg python gateway.py
"""

import json
import logging
import os
import signal
import sqlite3
import threading
import time
from collections import defaultdict

import httpx
import paho.mqtt.client as mqtt

API_URL = os.environ.get("KK_API_URL", "http://localhost:8000").rstrip("/")
MQTT_HOST = os.environ.get("KK_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("KK_MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("KK_MQTT_USER", "")
MQTT_PASSWORD = os.environ.get("KK_MQTT_PASSWORD", "")
DB_PATH = os.environ.get("KK_QUEUE_DB", "queue.db")
TOPIC = "klimaklas/+/reading"
BATCH = 200
ALLOWED_KEYS = {"co2", "temperature", "humidity", "measured_at"}

log = logging.getLogger("gateway")
stop = threading.Event()


class Queue:
    """Устойчива опашка в SQLite – оцелява рестарт на Raspberry Pi."""

    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, token TEXT NOT NULL, body TEXT NOT NULL)"
        )
        self.conn.commit()

    def push(self, token: str, reading: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT INTO queue (token, body) VALUES (?, ?)", (token, json.dumps(reading)))
            self.conn.commit()

    def peek(self, limit: int) -> list[tuple[int, str, dict]]:
        with self.lock:
            rows = self.conn.execute("SELECT id, token, body FROM queue ORDER BY id LIMIT ?", (limit,)).fetchall()
        return [(i, t, json.loads(b)) for i, t, b in rows]

    def delete(self, ids: list[int]) -> None:
        with self.lock:
            self.conn.executemany("DELETE FROM queue WHERE id = ?", [(i,) for i in ids])
            self.conn.commit()

    def size(self) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]


def on_message(queue: Queue):
    def handler(_client, _userdata, msg):
        try:
            data = json.loads(msg.payload)
            token = str(data.pop("token"))
            reading = {k: v for k, v in data.items() if k in ALLOWED_KEYS}
            if "measured_at" not in reading:
                # Слагаме време тук, за да е вярно, дори ако изпратим след часове
                reading["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            queue.push(token, reading)
            log.info("%s → %s ppm (в опашката: %d)", msg.topic, reading.get("co2"), queue.size())
        except (ValueError, KeyError, TypeError):
            log.warning("Невалидно съобщение на %s", msg.topic)

    return handler


def forward_once(queue: Queue, http: httpx.Client) -> bool:
    """Изпраща една порция. Връща True, ако има още за пращане веднага."""
    rows = queue.peek(BATCH)
    if not rows:
        return False
    by_token: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for row_id, token, reading in rows:
        by_token[token].append((row_id, reading))

    for token, items in by_token.items():
        ids = [i for i, _ in items]
        r = http.post(
            f"{API_URL}/api/v1/readings/batch",
            json={"readings": [rd for _, rd in items]},
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 201:
            queue.delete(ids)
            log.info("Препратени %d измервания", len(ids))
        elif r.status_code in (401, 422):
            queue.delete(ids)  # невалиден токен/данни – повторението няма да помогне
            log.error("API отказа %d измервания: %s %s", len(ids), r.status_code, r.text[:200])
        else:
            r.raise_for_status()
            raise httpx.HTTPError(f"Неочакван отговор {r.status_code}")
    return len(rows) == BATCH


def forwarder(queue: Queue) -> None:
    delay = 2
    with httpx.Client(timeout=15) as http:
        while not stop.is_set():
            try:
                more = forward_once(queue, http)
                delay = 2
                if not more:
                    stop.wait(5)
            except httpx.HTTPError as exc:
                log.warning("Няма връзка с API (%s). Нов опит след %d s. В опашката: %d", exc, delay, queue.size())
                stop.wait(delay)
                delay = min(delay * 2, 300)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    queue = Queue(DB_PATH)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="klimaklas-gateway")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = lambda c, *_: c.subscribe(TOPIC, qos=1)
    client.on_message = on_message(queue)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    log.info("Шлюзът работи: MQTT %s:%d → %s", MQTT_HOST, MQTT_PORT, API_URL)
    try:
        forwarder(queue)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        client.loop_stop()


if __name__ == "__main__":
    main()

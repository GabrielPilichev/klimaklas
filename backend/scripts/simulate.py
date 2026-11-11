"""Симулира сензорите от демо училището – за демонстрация без хардуер.

    python scripts/simulate.py                         # всички стаи, всяка минута
    python scripts/simulate.py --interval 5 --spike 214  # бързо + стая 214 „се задушава“

Токените се четат от .demo-devices.json (създава се от `python -m app.seed`).
"""

import argparse
import json
import random
import time
from pathlib import Path

import httpx


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8000", help="адрес на API сървъра")
    p.add_argument("--devices", default=".demo-devices.json")
    p.add_argument("--interval", type=float, default=60, help="секунди между измерванията")
    p.add_argument("--spike", action="append", default=[], help="стая, в която CO2 расте бързо (демо)")
    args = p.parse_args()

    devices = json.loads(Path(args.devices).read_text())
    co2 = {name: random.uniform(550, 900) for name in devices}
    print(f"Симулирам {len(devices)} сензора към {args.url} на всеки {args.interval} s. Ctrl+C за край.")
    with httpx.Client(base_url=args.url, timeout=10) as client:
        while True:
            for name, dev in devices.items():
                if name in args.spike:
                    co2[name] = min(2400, co2[name] + random.uniform(60, 140))
                else:
                    co2[name] += random.uniform(-40, 45)
                    co2[name] = min(1150, max(450, co2[name]))
                body = {
                    "co2": round(co2[name]),
                    "temperature": round(random.uniform(21, 24), 1),
                    "humidity": round(random.uniform(35, 50), 1),
                }
                try:
                    r = client.post("/api/v1/readings", json=body, headers={"Authorization": f"Bearer {dev['token']}"})
                    print(f"стая {name}: {body['co2']} ppm → {r.status_code}")
                except httpx.HTTPError as exc:
                    print(f"стая {name}: грешка {exc}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

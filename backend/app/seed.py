"""Демо училище с една седмица реалистични данни и тестови акаунти за трите роли.

python -m app.seed            # създава данните, ако базата е празна
python -m app.seed --reset    # изтрива всичко и започва отначало
"""

import argparse
import json
import math
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select

from . import db as dbmod
from .config import settings
from .db import Base, SessionLocal, create_tables
from .models import Alert, Device, Reading, Role, Room, School, User
from .security import hash_device_token, hash_password, new_device_token
from .timeutil import utcnow

DEMO_PASSWORD = os.environ.get("KK_DEMO_PASSWORD", "KlimaKlas-2026")
DEVICES_FILE = Path(os.environ.get("KK_DEMO_DEVICES_FILE", ".demo-devices.json"))

# (стая, етаж, ученици, вентилация: по-малко = по-лошо проветрена)
ROOMS = [
    ("101", 1, 26, 0.030),
    ("102", 1, 24, 0.022),
    ("103", 1, 28, 0.016),
    ("104", 1, 22, 0.035),
    ("211", 2, 27, 0.020),
    ("212", 2, 25, 0.028),
    ("213", 2, 29, 0.018),
    ("214", 2, 30, 0.012),
]

# Учебни часове (начало, продължителност в минути)
LESSONS = [(8, 0), (8, 50), (9, 40), (10, 50), (11, 40), (12, 30), (13, 20)]
LESSON_MIN = 40
OUTDOOR = 420.0


def _in_lesson(local: datetime, n_lessons: int) -> bool:
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    for h, m in LESSONS[:n_lessons]:
        start = h * 60 + m
        if start <= minutes < start + LESSON_MIN:
            return True
    return False


def generate_room_series(start: datetime, end: datetime, students: int, vent: float, rng: random.Random):
    """Опростен модел на масовия баланс: учениците добавят CO2, проветряването го сваля към външния."""
    tz = ZoneInfo(settings.timezone)
    co2 = OUTDOOR + 30
    t = start
    n_lessons = rng.choice([5, 6, 6, 7])
    while t <= end:
        local = t.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        if local.hour == 0 and local.minute == 0:
            n_lessons = rng.choice([5, 6, 6, 7])
        occupied = _in_lesson(local, n_lessons)
        school_hours = local.weekday() < 5 and 7 <= local.hour < 15
        if occupied:
            gen = 20.0 * students / 28
            air = vent
        elif school_hours:
            gen = 4.0 * students / 28  # междучасие – част от учениците остават
            air = vent * (4 if rng.random() < 0.55 else 1.2)  # понякога отварят прозореца
        else:
            gen, air = 0.0, 0.006
        co2 += gen - (co2 - OUTDOOR) * air + rng.gauss(0, 6)
        co2 = max(OUTDOOR - 15, co2)
        temp = 20.5 + (1.8 if occupied else 0) + 1.2 * math.sin((local.hour - 9) / 24 * 2 * math.pi)
        hum = 38 + (co2 - OUTDOOR) / 120 + rng.gauss(0, 0.8)
        yield t, int(round(co2)), round(temp + rng.gauss(0, 0.15), 1), round(min(95, max(15, hum)), 1)
        t += timedelta(minutes=1)


def reset() -> None:
    assert dbmod.engine is not None
    Base.metadata.drop_all(dbmod.engine)


def seed(days: int = 7, rng_seed: int = 2026) -> dict:
    create_tables()
    rng = random.Random(rng_seed)
    with SessionLocal() as db:
        if db.scalar(select(School.id).limit(1)) is not None:
            print("Базата вече има данни – пропускам. Използвайте --reset за ново начало.")
            return {}

        school = School(name="Демо училище „Джон Атанасов“", city="София")
        db.add(school)
        db.flush()

        rooms: dict[str, Room] = {}
        tokens: dict[str, dict] = {}
        for name, floor, students, _ in ROOMS:
            room = Room(school_id=school.id, name=name, floor=floor, capacity=students)
            db.add(room)
            db.flush()
            rooms[name] = room
            token = new_device_token()
            dev = Device(room_id=room.id, name=f"Сензор {name}", token_hash=hash_device_token(token))
            db.add(dev)
            db.flush()
            tokens[name] = {"device_id": dev.id, "room_id": room.id, "token": token}

        pw = hash_password(DEMO_PASSWORD)
        db.add_all(
            [
                User(email="admin@klimaklas.test", full_name="Администратор Демо", password_hash=pw, role=Role.admin),
                User(
                    email="direktor@klimaklas.test",
                    full_name="Директор Демо",
                    password_hash=pw,
                    role=Role.director,
                    school_id=school.id,
                ),
                User(
                    email="uchitel@klimaklas.test",
                    full_name="Учител Демо",
                    password_hash=pw,
                    role=Role.teacher,
                    school_id=school.id,
                    rooms=[rooms["214"], rooms["101"]],
                ),
            ]
        )
        db.commit()

        end = utcnow().replace(second=0, microsecond=0)
        start = end - timedelta(days=days)
        alert_after = timedelta(seconds=settings.alert_after_seconds)
        for name, _, students, vent in ROOMS:
            room = rooms[name]
            dev_id = tokens[name]["device_id"]
            batch: list[dict] = []
            high_since: datetime | None = None
            alert: Alert | None = None
            for t, co2, temp, hum in generate_room_series(start, end, students, vent, rng):
                batch.append(
                    dict(room_id=room.id, device_id=dev_id, co2=co2, temperature=temp, humidity=hum, measured_at=t)
                )
                # Същото правило като в services.process_alert_rule, но в паметта (по-бързо).
                if co2 > settings.co2_alert:
                    high_since = high_since or t
                    if alert is None and t - high_since >= alert_after:
                        alert = Alert(
                            room_id=room.id, started_at=high_since, triggered_at=t, max_co2=co2, notified=True
                        )
                        db.add(alert)
                    elif alert is not None:
                        alert.max_co2 = max(alert.max_co2, co2)
                else:
                    high_since = None
                    if alert is not None:
                        alert.resolved_at = t
                        if rng.random() < 0.7:
                            alert.acknowledged_at = alert.triggered_at + timedelta(minutes=rng.randint(1, 6))
                        alert = None
                if len(batch) >= 5000:
                    db.execute(insert(Reading), batch)
                    batch.clear()
            if batch:
                db.execute(insert(Reading), batch)
            room.high_since = high_since
        db.commit()

    DEVICES_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2))
    print(f"Готово: {len(ROOMS)} стаи, {days} дни данни.")
    print(f"Токените на устройствата са записани в {DEVICES_FILE} (не го качвайте в Git).")
    print("Тестови акаунти (парола: KK_DEMO_PASSWORD или KlimaKlas-2026):")
    print("  admin@klimaklas.test · direktor@klimaklas.test · uchitel@klimaklas.test")
    return tokens


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="изтрий всички таблици преди това")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    if args.reset:
        reset()
    seed(days=args.days)

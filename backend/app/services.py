"""Бизнес логика: статус на стая, известия при висок CO2, обобщения."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Alert, Reading, Room
from .schemas import ReadingOut, RoomOut, Status
from .timeutil import utcnow


def co2_status(co2: int) -> Status:
    if co2 < settings.co2_warn:
        return "green"
    if co2 <= settings.co2_alert:
        return "yellow"
    return "red"


def latest_reading(db: Session, room_id: int) -> Reading | None:
    return db.scalar(select(Reading).where(Reading.room_id == room_id).order_by(Reading.measured_at.desc()).limit(1))


def active_alert(db: Session, room_id: int) -> Alert | None:
    return db.scalar(
        select(Alert)
        .where(Alert.room_id == room_id, Alert.resolved_at.is_(None))
        .order_by(Alert.started_at.desc())
        .limit(1)
    )


def room_out(db: Session, room: Room, now: datetime | None = None) -> RoomOut:
    now = now or utcnow()
    latest = latest_reading(db, room.id)
    if latest is None or (now - latest.measured_at).total_seconds() > settings.offline_after_seconds:
        status: Status = "offline"
    else:
        status = co2_status(latest.co2)
    return RoomOut(
        id=room.id,
        school_id=room.school_id,
        name=room.name,
        floor=room.floor,
        capacity=room.capacity,
        status=status,
        latest=ReadingOut.model_validate(latest) if latest else None,
        alert_active=active_alert(db, room.id) is not None,
    )


def process_alert_rule(db: Session, room: Room, co2: int, at: datetime) -> Alert | None:
    """Правило: CO2 над прага непрекъснато повече от N секунди → известие.
    Връща новосъздадения Alert (ако има), за да може да се изпрати известие."""
    current = active_alert(db, room.id)

    if co2 <= settings.co2_alert:
        room.high_since = None
        if current is not None:
            current.resolved_at = at
        return None

    if room.high_since is None or at < room.high_since:
        room.high_since = at
    if current is not None:
        current.max_co2 = max(current.max_co2, co2)
        return None

    if (at - room.high_since) >= timedelta(seconds=settings.alert_after_seconds):
        alert = Alert(room_id=room.id, started_at=room.high_since, triggered_at=at, max_co2=co2)
        db.add(alert)
        db.flush()
        return alert
    return None


def downsample(points: list[Reading], max_points: int) -> list[ReadingOut]:
    """Усреднява съседни точки, ако са твърде много за графиката."""
    if len(points) <= max_points:
        return [ReadingOut.model_validate(p) for p in points]
    size = -(-len(points) // max_points)  # ceil
    out: list[ReadingOut] = []
    for i in range(0, len(points), size):
        chunk = points[i : i + size]
        temps = [p.temperature for p in chunk if p.temperature is not None]
        hums = [p.humidity for p in chunk if p.humidity is not None]
        out.append(
            ReadingOut(
                co2=round(sum(p.co2 for p in chunk) / len(chunk)),
                temperature=round(sum(temps) / len(temps), 1) if temps else None,
                humidity=round(sum(hums) / len(hums), 1) if hums else None,
                measured_at=chunk[len(chunk) // 2].measured_at,
            )
        )
    return out


def csv_safe(value: object) -> str:
    """Предпазва от CSV/формула инжекция при отваряне в Excel."""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s

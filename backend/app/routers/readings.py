"""Приемане на измервания от сензорните възли (или от Raspberry Pi шлюза)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_device
from ..models import Alert, Device, Reading
from ..notify import send_alert_notifications
from ..ratelimit import RateLimiter
from ..realtime import manager
from ..schemas import IngestResult, ReadingBatchIn, ReadingIn, ReadingOut
from ..services import co2_status, process_alert_rule
from ..timeutil import iso_z, utcnow

router = APIRouter(prefix="/readings", tags=["readings"])
device_limiter = RateLimiter(settings.reading_rate_limit, 60)

# Известие се праща само за свежи данни (буферирани стари данни от шлюза не трябва да „звънят“).
NOTIFY_MAX_AGE_SECONDS = 15 * 60


async def _ingest(items: list[ReadingIn], device: Device, db: Session, tasks: BackgroundTasks) -> IngestResult:
    if not device_limiter.hit(str(device.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Твърде много заявки от устройството.")

    now = utcnow()
    room = device.room
    rows: list[Reading] = []
    new_alerts: list[Alert] = []
    for item in sorted(items, key=lambda r: r.measured_at or now):
        at = item.measured_at or now
        row = Reading(
            room_id=room.id,
            device_id=device.id,
            co2=item.co2,
            temperature=item.temperature,
            humidity=item.humidity,
            measured_at=at,
        )
        db.add(row)
        rows.append(row)
        alert = process_alert_rule(db, room, item.co2, at)
        if alert is not None:
            new_alerts.append(alert)

    device.last_seen_at = now
    db.commit()

    for alert in new_alerts:
        if (now - alert.triggered_at).total_seconds() <= NOTIFY_MAX_AGE_SECONDS:
            tasks.add_task(send_alert_notifications, alert.id)
        else:
            alert.notified = True
    db.commit()

    last = rows[-1]
    await manager.broadcast(
        room.id,
        room.school_id,
        {
            "type": "reading",
            "room_id": room.id,
            "status": co2_status(last.co2),
            "reading": ReadingOut.model_validate(last).model_dump(mode="json"),
        },
    )
    for alert in new_alerts:
        await manager.broadcast(
            room.id,
            room.school_id,
            {
                "type": "alert",
                "room_id": room.id,
                "room_name": room.name,
                "alert_id": alert.id,
                "co2": alert.max_co2,
                "started_at": iso_z(alert.started_at),
            },
        )
    return IngestResult(accepted=len(rows), room_id=room.id)


@router.post("", response_model=IngestResult, status_code=201)
async def post_reading(
    payload: ReadingIn,
    tasks: BackgroundTasks,
    device: Device = Depends(get_device),
    db: Session = Depends(get_db),
) -> IngestResult:
    return await _ingest([payload], device, db, tasks)


@router.post("/batch", response_model=IngestResult, status_code=201)
async def post_batch(
    payload: ReadingBatchIn,
    tasks: BackgroundTasks,
    device: Device = Depends(get_device),
    db: Session = Depends(get_db),
) -> IngestResult:
    return await _ingest(payload.readings, device, db, tasks)

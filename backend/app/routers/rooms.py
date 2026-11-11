import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, get_room_for_user, require_roles, visible_rooms_stmt
from ..models import Reading, Role, Room, School, User
from ..schemas import RoomIn, RoomOut, RoomSeries, RoomUpdate
from ..services import csv_safe, downsample, room_out
from ..timeutil import iso_z, to_naive_utc, utcnow

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _range(start: datetime | None, end: datetime | None, hours: int) -> tuple[datetime, datetime]:
    end_n = to_naive_utc(end) if end else utcnow()
    start_n = to_naive_utc(start) if start else end_n - timedelta(hours=hours)
    if start_n >= end_n:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Началото трябва да е преди края.")
    if end_n - start_n > timedelta(days=62):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Периодът е най-много 62 дни.")
    return start_n, end_n


@router.get("", response_model=list[RoomOut])
def list_rooms(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RoomOut]:
    now = utcnow()
    return [room_out(db, r, now) for r in db.scalars(visible_rooms_stmt(user))]


@router.post("", response_model=RoomOut, status_code=201)
def create_room(
    payload: RoomIn, _: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)
) -> RoomOut:
    if db.get(School, payload.school_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Училището не е намерено.")
    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    return room_out(db, room)


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RoomOut:
    return room_out(db, get_room_for_user(room_id, db, user))


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    _: User = Depends(require_roles(Role.admin)),
    db: Session = Depends(get_db),
) -> RoomOut:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стаята не е намерена.")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(room, key, value)
    db.commit()
    return room_out(db, room)


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: int, _: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)) -> None:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стаята не е намерена.")
    db.delete(room)
    db.commit()


@router.get("/{room_id}/readings", response_model=RoomSeries)
def room_readings(
    room_id: int,
    start: datetime | None = Query(None, alias="from"),
    end: datetime | None = Query(None, alias="to"),
    hours: int = Query(24, ge=1, le=24 * 62),
    max_points: int = Query(1500, ge=10, le=5000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoomSeries:
    room = get_room_for_user(room_id, db, user)
    start_n, end_n = _range(start, end, hours)
    rows = list(
        db.scalars(
            select(Reading)
            .where(Reading.room_id == room.id, Reading.measured_at >= start_n, Reading.measured_at <= end_n)
            .order_by(Reading.measured_at)
        )
    )
    return RoomSeries(room_id=room.id, points=downsample(rows, max_points))


@router.get("/{room_id}/export.csv")
def export_csv(
    room_id: int,
    start: datetime | None = Query(None, alias="from"),
    end: datetime | None = Query(None, alias="to"),
    hours: int = Query(24 * 7, ge=1, le=24 * 62),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    room = get_room_for_user(room_id, db, user)
    start_n, end_n = _range(start, end, hours)
    rows = db.execute(
        select(Reading.measured_at, Reading.co2, Reading.temperature, Reading.humidity)
        .where(Reading.room_id == room.id, Reading.measured_at >= start_n, Reading.measured_at <= end_n)
        .order_by(Reading.measured_at)
    )

    buf = io.StringIO()
    buf.write("﻿")  # BOM, за да покаже Excel кирилицата правилно
    writer = csv.writer(buf)
    writer.writerow(["стая", "време (UTC)", "CO2 (ppm)", "температура (°C)", "влажност (%)"])
    name = csv_safe(room.name)
    for measured_at, co2, temp, hum in rows:
        writer.writerow([name, iso_z(measured_at), co2, temp, hum])

    filename = f"klimaklas-room-{room.id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

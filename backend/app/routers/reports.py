"""Седмични отчети за директора (JSON или CSV)."""

import csv
import io
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import require_roles
from ..models import Alert, Reading, Role, Room, School, User
from ..schemas import WeeklyReport, WeeklyRoomReport
from ..services import csv_safe
from ..timeutil import to_naive_utc

router = APIRouter(prefix="/reports", tags=["reports"])
READING_INTERVAL_MINUTES = 1  # сензорите пращат веднъж в минута


def _week_bounds(week_start: date | None) -> tuple[date, datetime, datetime]:
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).date()
    monday = week_start or (today - timedelta(days=today.weekday()))
    start_local = datetime.combine(monday, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=7)
    return monday, to_naive_utc(start_local), to_naive_utc(end_local)


def build_weekly_report(db: Session, school: School, week_start: date | None) -> WeeklyReport:
    monday, start, end = _week_bounds(week_start)
    over = case((Reading.co2 > settings.co2_alert, 1), else_=0)
    stats = {
        row.room_id: row
        for row in db.execute(
            select(
                Reading.room_id,
                func.avg(Reading.co2).label("avg_co2"),
                func.max(Reading.co2).label("max_co2"),
                func.avg(Reading.temperature).label("avg_t"),
                func.avg(Reading.humidity).label("avg_h"),
                func.count(Reading.id).label("n"),
                func.sum(over).label("n_over"),
            )
            .join(Room, Room.id == Reading.room_id)
            .where(Room.school_id == school.id, Reading.measured_at >= start, Reading.measured_at < end)
            .group_by(Reading.room_id)
        )
    }
    alert_counts = dict(
        db.execute(
            select(Alert.room_id, func.count(Alert.id))
            .join(Room, Room.id == Alert.room_id)
            .where(Room.school_id == school.id, Alert.triggered_at >= start, Alert.triggered_at < end)
            .group_by(Alert.room_id)
        ).all()
    )

    rooms = []
    for room in db.scalars(select(Room).where(Room.school_id == school.id).order_by(Room.floor, Room.name)):
        s = stats.get(room.id)
        n = s.n if s else 0
        n_over = int(s.n_over or 0) if s else 0
        rooms.append(
            WeeklyRoomReport(
                room_id=room.id,
                room_name=room.name,
                avg_co2=round(float(s.avg_co2), 0) if s and s.avg_co2 is not None else None,
                max_co2=s.max_co2 if s else None,
                avg_temperature=round(float(s.avg_t), 1) if s and s.avg_t is not None else None,
                avg_humidity=round(float(s.avg_h), 1) if s and s.avg_h is not None else None,
                minutes_over_alert=n_over * READING_INTERVAL_MINUTES,
                percent_over_alert=round(100 * n_over / n, 1) if n else 0.0,
                alerts=alert_counts.get(room.id, 0),
            )
        )
    return WeeklyReport(
        school_id=school.id,
        school_name=school.name,
        week_start=monday.isoformat(),
        week_end=(monday + timedelta(days=6)).isoformat(),
        rooms=rooms,
    )


@router.get("/weekly", response_model=WeeklyReport)
def weekly(
    school_id: int | None = None,
    week_start: date | None = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user: User = Depends(require_roles(Role.admin, Role.director)),
    db: Session = Depends(get_db),
):
    if user.role == Role.director:
        if school_id is not None and school_id != user.school_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Училището не е намерено.")
        school_id = user.school_id
    if school_id is None:
        school_id = db.scalar(select(School.id).order_by(School.id).limit(1))
    school = db.get(School, school_id) if school_id is not None else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Училището не е намерено.")

    report = build_weekly_report(db, school, week_start)
    if format == "json":
        return report

    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow([csv_safe(f"Седмичен отчет: {report.school_name}"), report.week_start, report.week_end])
    w.writerow(
        [
            "стая",
            "среден CO2",
            "максимален CO2",
            "ср. температура",
            "ср. влажност",
            f"минути над {settings.co2_alert} ppm",
            "% от времето",
            "известия",
        ]
    )
    for r in report.rooms:
        w.writerow(
            [
                csv_safe(r.room_name),
                r.avg_co2,
                r.max_co2,
                r.avg_temperature,
                r.avg_humidity,
                r.minutes_over_alert,
                r.percent_over_alert,
                r.alerts,
            ]
        )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="klimaklas-weekly-{report.week_start}.csv"'},
    )

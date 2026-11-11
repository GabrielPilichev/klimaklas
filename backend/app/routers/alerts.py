from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import can_access_room, get_current_user, visible_rooms_stmt
from ..models import Alert, Room, User
from ..schemas import AlertOut
from ..timeutil import utcnow

router = APIRouter(prefix="/alerts", tags=["alerts"])


def alert_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        room_id=alert.room_id,
        room_name=alert.room.name,
        started_at=alert.started_at,
        triggered_at=alert.triggered_at,
        resolved_at=alert.resolved_at,
        acknowledged_at=alert.acknowledged_at,
        max_co2=alert.max_co2,
        active=alert.resolved_at is None,
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    room_ids = select(visible_rooms_stmt(user).subquery().c.id)
    stmt = select(Alert).where(Alert.room_id.in_(room_ids)).order_by(Alert.triggered_at.desc()).limit(limit)
    if active is True:
        stmt = stmt.where(Alert.resolved_at.is_(None))
    elif active is False:
        stmt = stmt.where(Alert.resolved_at.is_not(None))
    return [alert_out(a) for a in db.scalars(stmt)]


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AlertOut:
    """Учителят потвърждава, че е отворил прозореца."""
    alert = db.get(Alert, alert_id)
    room = db.get(Room, alert.room_id) if alert else None
    if alert is None or room is None or not can_access_room(user, room):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Известието не е намерено.")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by = user.id
        db.commit()
    return alert_out(alert)

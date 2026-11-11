from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Device, Role, Room, User, room_teachers
from .security import SESSION_COOKIE, decode_session_token, hash_device_token


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE) or _bearer(request)
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не сте влезли в системата.")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Нямате права за това действие.")
        return user

    return checker


def get_device(request: Request, db: Session = Depends(get_db)) -> Device:
    token = _bearer(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Липсва токен на устройството.")
    device = db.scalar(select(Device).where(Device.token_hash == hash_device_token(token)))
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалиден токен на устройството.")
    return device


# ---------- кой какво вижда ----------


def visible_rooms_stmt(user: User):
    stmt = select(Room).order_by(Room.floor, Room.name)
    if user.role == Role.admin:
        return stmt
    if user.role == Role.director:
        return stmt.where(Room.school_id == user.school_id)
    return stmt.join(room_teachers, room_teachers.c.room_id == Room.id).where(room_teachers.c.user_id == user.id)


def can_access_room(user: User, room: Room) -> bool:
    if user.role == Role.admin:
        return True
    if user.role == Role.director:
        return room.school_id == user.school_id
    return any(r.id == room.id for r in user.rooms)


def get_room_for_user(room_id: int, db: Session, user: User) -> Room:
    room = db.get(Room, room_id)
    # 404 и при липса на права – за да не издаваме кои стаи съществуват.
    if room is None or not can_access_room(user, room):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стаята не е намерена.")
    return room

"""Администрация: училища, устройства, потребители. Само за роля „администратор“."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Device, Role, Room, School, User
from ..schemas import DeviceCreated, DeviceIn, DeviceOut, SchoolIn, SchoolOut, UserIn, UserOut, UserRoomsIn
from ..security import hash_device_token, hash_password, new_device_token
from .auth import user_out

router = APIRouter(tags=["admin"])
admin_only = require_roles(Role.admin)


# ---------- училища ----------


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[School]:
    stmt = select(School).order_by(School.name)
    if user.role != Role.admin:
        stmt = stmt.where(School.id == user.school_id)
    return list(db.scalars(stmt))


@router.post("/schools", response_model=SchoolOut, status_code=201)
def create_school(payload: SchoolIn, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> School:
    school = School(**payload.model_dump())
    db.add(school)
    db.commit()
    return school


# ---------- устройства ----------


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(_: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.id)))


@router.post("/devices", response_model=DeviceCreated, status_code=201)
def create_device(payload: DeviceIn, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> DeviceCreated:
    if db.get(Room, payload.room_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стаята не е намерена.")
    token = new_device_token()
    device = Device(room_id=payload.room_id, name=payload.name, token_hash=hash_device_token(token))
    db.add(device)
    db.commit()
    return DeviceCreated(**DeviceOut.model_validate(device).model_dump(), token=token)


@router.post("/devices/{device_id}/rotate-token", response_model=DeviceCreated)
def rotate_token(device_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> DeviceCreated:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Устройството не е намерено.")
    token = new_device_token()
    device.token_hash = hash_device_token(token)
    db.commit()
    return DeviceCreated(**DeviceOut.model_validate(device).model_dump(), token=token)


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> None:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Устройството не е намерено.")
    db.delete(device)
    db.commit()


# ---------- потребители ----------


def _rooms_by_ids(db: Session, ids: list[int]) -> list[Room]:
    rooms = list(db.scalars(select(Room).where(Room.id.in_(ids)))) if ids else []
    if len(rooms) != len(set(ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Някоя от стаите не съществува.")
    return rooms


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[UserOut]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.role, User.full_name))]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserIn, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> UserOut:
    if payload.role != Role.admin and payload.school_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Директор и учител трябва да имат училище.")
    if payload.school_id is not None and db.get(School, payload.school_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Училището не е намерено.")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        school_id=payload.school_id,
        telegram_chat_id=payload.telegram_chat_id,
        rooms=_rooms_by_ids(db, payload.room_ids) if payload.role == Role.teacher else [],
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Потребител с този имейл вече съществува.") from None
    return user_out(user)


@router.put("/users/{user_id}/rooms", response_model=UserOut)
def set_user_rooms(
    user_id: int, payload: UserRoomsIn, _: User = Depends(admin_only), db: Session = Depends(get_db)
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Потребителят не е намерен.")
    if user.role != Role.teacher:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Стаи се задават само на учители.")
    user.rooms = _rooms_by_ids(db, payload.room_ids)
    db.commit()
    return user_out(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, me: User = Depends(admin_only), db: Session = Depends(get_db)) -> None:
    if user_id == me.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Не можете да изтриете себе си.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Потребителят не е намерен.")
    db.delete(user)
    db.commit()

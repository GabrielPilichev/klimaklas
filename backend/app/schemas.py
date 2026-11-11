import re
from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from .models import Role
from .timeutil import iso_z, to_naive_utc, utcnow

UTCDateTime = Annotated[datetime, PlainSerializer(iso_z, return_type=str)]

_FORBIDDEN_NAME_CHARS = re.compile(r"[<>\x00-\x1f\x7f]")
_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def _clean_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("не може да е празно")
    if _FORBIDDEN_NAME_CHARS.search(v):
        raise ValueError("съдържа непозволени символи")
    return v


def _clean_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("невалиден имейл")
    return v


Name = Annotated[str, Field(min_length=1, max_length=60), AfterValidator(_clean_name)]
LongName = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_clean_name)]
Email = Annotated[str, Field(min_length=3, max_length=254), AfterValidator(_clean_email)]

Status = Literal["green", "yellow", "red", "offline"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- auth ----------


class LoginIn(StrictModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=72)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    school_id: int | None
    room_ids: list[int] = []
    telegram_chat_id: str | None = None


# ---------- readings ----------


class ReadingIn(StrictModel):
    co2: int = Field(ge=0, le=10000)
    temperature: float | None = Field(default=None, ge=-40, le=85)
    humidity: float | None = Field(default=None, ge=0, le=100)
    measured_at: datetime | None = None

    @field_validator("measured_at")
    @classmethod
    def _check_time(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        v = to_naive_utc(v)
        now = utcnow()
        if v > now + timedelta(minutes=5):
            raise ValueError("времето е в бъдещето")
        if v < now - timedelta(days=7):
            raise ValueError("измерването е по-старо от 7 дни")
        return v


class ReadingBatchIn(StrictModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=500)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co2: int
    temperature: float | None
    humidity: float | None
    measured_at: UTCDateTime


class IngestResult(BaseModel):
    accepted: int
    room_id: int


# ---------- rooms ----------


class RoomOut(BaseModel):
    id: int
    school_id: int
    name: str
    floor: int
    capacity: int
    status: Status
    latest: ReadingOut | None
    alert_active: bool


class RoomIn(StrictModel):
    school_id: int
    name: Name
    floor: int = Field(default=1, ge=-2, le=20)
    capacity: int = Field(default=28, ge=1, le=200)


class RoomUpdate(StrictModel):
    name: Name | None = None
    floor: int | None = Field(default=None, ge=-2, le=20)
    capacity: int | None = Field(default=None, ge=1, le=200)


class RoomSeries(BaseModel):
    room_id: int
    points: list[ReadingOut]


# ---------- admin ----------


class SchoolIn(StrictModel):
    name: LongName
    city: Annotated[str, Field(max_length=80)] = ""


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str


class DeviceIn(StrictModel):
    room_id: int
    name: Name


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    created_at: UTCDateTime
    last_seen_at: UTCDateTime | None


class DeviceCreated(DeviceOut):
    token: str  # показва се само веднъж


class UserIn(StrictModel):
    email: Email
    full_name: LongName
    password: Annotated[str, Field(min_length=8, max_length=72)]
    role: Role
    school_id: int | None = None
    room_ids: list[int] = []
    telegram_chat_id: Annotated[str, Field(max_length=40, pattern=r"^-?\d+$")] | None = None


class UserRoomsIn(StrictModel):
    room_ids: list[int]


# ---------- alerts & reports ----------


class AlertOut(BaseModel):
    id: int
    room_id: int
    room_name: str
    started_at: UTCDateTime
    triggered_at: UTCDateTime
    resolved_at: UTCDateTime | None
    acknowledged_at: UTCDateTime | None
    max_co2: int
    active: bool


class WeeklyRoomReport(BaseModel):
    room_id: int
    room_name: str
    avg_co2: float | None
    max_co2: int | None
    avg_temperature: float | None
    avg_humidity: float | None
    minutes_over_alert: int
    percent_over_alert: float
    alerts: int


class WeeklyReport(BaseModel):
    school_id: int
    school_name: str
    week_start: str
    week_end: str
    rooms: list[WeeklyRoomReport]

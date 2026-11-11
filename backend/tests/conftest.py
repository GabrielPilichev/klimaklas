import os

os.environ["KK_DATABASE_URL"] = "sqlite://"
os.environ["KK_ENVIRONMENT"] = "test"
os.environ["KK_LOGIN_RATE_LIMIT"] = "5"
os.environ["KK_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import notify  # noqa: E402
from app.db import Base, SessionLocal, create_tables  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Device, Role, Room, School, User  # noqa: E402
from app.routers.auth import login_limiter  # noqa: E402
from app.routers.readings import device_limiter  # noqa: E402
from app.security import CSRF_COOKIE, hash_device_token, hash_password  # noqa: E402

PASSWORD = "TestPass-123"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(dbmod.engine)
    create_tables()
    login_limiter.reset()
    device_limiter.reset()
    notify.sent_messages.clear()
    yield


@pytest.fixture
def data():
    """Две училища; учителят има достъп само до стая 214."""
    with SessionLocal() as db:
        s1 = School(name="Училище 1", city="София")
        s2 = School(name="Училище 2", city="Пловдив")
        db.add_all([s1, s2])
        db.flush()
        r214 = Room(school_id=s1.id, name="214", floor=2)
        r101 = Room(school_id=s1.id, name="101", floor=1)
        other = Room(school_id=s2.id, name="305", floor=3)
        db.add_all([r214, r101, other])
        db.flush()
        pw = hash_password(PASSWORD)
        db.add_all(
            [
                User(email="admin@t.test", full_name="Admin", password_hash=pw, role=Role.admin),
                User(email="dir@t.test", full_name="Director", password_hash=pw, role=Role.director, school_id=s1.id),
                User(
                    email="teacher@t.test",
                    full_name="Teacher",
                    password_hash=pw,
                    role=Role.teacher,
                    school_id=s1.id,
                    rooms=[r214],
                ),
            ]
        )
        db.add(Device(room_id=r214.id, name="Сензор 214", token_hash=hash_device_token("kk_dev214")))
        db.add(Device(room_id=other.id, name="Сензор 305", token_hash=hash_device_token("kk_dev305")))
        db.commit()
        return {"school1": s1.id, "school2": s2.id, "r214": r214.id, "r101": r101.id, "other": other.id}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str = PASSWORD) -> TestClient:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies.get(CSRF_COOKIE)
    return client


def device_headers(token: str = "kk_dev214") -> dict:
    return {"Authorization": f"Bearer {token}"}

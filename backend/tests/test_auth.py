from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

from .conftest import PASSWORD, login


def test_login_success_sets_httponly_cookie(client, data):
    r = client.post("/api/v1/auth/login", json={"email": "Teacher@T.test ", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["role"] == "teacher"
    set_cookie = r.headers.get_list("set-cookie")
    session = next(c for c in set_cookie if c.startswith("kk_session="))
    assert "HttpOnly" in session
    assert "SameSite=strict" in session


def test_login_wrong_password(client, data):
    r = client.post("/api/v1/auth/login", json={"email": "teacher@t.test", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user_same_error(client, data):
    r = client.post("/api/v1/auth/login", json={"email": "ghost@t.test", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Грешен имейл или парола."


def test_passwords_are_bcrypt_hashed(data):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@t.test"))
        assert user.password_hash.startswith("$2")
        assert PASSWORD not in user.password_hash


def test_login_rate_limited(client, data):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "teacher@t.test", "password": "bad"})
    r = client.post("/api/v1/auth/login", json={"email": "teacher@t.test", "password": PASSWORD})
    assert r.status_code == 429


def test_me_requires_login(client, data):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_after_login(client, data):
    login(client, "teacher@t.test")
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["room_ids"] == [data["r214"]]


def test_tampered_token_rejected(client, data):
    client.cookies.set("kk_session", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.forged")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_csrf(client, data):
    login(client, "teacher@t.test")
    del client.headers["X-CSRF-Token"]
    assert client.post("/api/v1/auth/logout").status_code == 403


def test_logout(client, data):
    login(client, "teacher@t.test")
    assert client.post("/api/v1/auth/logout").status_code == 204

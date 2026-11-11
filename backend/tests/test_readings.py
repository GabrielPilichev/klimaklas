from datetime import timedelta

import pytest

from app.timeutil import iso_z, utcnow

from .conftest import device_headers, login


def test_post_reading(client, data):
    r = client.post(
        "/api/v1/readings", json={"co2": 750, "temperature": 22.5, "humidity": 41}, headers=device_headers()
    )
    assert r.status_code == 201
    assert r.json() == {"accepted": 1, "room_id": data["r214"]}


def test_reading_requires_device_token(client, data):
    assert client.post("/api/v1/readings", json={"co2": 700}).status_code == 401
    r = client.post("/api/v1/readings", json={"co2": 700}, headers=device_headers("kk_wrong"))
    assert r.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"co2": -5},
        {"co2": 50000},
        {"co2": "много"},
        {"co2": 700, "humidity": 140},
        {"co2": 700, "temperature": 200},
        {"co2": 700, "room_id": 999},  # непознато поле – не позволяваме устройството да сменя стаята
        {},
    ],
)
def test_reading_validation(client, data, payload):
    r = client.post("/api/v1/readings", json=payload, headers=device_headers())
    assert r.status_code == 422


def test_reading_in_future_rejected(client, data):
    future = iso_z(utcnow() + timedelta(hours=1))
    r = client.post("/api/v1/readings", json={"co2": 700, "measured_at": future}, headers=device_headers())
    assert r.status_code == 422


def test_batch_from_gateway(client, data):
    now = utcnow()
    readings = [{"co2": 600 + i, "measured_at": iso_z(now - timedelta(minutes=10 - i))} for i in range(10)]
    r = client.post("/api/v1/readings/batch", json={"readings": readings}, headers=device_headers())
    assert r.status_code == 201
    assert r.json()["accepted"] == 10


def test_device_rate_limited(client, data):
    codes = [
        client.post("/api/v1/readings", json={"co2": 700}, headers=device_headers()).status_code for _ in range(31)
    ]
    assert codes[-1] == 429


def test_room_status_colours(client, data):
    login(client, "admin@t.test")
    room = client.get(f"/api/v1/rooms/{data['r214']}").json()
    assert room["status"] == "offline"
    for co2, expected in [(650, "green"), (1000, "yellow"), (1500, "red")]:
        client.post("/api/v1/readings", json={"co2": co2}, headers=device_headers())
        room = client.get(f"/api/v1/rooms/{data['r214']}").json()
        assert room["status"] == expected
        assert room["latest"]["co2"] == co2


def test_room_readings_series_and_csv(client, data):
    client.post("/api/v1/readings", json={"co2": 900, "temperature": 22}, headers=device_headers())
    login(client, "teacher@t.test")
    series = client.get(f"/api/v1/rooms/{data['r214']}/readings?hours=1").json()
    assert [p["co2"] for p in series["points"]] == [900]
    csv = client.get(f"/api/v1/rooms/{data['r214']}/export.csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "900" in csv.text


def test_csv_formula_injection_escaped(client, data):
    login(client, "admin@t.test")
    client.patch(f"/api/v1/rooms/{data['r214']}", json={"name": "=HYPERLINK(1)"})
    client.post("/api/v1/readings", json={"co2": 900}, headers=device_headers())
    text = client.get(f"/api/v1/rooms/{data['r214']}/export.csv").text
    assert "'=HYPERLINK(1)" in text


def test_html_in_names_rejected(client, data):
    login(client, "admin@t.test")
    r = client.post("/api/v1/rooms", json={"school_id": data["school1"], "name": "<script>alert(1)</script>"})
    assert r.status_code == 422


def test_sql_injection_attempt_is_harmless(client, data):
    r = client.post("/api/v1/auth/login", json={"email": "' OR 1=1 --", "password": "' OR '1'='1"})
    assert r.status_code == 401
    login(client, "admin@t.test")
    assert client.get("/api/v1/rooms/1%20OR%201=1").status_code == 422
    assert len(client.get("/api/v1/rooms").json()) == 3


def test_security_headers(client, data):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]

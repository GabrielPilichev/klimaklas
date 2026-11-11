from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.timeutil import iso_z, utcnow

from .conftest import device_headers, login


def test_weekly_report(client, data):
    now = utcnow()
    readings = [
        {
            "co2": 1300 if i < 30 else 700,
            "temperature": 22,
            "humidity": 40,
            "measured_at": iso_z(now - timedelta(minutes=60 - i)),
        }
        for i in range(60)
    ]
    client.post("/api/v1/readings/batch", json={"readings": readings}, headers=device_headers())
    login(client, "dir@t.test")
    report = client.get("/api/v1/reports/weekly").json()
    assert report["school_id"] == data["school1"]
    room = next(r for r in report["rooms"] if r["room_id"] == data["r214"])
    assert room["minutes_over_alert"] == 30
    assert room["percent_over_alert"] == 50.0
    assert room["max_co2"] == 1300
    assert room["alerts"] == 1
    empty = next(r for r in report["rooms"] if r["room_id"] == data["r101"])
    assert empty["avg_co2"] is None


def test_weekly_report_csv(client, data):
    login(client, "dir@t.test")
    r = client.get("/api/v1/reports/weekly?format=csv")
    assert r.status_code == 200
    assert "минути над 1200 ppm" in r.text


def test_websocket_requires_login(client, data):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.receive_json()


def test_websocket_rejects_foreign_origin(client, data):
    login(client, "teacher@t.test")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_websocket_pushes_only_visible_rooms(client, data):
    login(client, "teacher@t.test")
    with client.websocket_connect("/api/v1/ws", headers={"origin": "http://testserver"}) as ws:
        # чужда стая – учителят не трябва да я получи
        client.post("/api/v1/readings", json={"co2": 999}, headers=device_headers("kk_dev305"))
        client.post("/api/v1/readings", json={"co2": 1234}, headers=device_headers("kk_dev214"))
        msg = ws.receive_json()
        assert msg["type"] == "reading"
        assert msg["room_id"] == data["r214"]
        assert msg["reading"]["co2"] == 1234
        assert msg["status"] == "red"

from datetime import timedelta

from sqlalchemy import select

from app import notify
from app.db import SessionLocal
from app.models import Alert, Room
from app.services import process_alert_rule
from app.timeutil import iso_z, utcnow

from .conftest import device_headers, login


def _feed(room_id: int, values: list[int], start, step_s: int = 60) -> list[Alert]:
    created = []
    with SessionLocal() as db:
        room = db.get(Room, room_id)
        for i, co2 in enumerate(values):
            a = process_alert_rule(db, room, co2, start + timedelta(seconds=i * step_s))
            if a:
                created.append(a)
        db.commit()
    return created


def test_no_alert_before_five_minutes(data):
    start = utcnow() - timedelta(hours=1)
    assert _feed(data["r214"], [1300] * 5, start) == []  # 0..4 мин


def test_alert_after_five_minutes(data):
    start = utcnow() - timedelta(hours=1)
    created = _feed(data["r214"], [1300] * 6, start)  # 0..5 мин
    assert len(created) == 1


def test_short_spike_does_not_alert(data):
    start = utcnow() - timedelta(hours=1)
    assert _feed(data["r214"], [1300, 1300, 1300, 900, 1300, 1300, 1300, 1300], start) == []


def test_alert_created_once_and_resolved(data):
    start = utcnow() - timedelta(hours=1)
    _feed(data["r214"], [1300] * 10 + [1500] * 3 + [800], start)
    with SessionLocal() as db:
        alerts = list(db.scalars(select(Alert)))
        assert len(alerts) == 1
        assert alerts[0].max_co2 == 1500
        assert alerts[0].resolved_at is not None


def test_threshold_is_strictly_above_1200(data):
    start = utcnow() - timedelta(hours=1)
    assert _feed(data["r214"], [1200] * 10, start) == []


def test_end_to_end_alert_notifies_teacher_and_director(client, data):
    now = utcnow()
    readings = [{"co2": 1400, "measured_at": iso_z(now - timedelta(minutes=6 - i))} for i in range(7)]
    r = client.post("/api/v1/readings/batch", json={"readings": readings}, headers=device_headers())
    assert r.status_code == 201
    recipients = {to for _, to, _ in notify.sent_messages}
    assert recipients == {"teacher@t.test", "dir@t.test"}
    assert "Отворете прозореца в стая 214" in notify.sent_messages[0][2]

    login(client, "teacher@t.test")
    alerts = client.get("/api/v1/alerts?active=true").json()
    assert len(alerts) == 1 and alerts[0]["room_name"] == "214"
    acked = client.post(f"/api/v1/alerts/{alerts[0]['id']}/ack").json()
    assert acked["acknowledged_at"] is not None


def test_old_buffered_data_does_not_notify(client, data):
    old = utcnow() - timedelta(hours=3)
    readings = [{"co2": 1400, "measured_at": iso_z(old + timedelta(minutes=i))} for i in range(7)]
    client.post("/api/v1/readings/batch", json={"readings": readings}, headers=device_headers())
    assert notify.sent_messages == []


def test_teacher_cannot_ack_foreign_alert(client, data):
    now = utcnow()
    readings = [{"co2": 1400, "measured_at": iso_z(now - timedelta(minutes=6 - i))} for i in range(7)]
    client.post("/api/v1/readings/batch", json={"readings": readings}, headers=device_headers("kk_dev305"))
    login(client, "teacher@t.test")
    assert client.get("/api/v1/alerts").json() == []
    assert client.post("/api/v1/alerts/1/ack").status_code == 404

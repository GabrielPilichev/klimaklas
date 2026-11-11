import json
from types import SimpleNamespace

import httpx

import gateway


def test_queue_survives_and_strips_unknown_fields(tmp_path):
    q = gateway.Queue(str(tmp_path / "q.db"))
    handler = gateway.on_message(q)
    payload = {"token": "kk_x", "co2": 900, "evil": "drop table", "measured_at": "2026-11-11T10:00:00Z"}
    handler(None, None, SimpleNamespace(topic="klimaklas/room-214/reading", payload=json.dumps(payload).encode()))
    handler(None, None, SimpleNamespace(topic="klimaklas/x/reading", payload=b"not json"))
    q2 = gateway.Queue(str(tmp_path / "q.db"))  # „рестарт“
    rows = q2.peek(10)
    assert len(rows) == 1
    assert rows[0][1] == "kk_x"
    assert rows[0][2] == {"co2": 900, "measured_at": "2026-11-11T10:00:00Z"}


def test_forward_groups_by_token_and_keeps_data_on_failure(tmp_path):
    q = gateway.Queue(str(tmp_path / "q.db"))
    q.push("kk_a", {"co2": 700})
    q.push("kk_b", {"co2": 800})
    q.push("kk_a", {"co2": 710})

    calls = []

    def ok(request: httpx.Request):
        calls.append((request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(201, json={"accepted": 1})

    with httpx.Client(transport=httpx.MockTransport(ok)) as http:
        gateway.forward_once(q, http)
    assert q.size() == 0
    assert ("Bearer kk_a", {"readings": [{"co2": 700}, {"co2": 710}]}) in calls

    q.push("kk_a", {"co2": 720})
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as http:
        try:
            gateway.forward_once(q, http)
        except httpx.HTTPError:
            pass
    assert q.size() == 1  # нищо не се губи, когато сървърът не отговаря

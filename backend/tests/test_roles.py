from .conftest import login


def _room_ids(client):
    r = client.get("/api/v1/rooms")
    assert r.status_code == 200
    return {room["id"] for room in r.json()}


def test_admin_sees_all_rooms(client, data):
    login(client, "admin@t.test")
    assert _room_ids(client) == {data["r214"], data["r101"], data["other"]}


def test_director_sees_only_own_school(client, data):
    login(client, "dir@t.test")
    assert _room_ids(client) == {data["r214"], data["r101"]}


def test_teacher_sees_only_assigned_rooms(client, data):
    login(client, "teacher@t.test")
    assert _room_ids(client) == {data["r214"]}


def test_teacher_cannot_open_foreign_room(client, data):
    login(client, "teacher@t.test")
    assert client.get(f"/api/v1/rooms/{data['r101']}").status_code == 404
    assert client.get(f"/api/v1/rooms/{data['r101']}/readings").status_code == 404
    assert client.get(f"/api/v1/rooms/{data['r101']}/export.csv").status_code == 404


def test_director_cannot_open_other_school_room(client, data):
    login(client, "dir@t.test")
    assert client.get(f"/api/v1/rooms/{data['other']}").status_code == 404


def test_teacher_cannot_manage_users(client, data):
    login(client, "teacher@t.test")
    assert client.get("/api/v1/users").status_code == 403
    r = client.post(
        "/api/v1/users",
        json={"email": "x@t.test", "full_name": "X", "password": "12345678", "role": "admin"},
    )
    assert r.status_code == 403


def test_director_cannot_create_devices(client, data):
    login(client, "dir@t.test")
    r = client.post("/api/v1/devices", json={"room_id": data["r101"], "name": "Нов"})
    assert r.status_code == 403


def test_teacher_cannot_see_reports(client, data):
    login(client, "teacher@t.test")
    assert client.get("/api/v1/reports/weekly").status_code == 403


def test_director_cannot_request_other_school_report(client, data):
    login(client, "dir@t.test")
    assert client.get(f"/api/v1/reports/weekly?school_id={data['school2']}").status_code == 404


def test_admin_creates_teacher_with_rooms(client, data):
    login(client, "admin@t.test")
    r = client.post(
        "/api/v1/users",
        json={
            "email": "new@t.test",
            "full_name": "Нов учител",
            "password": "dobra-parola",
            "role": "teacher",
            "school_id": data["school1"],
            "room_ids": [data["r101"]],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["room_ids"] == [data["r101"]]
    # дублиран имейл
    r2 = client.post(
        "/api/v1/users",
        json={"email": "NEW@t.test", "full_name": "Пак", "password": "dobra-parola", "role": "admin"},
    )
    assert r2.status_code == 409


def test_admin_device_token_shown_once_and_works(client, data):
    login(client, "admin@t.test")
    r = client.post("/api/v1/devices", json={"room_id": data["r101"], "name": "Сензор 101"})
    assert r.status_code == 201
    token = r.json()["token"]
    assert token.startswith("kk_")
    listed = client.get("/api/v1/devices").json()
    assert all("token" not in d for d in listed)
    client.cookies.clear()
    del client.headers["X-CSRF-Token"]
    r = client.post("/api/v1/readings", json={"co2": 650}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["room_id"] == data["r101"]

"""Настройки за Render: един процес сервира и API, и Vue панела."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_render_database_url_gets_psycopg_driver():
    s = Settings(database_url="postgresql://u:p@host/db")
    assert s.database_url == "postgresql+psycopg://u:p@host/db"
    assert Settings(database_url="sqlite://").database_url == "sqlite://"


def test_public_url_from_render(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://klimaklas.onrender.com")
    assert Settings().public_url == "https://klimaklas.onrender.com"
    assert Settings(public_url="https://x.bg").public_url == "https://x.bg"


def test_dashboard_served_with_spa_fallback(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=app></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("x")
    monkeypatch.setattr("app.main.settings.static_dir", str(tmp_path))
    client = TestClient(create_app())

    r = client.get("/rooms/5")  # маршрут на Vue → index.html
    assert r.status_code == 200 and "id=app" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert "id=app" in client.get("/../secret.txt").text  # не излиза извън папката
    assert client.get("/api/v1/nope").status_code == 404
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/health").headers["content-security-policy"].startswith("default-src 'none'")

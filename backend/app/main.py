import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import create_tables
from .middleware import CSRFMiddleware, SecurityHeadersMiddleware
from .routers import admin, alerts, auth, readings, reports, rooms, ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("klimaklas")


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    if settings.seed_demo:
        if settings.environment == "production" and not os.environ.get("KK_DEMO_PASSWORD"):
            log.warning("KK_SEED_DEMO е включен, но KK_DEMO_PASSWORD липсва – не зареждам демо данни.")
        else:
            from .seed import seed

            seed()
    yield


def mount_dashboard(app: FastAPI, directory: str) -> None:
    """Сервира Vue панела; непознатите пътища връщат index.html (маршрутите са в браузъра)."""
    root = Path(directory).resolve()
    index = root / "index.html"
    if not index.is_file():
        log.warning("KK_STATIC_DIR=%s няма index.html – панелът няма да се сервира.", directory)
        return
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def dashboard(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    settings.check()
    app = FastAPI(
        title="КлимаКлас API",
        version="1.0.0",
        description="Мониторинг на въздуха (CO₂, температура, влажност) в класните стаи.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    for module in (auth, readings, rooms, admin, alerts, reports, ws):
        app.include_router(module.router, prefix="/api/v1")

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    if settings.static_dir:
        mount_dashboard(app, settings.static_dir)
    return app


app = create_app()

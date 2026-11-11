import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .db import create_tables
from .middleware import CSRFMiddleware, SecurityHeadersMiddleware
from .routers import admin, alerts, auth, readings, reports, rooms, ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


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
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    for module in (auth, readings, rooms, admin, alerts, reports, ws):
        app.include_router(module.router, prefix="/api/v1")

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

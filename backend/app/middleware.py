from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import settings
from .security import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, tokens_equal

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Тези пътища не използват бисквитка за вход, затова CSRF не ги засяга.
CSRF_EXEMPT = ("/api/v1/auth/login", "/api/v1/readings")
# Същата политика като в deploy/Caddyfile – за панела, когато FastAPI го сервира сам.
DASHBOARD_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self' wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie: при вход с бисквитка всяка променяща заявка трябва да изпрати
    същия CSRF токен и в хедъра X-CSRF-Token. Друг сайт не може да прочете бисквитката,
    затова не може да подправи хедъра."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if (
            request.method not in SAFE_METHODS
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith(CSRF_EXEMPT)
            and SESSION_COOKIE in request.cookies
        ):
            cookie = request.cookies.get(CSRF_COOKIE, "")
            header = request.headers.get(CSRF_HEADER, "")
            if not cookie or not header or not tokens_equal(cookie, header):
                return JSONResponse({"detail": "Невалиден CSRF токен."}, status_code=403)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        path = request.url.path
        if not path.startswith("/api/"):
            h.setdefault("Content-Security-Policy", DASHBOARD_CSP)
        elif not path.startswith("/api/docs"):
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if settings.cookie_secure:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/v1/"):
            h.setdefault("Cache-Control", "no-store")
        return response

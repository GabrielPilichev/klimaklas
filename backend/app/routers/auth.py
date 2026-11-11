from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..ratelimit import RateLimiter
from ..schemas import LoginIn, UserOut
from ..security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    create_session_token,
    new_csrf_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = RateLimiter(settings.login_rate_limit, 60)


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.room_ids = sorted(r.id for r in user.rooms)
    return out


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    ip = request.client.host if request.client else "unknown"
    if not login_limiter.hit(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Твърде много опити. Опитайте след минута.")

    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    ok = verify_password(payload.password, user.password_hash if user else None)
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Грешен имейл или парола.")

    max_age = settings.token_ttl_minutes * 60
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, user.role.value),
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        new_csrf_token(),
        max_age=max_age,
        httponly=False,  # фронтендът трябва да го прочете и да го върне в хедър
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)

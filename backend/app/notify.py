"""Изпращане на известия по имейл и Telegram. Без настройки известията само се записват в лога."""

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Alert, Role, User

log = logging.getLogger("klimaklas.notify")

# Тестовете могат да заменят тези функции, за да проверят какво би било изпратено.
sent_messages: list[tuple[str, str, str]] = []  # (канал, получател, текст) – последните изпратени


def alert_text(room_name: str, co2: int, minutes: int) -> str:
    return (
        f"⚠️ Отворете прозореца в стая {room_name}!\n"
        f"CO₂ е {co2} ppm вече {minutes} мин. (прагът е {settings.co2_alert} ppm).\n"
        f"{settings.public_url}"
    )


def _send_telegram(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=10).raise_for_status()


def _send_email(to: str, subject: str, text: str) -> None:
    if not settings.smtp_host:
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def _deliver(channel: str, to: str, text: str, subject: str = "") -> None:
    sent_messages.append((channel, to, text))
    del sent_messages[:-100]
    try:
        if channel == "telegram":
            _send_telegram(to, text)
        else:
            _send_email(to, subject, text)
    except Exception:  # известията не трябва да спират приемането на данни
        log.exception("Неуспешно известие през %s до %s", channel, to)


def send_alert_notifications(alert_id: int) -> None:
    """Изпълнява се като background task след приемане на измерване."""
    with SessionLocal() as db:
        alert = db.get(Alert, alert_id)
        if alert is None or alert.notified:
            return
        room = alert.room
        minutes = max(1, round((alert.triggered_at - alert.started_at).total_seconds() / 60))
        text = alert_text(room.name, alert.max_co2, minutes)
        subject = f"КлимаКлас: висок CO₂ в стая {room.name}"

        recipients: set[User] = set(room.teachers)
        recipients.update(
            db.scalars(
                select(User).where(
                    User.role == Role.director, User.school_id == room.school_id, User.is_active.is_(True)
                )
            )
        )
        if settings.telegram_chat_id:
            _deliver("telegram", settings.telegram_chat_id, text)
        for user in recipients:
            if not user.is_active:
                continue
            if user.telegram_chat_id:
                _deliver("telegram", user.telegram_chat_id, text)
            _deliver("email", user.email, text, subject)

        log.warning("ИЗВЕСТИЕ: %s", text.replace("\n", " "))
        alert.notified = True
        db.commit()

from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..db import SessionLocal
from ..deps import user_from_token
from ..realtime import Connection, manager
from ..security import SESSION_COOKIE

router = APIRouter(tags=["realtime"])


def _same_origin(ws: WebSocket) -> bool:
    """Защита от Cross-Site WebSocket Hijacking: приемаме само заявки от нашия сайт."""
    origin = ws.headers.get("origin")
    if origin is None:  # не е браузър (напр. скрипт) – бисквитката пак е нужна
        return True
    return urlparse(origin).netloc == ws.headers.get("host")


@router.websocket("/ws")
async def live(ws: WebSocket) -> None:
    if not _same_origin(ws):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    with SessionLocal() as db:
        user = user_from_token(db, ws.cookies.get(SESSION_COOKIE))
        if user is None:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        conn = Connection(ws=ws, role=user.role, school_id=user.school_id, room_ids={r.id for r in user.rooms})

    await ws.accept()
    manager.add(conn)
    try:
        while True:
            # Клиентът праща "ping", за да държи връзката жива; съдържанието не ни интересува.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(conn)

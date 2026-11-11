"""Стойности на живо през WebSocket. Всяка връзка получава само стаите, които потребителят има право да вижда."""

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from .models import Role


@dataclass(eq=False)
class Connection:
    ws: WebSocket
    role: Role
    school_id: int | None
    room_ids: set[int] = field(default_factory=set)

    def can_see(self, room_id: int, school_id: int) -> bool:
        if self.role == Role.admin:
            return True
        if self.role == Role.director:
            return self.school_id == school_id
        return room_id in self.room_ids


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[Connection] = set()

    def add(self, conn: Connection) -> None:
        self.connections.add(conn)

    def remove(self, conn: Connection) -> None:
        self.connections.discard(conn)

    async def broadcast(self, room_id: int, school_id: int, message: dict) -> None:
        targets = [c for c in self.connections if c.can_see(room_id, school_id)]
        results = await asyncio.gather(*(c.ws.send_json(message) for c in targets), return_exceptions=True)
        for conn, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                self.remove(conn)


manager = ConnectionManager()

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime

from fastapi import WebSocket


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class WSManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        print(f"[WS] Loop set: {loop}")

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id].append(ws)
        print(f"[WS] Connected: {user_id}, total connections: {len(self._connections.get(user_id, []))}")

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        user_sockets = self._connections.get(user_id, [])
        if ws in user_sockets:
            user_sockets.remove(ws)
        if not self._connections.get(user_id):
            self._connections.pop(user_id, None)
        print(f"[WS] Disconnected: {user_id}")

    async def _send_json(self, ws: WebSocket, data: dict) -> None:
        try:
            await ws.send_text(json.dumps(data, default=_json_default))
            print(f"[WS] Sent to {id(ws)}: {data.get('type')}")
        except Exception as e:
            print(f"[WS] Send error: {e}")

    def _schedule_send(self, ws: WebSocket, data: dict) -> None:
        print(f"[WS] Schedule send to {id(ws)}: {data.get('type')}, loop={self._loop}, running={self._loop.is_running() if self._loop else False}")
        if self._loop and self._loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._send_json(ws, data), self._loop)
            fut.add_done_callback(lambda f: f.exception())

    def send_to_user(self, user_id: str, data: dict) -> None:
        sockets = self._connections.get(user_id, [])
        print(f"[WS] send_to_user {user_id}: {len(sockets)} sockets, data type={data.get('type')}")
        for ws in sockets:
            self._schedule_send(ws, data)

    def broadcast_to_chat(
        self,
        member_ids: list[str],
        data: dict,
        exclude_user_id: str | None = None,
    ) -> None:
        for uid in member_ids:
            if uid != exclude_user_id:
                self.send_to_user(uid, data)

    def send_global_mentions(self, user_id: str, count: int) -> None:
        self.send_to_user(user_id, {"type": "global_mentions", "count": count})

    def send_new_message(
        self,
        member_ids: list[str],
        chat_id: int,
        message: dict,
        sender_id: str,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "new_message", "chat_id": chat_id, "message": message},
            exclude_user_id=sender_id,
        )

    def send_message_updated(
        self,
        member_ids: list[str],
        chat_id: int,
        message: dict,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "message_updated", "chat_id": chat_id, "message": message},
        )

    def send_message_deleted(
        self,
        member_ids: list[str],
        chat_id: int,
        message_id: int,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "message_deleted", "chat_id": chat_id, "message_id": message_id},
        )

    def send_mention(
        self,
        member_ids: list[str],
        chat_id: int,
        message_id: int,
        target_user_id: str,
        unviewed_count: int = 0,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "mention", "chat_id": chat_id, "message_id": message_id},
        )
        self.send_global_mentions(target_user_id, unviewed_count)

    def send_read_status(
        self,
        member_ids: list[str],
        chat_id: int,
        user_id: str,
        last_read_message_id: int,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {
                "type": "read_status",
                "chat_id": chat_id,
                "user_id": user_id,
                "last_read_message_id": last_read_message_id,
            },
        )

    def send_badge(
        self,
        member_ids: list[str],
        chat_id: int,
        unread: bool,
        has_unviewed_mention: bool,
    ) -> None:
        self.broadcast_to_chat(
            member_ids,
            {
                "type": "badge",
                "chat_id": chat_id,
                "unread": unread,
                "has_unviewed_mention": has_unviewed_mention,
            },
        )

    def send_chat_updated(self, member_ids: list[str], chat: dict) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "chat_updated", "chat": chat},
        )

    def send_new_chat(self, member_ids: list[str], chat: dict) -> None:
        self.broadcast_to_chat(
            member_ids,
            {"type": "new_chat", "chat": chat},
        )

    def send_badge_counts(self, user_id: str, counts: dict) -> None:
        self.send_to_user(user_id, {"type": "badge_counts", **counts})


ws_manager = WSManager()

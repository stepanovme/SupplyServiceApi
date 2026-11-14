import asyncio
import json

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.database import AuthSessionLocal, SupplySessionLocal, current_tenant, resolve_tenant, tenant_cookie_name
from app.repositories.session_repository import SessionRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.notification_feed_repository import NotificationFeedRepository
from app.routes import main_router
from app.routes.request_suppliers_routes import public_request_suppliers_router
from app.services.ws_manager import ws_manager


def _get_badge_counts(user_id: str) -> dict:
    db = SupplySessionLocal()
    try:
        repo = InvoiceRepository(db)
        return repo.get_badge_counts(user_id)
    finally:
        db.close()


def _get_notification_unread_count(user_id: str) -> int:
    db = SupplySessionLocal()
    try:
        repo = NotificationFeedRepository(db)
        return repo.get_unread_count(user_id)
    finally:
        db.close()


app = FastAPI(
    title="SupplyService",
    debug=True,
)


class TenantMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        tenant = resolve_tenant(scope)
        if tenant is None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await send({"type": "http.response.start", "status": 403, "headers": []})
                await send({"type": "http.response.body", "body": b"Unknown site"})
            return
        token = current_tenant.set(tenant)
        try:
            await self.app(scope, receive, send)
        finally:
            current_tenant.reset(token)


app.add_middleware(TenantMiddleware)


@app.on_event("startup")
async def startup():
    ws_manager.set_loop(asyncio.get_event_loop())


@app.websocket("/api/supply/ws")
async def websocket_endpoint(
    ws: WebSocket,
    user_id: str | None = Query(default=None),
):
    def authenticate():
        token = ws.cookies.get(tenant_cookie_name())
        if not token:
            return None
        db = AuthSessionLocal()
        try:
            session = SessionRepository(db).get_by_token(token)
            return str(session.user_id) if session else None
        finally:
            db.close()

    authenticated_id = await run_in_threadpool(authenticate)
    if not authenticated_id or (user_id and user_id != authenticated_id):
        await ws.close(code=4001, reason="Invalid session")
        return
    user_id = authenticated_id

    await ws_manager.connect(user_id, ws)

    # send initial badge counts
    try:
        counts = _get_badge_counts(user_id)
        await ws.send_text(json.dumps({"type": "badge_counts", **counts}))
    except Exception:
        pass

    # send initial notification unread count
    try:
        n_count = _get_notification_unread_count(user_id)
        await ws.send_text(json.dumps({"type": "notification_unread", "unread_count": n_count}))
    except Exception:
        pass

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
            elif data.startswith("{"):
                try:
                    payload = json.loads(data)
                    if payload.get("type") != "typing" or type(payload.get("chat_id")) is not int or type(payload.get("is_typing")) is not bool:
                        continue
                    def typing_recipients():
                        db = SupplySessionLocal()
                        auth_db = AuthSessionLocal()
                        try:
                            repo = ChatRepository(db)
                            if not repo.get_member(payload["chat_id"], user_id):
                                return None
                            users = AuthUserRepository(auth_db).get_by_ids([user_id])
                            user = users[0] if users else None
                            name = " ".join(filter(None, (user.surname, user.name, user.patronymic))) if user else None
                            return [str(member.user_id) for member in repo.get_members(payload["chat_id"])], name
                        finally:
                            db.close()
                            auth_db.close()
                    result = await run_in_threadpool(typing_recipients)
                    if result:
                        members, name = result
                        ws_manager.broadcast_to_chat(members, {"type": "typing", "chat_id": payload["chat_id"], "user_id": user_id, "user_name": name, "is_typing": payload["is_typing"]}, exclude_user_id=user_id)
                except (ValueError, TypeError, AttributeError):
                    continue
            elif data == "get_badge":
                try:
                    counts = _get_badge_counts(user_id)
                    await ws.send_text(json.dumps({"type": "badge_counts", **counts}))
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(user_id, ws)


app.include_router(main_router)
app.include_router(public_request_suppliers_router, prefix="/api/supply")

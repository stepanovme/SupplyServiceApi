import asyncio
import json

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from app.database import SupplySessionLocal
from app.repositories.invoice_repository import InvoiceRepository
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


app = FastAPI(
    title="SupplyService",
    debug=True,
)


@app.on_event("startup")
async def startup():
    ws_manager.set_loop(asyncio.get_event_loop())


@app.websocket("/api/supply/ws")
async def websocket_endpoint(
    ws: WebSocket,
    user_id: str = Query(...),
):
    if not user_id:
        await ws.close(code=4001, reason="Missing user_id")
        return

    await ws_manager.connect(user_id, ws)

    # send initial badge counts
    try:
        counts = _get_badge_counts(user_id)
        await ws.send_text(json.dumps({"type": "badge_counts", **counts}))
    except Exception:
        pass

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
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

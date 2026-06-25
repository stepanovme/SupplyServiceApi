from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    user_id: str = Query(...),
):
    if not user_id:
        await ws.close(code=4001, reason="Missing user_id")
        return

    await ws_manager.connect(user_id, ws)

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(user_id, ws)

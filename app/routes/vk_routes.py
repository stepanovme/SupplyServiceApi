import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.repositories.vk_repository import VkRepository
from app.services.vk_service import VkService

vk_router = APIRouter(prefix="/vk", tags=["VK"])


class VkLinkRequest(BaseModel):
    vk_id: str


class VkNotificationsRequest(BaseModel):
    enabled: bool


def build_service(supply_db: DbSupplySession) -> VkService:
    return VkService(VkRepository(supply_db))


@vk_router.get("/status")
def vk_status(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(supply_db)
    return service.get_status(_session.user_id)


@vk_router.get("/link")
def get_vk_link(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(supply_db)
    return {"url": service.get_link_url(_session.user_id)}


@vk_router.post("/link")
def save_vk_link(
    payload: VkLinkRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(supply_db)
    result = service.save_vk_id(_session.user_id, payload.vk_id)
    if result:
        msg = service.send_notification(payload.vk_id, "Уведомления успешно настроены!")
        return {"ok": True, "notification_sent": msg}
    return {"ok": False}


@vk_router.patch("/notifications")
def toggle_vk_notifications(
    payload: VkNotificationsRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(supply_db)
    result = service.toggle_notifications(_session.user_id, payload.enabled)
    if not result:
        raise HTTPException(status_code=404, detail="VK link not found")
    return {"ok": True, "notifications_enabled": payload.enabled}


@vk_router.delete("/link")
def delete_vk_link(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(supply_db)
    service.delete_link(_session.user_id)
    return {"ok": True}


@vk_router.post("/callback", response_class=PlainTextResponse)
async def vk_callback(
    request: Request,
    supply_db: DbSupplySession,
):
    body = await request.json()
    service = build_service(supply_db)

    secret = os.getenv("VK_CALLBACK_SECRET", "")
    if secret and body.get("secret") != secret:
        return PlainTextResponse("ok")

    event_type = body.get("type")
    if event_type == "confirmation":
        return PlainTextResponse(service.get_confirmation_code())

    if event_type == "message_new":
        message = body.get("object", {}).get("message", {})
        vk_id = str(message.get("from_id"))
        ref = message.get("ref") or ""
        try:
            service.handle_message_new(vk_id, ref)
        except Exception as e:
            print(f"[VK] message_new error: {e}")

    return PlainTextResponse("ok")

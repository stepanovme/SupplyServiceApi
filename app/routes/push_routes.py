from pydantic import BaseModel

from fastapi import APIRouter, Depends, Header, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.repositories.push_subscription_repository import PushSubscriptionRepository
from app.services.push_service import PushService

push_router = APIRouter(prefix="/push", tags=["Push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    device_type: str = "desktop"


class ToggleRequest(BaseModel):
    is_active: bool


def build_service(supply_db: DbSupplySession) -> PushService:
    return PushService(PushSubscriptionRepository(supply_db))


@push_router.get("/vapid-public-key", status_code=status.HTTP_200_OK)
def get_vapid_public_key(supply_db: DbSupplySession):
    return {"public_key": build_service(supply_db).get_vapid_public_key()}


@push_router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    body: SubscribeRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    user_agent: str | None = Header(None, alias="User-Agent"),
):
    return build_service(supply_db).subscribe(
        user_id=_session.user_id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        device_type=body.device_type,
        user_agent=user_agent,
    )


@push_router.get("/subscriptions", status_code=status.HTTP_200_OK)
def list_subscriptions(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).list_subscriptions(_session.user_id)


@push_router.patch("/subscriptions/{sub_id}", status_code=status.HTTP_200_OK)
def toggle_subscription(
    sub_id: int,
    body: ToggleRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).toggle_subscription(sub_id, _session.user_id, body.is_active)


@push_router.delete("/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    sub_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).unsubscribe(sub_id, _session.user_id)
    return None

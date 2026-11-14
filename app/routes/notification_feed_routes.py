from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.repositories.notification_feed_repository import NotificationFeedRepository
from app.services.notification_feed_service import NotificationFeedService

notification_feed_router = APIRouter(prefix="/feed", tags=["Notification Feed"])


def build_service(db: DbSupplySession) -> NotificationFeedService:
    return NotificationFeedService(NotificationFeedRepository(db))


@notification_feed_router.get("")
def get_feed(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = build_service(db)
    return service.get_feed(str(_session.user_id), limit=limit, offset=offset)


@notification_feed_router.patch("/{notification_id}/unread")
def mark_unread(
    notification_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    result = service.mark_unread(notification_id, str(_session.user_id))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return result


@notification_feed_router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    result = service.mark_read(notification_id, str(_session.user_id))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return result


@notification_feed_router.patch("/read-all")
def mark_all_read(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    count = service.mark_all_read(str(_session.user_id))
    return {"marked_read": count}


@notification_feed_router.get("/unread-count")
def get_unread_count(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    count = service.get_unread_count(str(_session.user_id))
    return {"unread_count": count}

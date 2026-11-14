import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.notification_feed_repository import NotificationFeedRepository

logger = logging.getLogger(__name__)


def push_notification(db: Session, user_id: str, type: str, title: str | None = None,
                       body: str | None = None, object_type: str | None = None,
                       object_id: str | None = None, related_user_id: str | None = None) -> dict | None:
    if not user_id:
        return None
    repo = NotificationFeedRepository(db)
    service = NotificationFeedService(repo)
    result = service.create({
        "user_id": user_id,
        "type": type,
        "title": title,
        "body": body,
        "object_type": object_type,
        "object_id": object_id,
        "related_user_id": related_user_id,
    })
    if type in ("chat_message", "task_assigned"):
        from app.services.apns_service import schedule_notification
        try:
            schedule_notification(user_id, title, body, {"type": type, "object_type": object_type, "object_id": str(object_id or ""), "related_user_id": str(related_user_id or "")})
        except Exception:
            logger.exception("Could not schedule APNs notification")
    return result


class NotificationFeedService:
    def __init__(self, repo: NotificationFeedRepository) -> None:
        self.repo = repo

    def create(self, payload: dict) -> dict:
        row = self.repo.create(payload)
        notification = self._serialize(row)

        from app.services.ws_manager import ws_manager

        ws_manager.send_to_user(payload["user_id"], {
            "type": "notification",
            "notification": notification,
        })

        unread = self.repo.get_unread_count(payload["user_id"])
        ws_manager.send_to_user(payload["user_id"], {
            "type": "notification_unread",
            "unread_count": unread,
        })

        return notification

    def get_feed(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.repo.get_for_user(user_id, limit=limit, offset=offset)
        return [self._serialize(r) for r in rows]

    def mark_read(self, notification_id: int, user_id: str) -> dict | None:
        row = self.repo.get_by_id(notification_id)
        if not row or row.user_id != user_id:
            return None
        row = self.repo.mark_read(notification_id)
        if row:
            notification = self._serialize(row)
            from app.services.ws_manager import ws_manager

            unread = self.repo.get_unread_count(user_id)
            ws_manager.send_to_user(user_id, {
                "type": "notification_read",
                "notification_id": notification_id,
                "unread_count": unread,
            })
            return notification
        return None

    def mark_unread(self, notification_id: int, user_id: str) -> dict | None:
        row = self.repo.get_by_id(notification_id)
        if not row or row.user_id != user_id:
            return None
        row = self.repo.mark_unread(notification_id)
        if row:
            notification = self._serialize(row)
            from app.services.ws_manager import ws_manager

            unread = self.repo.get_unread_count(user_id)
            ws_manager.send_to_user(user_id, {
                "type": "notification_unread",
                "unread_count": unread,
            })
            return notification
        return None

    def mark_all_read(self, user_id: str) -> int:
        count = self.repo.mark_all_read(user_id)

        from app.services.ws_manager import ws_manager

        ws_manager.send_to_user(user_id, {
            "type": "notification_read_all",
            "unread_count": 0,
        })
        return count

    def get_unread_count(self, user_id: str) -> int:
        return self.repo.get_unread_count(user_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "type": row.type,
            "title": row.title,
            "body": row.body,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "related_user_id": row.related_user_id,
            "is_read": row.is_read,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

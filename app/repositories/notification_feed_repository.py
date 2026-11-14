import uuid

from sqlalchemy.orm import Session

from app.models.notification_feed import NotificationFeed


class NotificationFeedRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NotificationFeed:
        row = NotificationFeed(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_for_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[NotificationFeed]:
        return (
            self.db.query(NotificationFeed)
            .filter(NotificationFeed.user_id == user_id)
            .order_by(NotificationFeed.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_id(self, notification_id: int) -> NotificationFeed | None:
        return self.db.query(NotificationFeed).filter(NotificationFeed.id == notification_id).first()

    def mark_read(self, notification_id: int) -> NotificationFeed | None:
        row = self.get_by_id(notification_id)
        if row:
            row.is_read = True
            self.db.commit()
            self.db.refresh(row)
        return row

    def mark_unread(self, notification_id: int) -> NotificationFeed | None:
        row = self.get_by_id(notification_id)
        if row:
            row.is_read = False
            self.db.commit()
            self.db.refresh(row)
        return row

    def mark_all_read(self, user_id: str) -> int:
        count = (
            self.db.query(NotificationFeed)
            .filter(NotificationFeed.user_id == user_id, NotificationFeed.is_read == False)
            .update({"is_read": True})
        )
        self.db.commit()
        return count

    def get_unread_count(self, user_id: str) -> int:
        return (
            self.db.query(NotificationFeed)
            .filter(NotificationFeed.user_id == user_id, NotificationFeed.is_read == False)
            .count()
        )

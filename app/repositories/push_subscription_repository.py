from sqlalchemy.orm import Session

from app.models.push_subscription import PushSubscription


class PushSubscriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, sub_id: int) -> PushSubscription | None:
        return self.db.query(PushSubscription).filter(PushSubscription.id == sub_id).first()

    def get_by_user_id(self, user_id: str) -> list[PushSubscription]:
        return self.db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()

    def get_active_by_user_id(self, user_id: str) -> list[PushSubscription]:
        return (
            self.db.query(PushSubscription)
            .filter(PushSubscription.user_id == user_id, PushSubscription.is_active == True)
            .all()
        )

    def create(
        self,
        user_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        device_type: str,
        user_agent: str | None = None,
    ) -> PushSubscription:
        row = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            device_type=device_type,
            user_agent=user_agent,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_is_active(self, sub_id: int, is_active: bool) -> PushSubscription | None:
        row = self.get_by_id(sub_id)
        if not row:
            return None
        row.is_active = is_active
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, sub_id: int) -> None:
        self.db.query(PushSubscription).filter(PushSubscription.id == sub_id).delete()
        self.db.commit()

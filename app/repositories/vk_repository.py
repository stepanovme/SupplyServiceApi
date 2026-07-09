from sqlalchemy.orm import Session

from app.models.vk import VkUserLink


class VkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: str) -> VkUserLink | None:
        return self.db.query(VkUserLink).filter(VkUserLink.user_id == user_id).first()

    def get_by_ref(self, ref: str) -> VkUserLink | None:
        return self.db.query(VkUserLink).filter(VkUserLink.ref == ref).first()

    def get_by_vk_id(self, vk_id: str) -> VkUserLink | None:
        return self.db.query(VkUserLink).filter(VkUserLink.vk_id == vk_id).first()

    def create(self, user_id: str, vk_id: str, ref: str | None = None) -> VkUserLink:
        row = VkUserLink(user_id=user_id, vk_id=vk_id, ref=ref)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_vk_id(self, user_id: str, vk_id: str) -> VkUserLink | None:
        row = self.get_by_user_id(user_id)
        if not row:
            return None
        row.vk_id = vk_id
        row.ref = None
        self.db.commit()
        self.db.refresh(row)
        return row

    def set_notifications(self, user_id: str, enabled: bool) -> VkUserLink | None:
        row = self.get_by_user_id(user_id)
        if not row:
            return None
        row.notifications_enabled = enabled
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_by_user_id(self, user_id: str) -> None:
        self.db.query(VkUserLink).filter(VkUserLink.user_id == user_id).delete()
        self.db.commit()

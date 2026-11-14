import uuid

from fastapi import HTTPException, status

from app.models.object_setting import ObjectSetting, ObjectSettingCreate, ObjectSettingUpdate
from app.repositories.object_setting_repository import ObjectSettingRepository


class ObjectSettingService:
    def __init__(self, repo: ObjectSettingRepository) -> None:
        self.repo = repo

    def get_all(self) -> list[ObjectSetting]:
        return self.repo.get_all()

    def get_by_id(self, item_id: str) -> ObjectSetting:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object setting not found",
            )
        return item

    def create(self, data: ObjectSettingCreate) -> ObjectSetting:
        item_data = data.model_dump(exclude_none=True)
        if "id" not in item_data or not item_data["id"]:
            item_data["id"] = str(uuid.uuid4())
        item = ObjectSetting(**item_data)
        return self.repo.create(item)

    def update(self, item_id: str, data: ObjectSettingUpdate) -> ObjectSetting:
        item = self.get_by_id(item_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        return self.repo.save(item)

    def get_create_request_object_ids(self, user_id: str) -> set[str]:
        return self.repo.get_create_request_object_ids_for_user(user_id)

    def get_accessible_object_ids(self, user_id: str) -> set[str]:
        return self.repo.get_accessible_object_ids_for_user(user_id)

    def delete(self, item_id: str) -> None:
        item = self.get_by_id(item_id)
        self.repo.delete(item)

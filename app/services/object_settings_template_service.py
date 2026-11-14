import uuid

from fastapi import HTTPException, status

from app.models.object_settings_template import (
    ObjectSettingsTemplate,
    ObjectSettingsTemplateCreate,
    ObjectSettingsTemplateUpdate,
)
from app.repositories.object_settings_template_repository import ObjectSettingsTemplateRepository


class ObjectSettingsTemplateService:
    def __init__(self, repo: ObjectSettingsTemplateRepository) -> None:
        self.repo = repo

    def get_all(self) -> list[ObjectSettingsTemplate]:
        return self.repo.get_all()

    def get_by_id(self, item_id: str) -> ObjectSettingsTemplate:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object settings template not found",
            )
        return item

    def create(self, data: ObjectSettingsTemplateCreate) -> ObjectSettingsTemplate:
        item_data = data.model_dump(exclude_none=True)
        if "id" not in item_data or not item_data["id"]:
            item_data["id"] = str(uuid.uuid4())
        item = ObjectSettingsTemplate(**item_data)
        return self.repo.create(item)

    def update(self, item_id: str, data: ObjectSettingsTemplateUpdate) -> ObjectSettingsTemplate:
        item = self.get_by_id(item_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        return self.repo.save(item)

    def delete(self, item_id: str) -> None:
        item = self.get_by_id(item_id)
        self.repo.delete(item)

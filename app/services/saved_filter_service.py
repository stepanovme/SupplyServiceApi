import uuid

from fastapi import HTTPException, status

from app.models.saved_filter import SavedFilter, SavedFilterCreate, SavedFilterUpdate
from app.repositories.saved_filter_repository import SavedFilterRepository


class SavedFilterService:
    def __init__(self, repo: SavedFilterRepository) -> None:
        self.repo = repo

    def get_by_user(self, user_id: str) -> list[SavedFilter]:
        return self.repo.get_by_user(user_id)

    def get_by_id(self, item_id: str, user_id: str) -> SavedFilter:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved filter not found",
            )
        if item.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        return item

    def create(self, data: SavedFilterCreate, user_id: str) -> SavedFilter:
        item_data = data.model_dump(exclude_none=True)
        item_data["id"] = str(uuid.uuid4())
        item_data["user_id"] = user_id
        item = SavedFilter(**item_data)
        return self.repo.create(item)

    def update(self, item_id: str, data: SavedFilterUpdate, user_id: str) -> SavedFilter:
        item = self.get_by_id(item_id, user_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        return self.repo.save(item)

    def delete(self, item_id: str, user_id: str) -> None:
        item = self.get_by_id(item_id, user_id)
        self.repo.delete(item)

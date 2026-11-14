from sqlalchemy.orm import Session

from app.models.saved_filter import SavedFilter


class SavedFilterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: str) -> list[SavedFilter]:
        return self.db.query(SavedFilter).filter(SavedFilter.user_id == user_id).all()

    def get_by_id(self, item_id: str) -> SavedFilter | None:
        return self.db.query(SavedFilter).filter(SavedFilter.id == item_id).first()

    def create(self, item: SavedFilter) -> SavedFilter:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: SavedFilter) -> SavedFilter:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: SavedFilter) -> None:
        self.db.delete(item)
        self.db.commit()

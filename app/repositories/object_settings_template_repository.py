from sqlalchemy.orm import Session

from app.models.object_settings_template import ObjectSettingsTemplate


class ObjectSettingsTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[ObjectSettingsTemplate]:
        return self.db.query(ObjectSettingsTemplate).all()

    def get_by_id(self, item_id: str) -> ObjectSettingsTemplate | None:
        return self.db.query(ObjectSettingsTemplate).filter(ObjectSettingsTemplate.id == item_id).first()

    def create(self, item: ObjectSettingsTemplate) -> ObjectSettingsTemplate:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: ObjectSettingsTemplate) -> ObjectSettingsTemplate:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: ObjectSettingsTemplate) -> None:
        self.db.delete(item)
        self.db.commit()

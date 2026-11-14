from sqlalchemy.orm import Session

from app.models.editor_key import EditorKey


class EditorKeyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_key(self, entity_type: str, entity_id: int) -> str | None:
        row = (
            self.db.query(EditorKey)
            .filter(EditorKey.entity_type == entity_type, EditorKey.entity_id == entity_id)
            .order_by(EditorKey.created_at.desc())
            .first()
        )
        return row.key if row else None

    def set_key(self, entity_type: str, entity_id: int, key: str) -> None:
        existing = (
            self.db.query(EditorKey)
            .filter(EditorKey.entity_type == entity_type, EditorKey.entity_id == entity_id)
            .all()
        )
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        row = EditorKey(entity_type=entity_type, entity_id=entity_id, key=key)
        self.db.add(row)
        self.db.commit()

    def delete_key(self, entity_type: str, entity_id: int) -> None:
        existing = (
            self.db.query(EditorKey)
            .filter(EditorKey.entity_type == entity_type, EditorKey.entity_id == entity_id)
            .all()
        )
        for row in existing:
            self.db.delete(row)
        self.db.commit()

import uuid

from sqlalchemy.orm import Session

from app.models.document_access_setting import DocumentAccessSetting
from app.database import msk_now


class DocumentAccessSettingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self, document_type: str | None = None) -> list[DocumentAccessSetting]:
        query = self.db.query(DocumentAccessSetting)
        if document_type:
            query = query.filter(DocumentAccessSetting.document_type == document_type)
        return query.order_by(DocumentAccessSetting.created_at.desc()).all()

    def get_by_id(self, setting_id: str) -> DocumentAccessSetting | None:
        return self.db.query(DocumentAccessSetting).filter(DocumentAccessSetting.id == setting_id).first()

    def get_for_user(
        self,
        document_type: str,
        user_id: str,
        department_ids: list[int],
    ) -> list[DocumentAccessSetting]:
        from sqlalchemy import or_
        conditions = [DocumentAccessSetting.user_id == user_id]
        if department_ids:
            conditions.append(DocumentAccessSetting.department_id.in_(department_ids))
        return (
            self.db.query(DocumentAccessSetting)
            .filter(
                DocumentAccessSetting.document_type == document_type,
                or_(*conditions),
            )
            .all()
        )

    def get_by_target(
        self,
        user_id: str | None = None,
        department_id: int | None = None,
    ) -> list[DocumentAccessSetting]:
        query = self.db.query(DocumentAccessSetting)
        if user_id:
            query = query.filter(DocumentAccessSetting.user_id == user_id)
        elif department_id is not None:
            query = query.filter(DocumentAccessSetting.department_id == department_id)
        return query.all()

    def delete_by_target(
        self,
        user_id: str | None = None,
        department_id: int | None = None,
    ) -> None:
        query = self.db.query(DocumentAccessSetting)
        if user_id:
            query = query.filter(DocumentAccessSetting.user_id == user_id)
        elif department_id is not None:
            query = query.filter(DocumentAccessSetting.department_id == department_id)
        query.delete(synchronize_session="fetch")
        self.db.commit()

    def create(self, data: dict) -> DocumentAccessSetting:
        row = DocumentAccessSetting(id=str(uuid.uuid4()), **data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: DocumentAccessSetting) -> DocumentAccessSetting:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: DocumentAccessSetting) -> None:
        self.db.delete(row)
        self.db.commit()

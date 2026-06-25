from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.smtp import Smtp


class SmtpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, smtp_id: str) -> Smtp | None:
        return self.db.query(Smtp).filter(Smtp.id == smtp_id).first()

    def get_by_user_id(self, user_id: str) -> list[Smtp]:
        return (
            self.db.query(Smtp)
            .filter(Smtp.user_id == user_id)
            .order_by(Smtp.created_at.desc(), Smtp.id.desc())
            .all()
        )

    def create(self, payload: dict) -> Smtp:
        row = Smtp(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Smtp) -> Smtp:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Smtp) -> None:
        self.db.delete(row)
        self.db.commit()

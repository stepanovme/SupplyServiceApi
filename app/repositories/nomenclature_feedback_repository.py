from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureFeedback, NomenclatureFeedbackFile


class NomenclatureFeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureFeedback:
        row = NomenclatureFeedback(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, feedback_id: str) -> NomenclatureFeedback | None:
        return self.db.query(NomenclatureFeedback).filter(NomenclatureFeedback.id == feedback_id).first()

    def get_by_nomenclature(self, nomenclature_id: str) -> list[NomenclatureFeedback]:
        return (
            self.db.query(NomenclatureFeedback)
            .filter(NomenclatureFeedback.nomenclature_id == nomenclature_id)
            .order_by(NomenclatureFeedback.created_at.desc())
            .all()
        )

    def update(self, feedback_id: str, payload: dict) -> NomenclatureFeedback | None:
        row = self.get_by_id(feedback_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, feedback_id: str) -> bool:
        row = self.get_by_id(feedback_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def create_file(self, payload: dict) -> NomenclatureFeedbackFile:
        row = NomenclatureFeedbackFile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_files(self, feedback_id: str) -> list[NomenclatureFeedbackFile]:
        return (
            self.db.query(NomenclatureFeedbackFile)
            .filter(NomenclatureFeedbackFile.nomenclature_feedback_id == feedback_id)
            .order_by(NomenclatureFeedbackFile.uploaded_at.desc())
            .all()
        )

    def get_files_by_feedback_ids(self, feedback_ids: list[str]) -> list[NomenclatureFeedbackFile]:
        if not feedback_ids:
            return []
        return (
            self.db.query(NomenclatureFeedbackFile)
            .filter(NomenclatureFeedbackFile.nomenclature_feedback_id.in_(feedback_ids))
            .order_by(NomenclatureFeedbackFile.uploaded_at.desc())
            .all()
        )

    def get_file(self, feedback_id: str, file_id: str) -> NomenclatureFeedbackFile | None:
        return (
            self.db.query(NomenclatureFeedbackFile)
            .filter(
                NomenclatureFeedbackFile.id == file_id,
                NomenclatureFeedbackFile.nomenclature_feedback_id == feedback_id,
            )
            .first()
        )

    def get_file_by_id(self, file_id: str) -> NomenclatureFeedbackFile | None:
        return self.db.query(NomenclatureFeedbackFile).filter(NomenclatureFeedbackFile.id == file_id).first()

    def delete_file(self, file_row: NomenclatureFeedbackFile) -> None:
        self.db.delete(file_row)
        self.db.commit()

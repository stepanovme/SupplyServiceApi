from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureCompetitor, NomenclatureCompetitorFile


class NomenclatureCompetitorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureCompetitor:
        row = NomenclatureCompetitor(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, competitor_id: str) -> NomenclatureCompetitor | None:
        return self.db.query(NomenclatureCompetitor).filter(NomenclatureCompetitor.id == competitor_id).first()

    def get_by_nomenclature(self, nomenclature_id: str) -> list[NomenclatureCompetitor]:
        return (
            self.db.query(NomenclatureCompetitor)
            .filter(NomenclatureCompetitor.nomenclature_id == nomenclature_id)
            .order_by(NomenclatureCompetitor.created_at.desc())
            .all()
        )

    def update(self, competitor_id: str, payload: dict) -> NomenclatureCompetitor | None:
        row = self.get_by_id(competitor_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, competitor_id: str) -> bool:
        row = self.get_by_id(competitor_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def create_file(self, payload: dict) -> NomenclatureCompetitorFile:
        row = NomenclatureCompetitorFile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_competitor_files(self, competitor_id: str) -> list[NomenclatureCompetitorFile]:
        return (
            self.db.query(NomenclatureCompetitorFile)
            .filter(NomenclatureCompetitorFile.nomenclature_competitor_id == competitor_id)
            .order_by(NomenclatureCompetitorFile.uploaded_at.desc())
            .all()
        )

    def get_files_by_competitor_ids(self, competitor_ids: list[str]) -> list[NomenclatureCompetitorFile]:
        if not competitor_ids:
            return []
        return (
            self.db.query(NomenclatureCompetitorFile)
            .filter(NomenclatureCompetitorFile.nomenclature_competitor_id.in_(competitor_ids))
            .order_by(NomenclatureCompetitorFile.uploaded_at.desc())
            .all()
        )

    def get_competitor_file(self, competitor_id: str, file_id: str) -> NomenclatureCompetitorFile | None:
        return (
            self.db.query(NomenclatureCompetitorFile)
            .filter(
                NomenclatureCompetitorFile.id == file_id,
                NomenclatureCompetitorFile.nomenclature_competitor_id == competitor_id,
            )
            .first()
        )

    def get_file_by_id(self, file_id: str) -> NomenclatureCompetitorFile | None:
        return self.db.query(NomenclatureCompetitorFile).filter(NomenclatureCompetitorFile.id == file_id).first()

    def delete_file(self, file_row: NomenclatureCompetitorFile) -> None:
        self.db.delete(file_row)
        self.db.commit()

    def get_file_type_by_code(self, code: str):
        from app.models.request_file import FileType
        return (
            self.db.query(FileType)
            .filter(
                FileType.code == code,
                FileType.is_active.is_(True),
            )
            .first()
        )

from sqlalchemy.orm import Session

from app.models.request_file import FileAudit, FileDB, FileType, NomenclatureFile, RequestFile
from app.models.supply_request import NomenclatureRef, SupplyRequest


class RequestFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_exists(self, request_id: int) -> bool:
        return self.db.query(SupplyRequest.id).filter(SupplyRequest.id == request_id).first() is not None

    def nomenclature_exists(self, nomenclature_id: str) -> bool:
        return (
            self.db.query(NomenclatureRef.id)
            .filter(NomenclatureRef.id == nomenclature_id)
            .first()
            is not None
        )

    def get_request_attachment_type(self) -> FileType | None:
        return (
            self.db.query(FileType)
            .filter(
                FileType.code == "request_attachment",
                FileType.is_active.is_(True),
            )
            .first()
        )

    def get_file_type_by_id(self, file_type_id: str) -> FileType | None:
        return (
            self.db.query(FileType)
            .filter(
                FileType.id == file_type_id,
                FileType.is_active.is_(True),
            )
            .first()
        )

    def create_file_and_link(self, file_row: FileDB, request_file_row: RequestFile) -> FileDB:
        self.db.add(file_row)
        self.db.add(request_file_row)
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def create_file_and_nomenclature_link(
        self,
        file_row: FileDB,
        nomenclature_file_row: NomenclatureFile,
    ) -> FileDB:
        self.db.add(file_row)
        self.db.add(nomenclature_file_row)
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def create_file(self, file_row: FileDB) -> FileDB:
        self.db.add(file_row)
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def get_request_files(self, request_id: int, link_type: str | None = None):
        query = (
            self.db.query(RequestFile, FileDB, FileType)
            .join(FileDB, FileDB.id == RequestFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                RequestFile.request_id == request_id,
                FileDB.status == "active",
            )
        )
        if link_type:
            query = query.filter(RequestFile.link_type == link_type)

        rows = (
            query
            .order_by(RequestFile.sort_order.asc(), RequestFile.created_at.desc())
            .all()
        )
        return rows

    def get_request_file(self, request_id: int, file_id: str):
        row = (
            self.db.query(RequestFile, FileDB, FileType)
            .join(FileDB, FileDB.id == RequestFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                RequestFile.request_id == request_id,
                RequestFile.file_id == file_id,
                FileDB.status == "active",
            )
            .first()
        )
        return row

    def get_nomenclature_files(self, nomenclature_id: str):
        return (
            self.db.query(NomenclatureFile, FileDB, FileType)
            .join(FileDB, FileDB.id == NomenclatureFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                NomenclatureFile.nomenclature_id == nomenclature_id,
                FileDB.status == "active",
            )
            .order_by(NomenclatureFile.created_at.desc())
            .all()
        )

    def get_nomenclature_file(self, nomenclature_id: str, file_id: str):
        return (
            self.db.query(NomenclatureFile, FileDB, FileType)
            .join(FileDB, FileDB.id == NomenclatureFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                NomenclatureFile.nomenclature_id == nomenclature_id,
                NomenclatureFile.file_id == file_id,
                FileDB.status == "active",
            )
            .first()
        )

    def add_audit(self, audit: FileAudit) -> None:
        self.db.add(audit)
        self.db.commit()

    def mark_file_deleted(self, file_row: FileDB) -> None:
        file_row.status = "deleted"
        self.db.commit()

    def get_file_by_id(self, file_id: str) -> FileDB | None:
        return (
            self.db.query(FileDB)
            .filter(
                FileDB.id == file_id,
                FileDB.status == "active",
            )
            .first()
        )

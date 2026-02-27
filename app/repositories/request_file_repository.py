from sqlalchemy.orm import Session

from app.models.request_file import FileAudit, FileDB, FileType, RequestFile
from app.models.supply_request import SupplyRequest


class RequestFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def request_exists(self, request_id: int) -> bool:
        return self.db.query(SupplyRequest.id).filter(SupplyRequest.id == request_id).first() is not None

    def get_request_attachment_type(self) -> FileType | None:
        return (
            self.db.query(FileType)
            .filter(
                FileType.code == "request_attachment",
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

    def get_request_files(self, request_id: int):
        rows = (
            self.db.query(RequestFile, FileDB, FileType)
            .join(FileDB, FileDB.id == RequestFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(RequestFile.request_id == request_id)
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

    def add_audit(self, audit: FileAudit) -> None:
        self.db.add(audit)
        self.db.commit()

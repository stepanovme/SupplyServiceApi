import uuid

from sqlalchemy.orm import Session

from app.models.contract import ContractLog
from app.models.letter import (
    Letter,
    LetterFile,
    LetterFolder,
    LetterObject,
    LetterStatus,
    LetterUserRole,
    msk_now,
)


class LetterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Letter ---

    def get_letter_by_id(self, letter_id: int) -> Letter | None:
        return self.db.query(Letter).filter(Letter.id == letter_id).first()

    def get_letters(self, letter_type: str | None = None) -> list[Letter]:
        q = self.db.query(Letter)
        if letter_type is not None:
            q = q.filter(Letter.type == letter_type)
        return q.order_by(Letter.id.desc()).all()

    def get_letters_by_ids(self, letter_ids: list[int]) -> list[Letter]:
        if not letter_ids:
            return []
        return self.db.query(Letter).filter(Letter.id.in_(letter_ids)).order_by(Letter.id.desc()).all()

    def get_letter_ids_by_user(self, user_id: str) -> list[int]:
        from sqlalchemy import union
        created_q = self.db.query(Letter.id).filter(Letter.created_by == user_id)
        role_q = self.db.query(LetterUserRole.letter_id).filter(LetterUserRole.user_id == user_id)
        union_q = union(created_q, role_q).subquery()
        rows = self.db.query(Letter.id).filter(Letter.id.in_(union_q)).all()
        return [row[0] for row in rows]

    def count_letters(self, counterparty_id: str | None = None, column: str | None = None, letter_type: str | None = None) -> int:
        from sqlalchemy import func
        q = self.db.query(func.count(Letter.id))
        if counterparty_id and column:
            col = getattr(Letter, column)
            q = q.filter(col == counterparty_id)
        if letter_type:
            q = q.filter(Letter.type == letter_type)
        return q.scalar() or 0

    def create_letter(self, payload: dict) -> Letter:
        row = Letter(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_letter(self, row: Letter) -> Letter:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_letter(self, row: Letter) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- LetterFolder ---

    def get_folders(self, letter_id: int | None = None) -> list[LetterFolder]:
        q = self.db.query(LetterFolder)
        if letter_id is not None:
            q = q.filter(LetterFolder.letter_id == letter_id)
        return q.order_by(LetterFolder.created_at.asc()).all()

    def get_folder_by_id(self, folder_id: str) -> LetterFolder | None:
        return self.db.query(LetterFolder).filter(LetterFolder.id == folder_id).first()

    def create_folder(self, payload: dict) -> LetterFolder:
        row = LetterFolder(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_folder(self, row: LetterFolder) -> LetterFolder:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_folder(self, row: LetterFolder) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- LetterFile ---

    def get_files(
        self, letter_id: int | None = None, folder_id: str | None = None
    ) -> list[LetterFile]:
        q = self.db.query(LetterFile)
        if letter_id is not None:
            q = q.filter(LetterFile.letter_id == letter_id)
        if folder_id is not None:
            q = q.filter(LetterFile.letter_folder_id == folder_id)
        return q.order_by(LetterFile.uploaded_at.desc()).all()

    def get_files_history(self, letter_id: int) -> list[LetterFile]:
        return (
            self.db.query(LetterFile)
            .filter(
                LetterFile.letter_id == letter_id,
                LetterFile.type.in_(["original", "version"]),
            )
            .order_by(LetterFile.uploaded_at.desc())
            .all()
        )

    def get_files_by_letter_ids(self, letter_ids: list[int]) -> list[LetterFile]:
        if not letter_ids:
            return []
        return (
            self.db.query(LetterFile)
            .filter(LetterFile.letter_id.in_(letter_ids))
            .order_by(LetterFile.uploaded_at.desc())
            .all()
        )

    def get_file_by_id(self, file_id: str) -> LetterFile | None:
        return self.db.query(LetterFile).filter(LetterFile.id == file_id).first()

    def create_file(self, payload: dict) -> LetterFile:
        row = LetterFile(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_file(self, row: LetterFile) -> LetterFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: LetterFile) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- LetterObject ---

    def get_objects(self, letter_id: int | None = None) -> list[LetterObject]:
        q = self.db.query(LetterObject)
        if letter_id is not None:
            q = q.filter(LetterObject.letter_id == letter_id)
        return q.order_by(LetterObject.created_at.asc()).all()

    def get_object_by_id(self, obj_id: int) -> LetterObject | None:
        return self.db.query(LetterObject).filter(LetterObject.id == obj_id).first()

    def create_object(self, payload: dict) -> LetterObject:
        row = LetterObject(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_object(self, row: LetterObject) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- LetterStatus ---

    def get_statuses(self, letter_id: int | None = None) -> list[LetterStatus]:
        q = self.db.query(LetterStatus)
        if letter_id is not None:
            q = q.filter(LetterStatus.letter_id == letter_id)
        return q.order_by(LetterStatus.created_at.desc()).all()

    def get_status_by_id(self, status_id: int) -> LetterStatus | None:
        return self.db.query(LetterStatus).filter(LetterStatus.id == status_id).first()

    def create_status(self, payload: dict) -> LetterStatus:
        row = LetterStatus(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_status(self, row: LetterStatus) -> LetterStatus:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_status(self, row: LetterStatus) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- LetterUserRole ---

    def get_user_roles(self, letter_id: int | None = None, role: str | None = None) -> list[LetterUserRole]:
        q = self.db.query(LetterUserRole)
        if letter_id is not None:
            q = q.filter(LetterUserRole.letter_id == letter_id)
        if role is not None:
            q = q.filter(LetterUserRole.role == role)
        return q.order_by(LetterUserRole.created_at.desc()).all()

    def get_user_role_by_id(self, role_id: str) -> LetterUserRole | None:
        return self.db.query(LetterUserRole).filter(LetterUserRole.id == role_id).first()

    def create_user_role(self, payload: dict) -> LetterUserRole:
        row = LetterUserRole(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_user_role(self, row: LetterUserRole) -> LetterUserRole:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user_role(self, row: LetterUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- Logging ---

    def create_log(self, log_object_id: str, message: str, created_by: str) -> ContractLog:
        row = ContractLog(
            id=str(uuid.uuid4()),
            log_object_id=log_object_id,
            log_object_type="letter",
            message=message,
            created_at=msk_now(),
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_logs_by_letter(self, letter_id: int) -> None:
        self.db.query(ContractLog).filter(
            ContractLog.log_object_id == letter_id,
            ContractLog.log_object_type == "letter",
        ).delete()
        self.db.commit()

    def get_logs(
        self,
        log_object_id: str | None = None,
        created_by: str | None = None,
    ) -> list[ContractLog]:
        q = self.db.query(ContractLog).filter(ContractLog.log_object_type == "letter")
        if log_object_id is not None:
            q = q.filter(ContractLog.log_object_id == log_object_id)
        if created_by is not None:
            q = q.filter(ContractLog.created_by == created_by)
        return q.order_by(ContractLog.created_at.desc()).all()

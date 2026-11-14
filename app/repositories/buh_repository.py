import uuid

from sqlalchemy.orm import Session

from app.models.buh import BuhAccess, BuhFile, BuhFolder
from app.database import msk_now


class BuhFolderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[BuhFolder]:
        return self.db.query(BuhFolder).order_by(BuhFolder.name).all()

    def get_by_id(self, folder_id: str) -> BuhFolder | None:
        return self.db.query(BuhFolder).filter(BuhFolder.id == folder_id).first()

    def get_children(self, parent_id: str | None) -> list[BuhFolder]:
        query = self.db.query(BuhFolder)
        if parent_id is None:
            query = query.filter(BuhFolder.parent_id.is_(None))
        else:
            query = query.filter(BuhFolder.parent_id == parent_id)
        return query.order_by(BuhFolder.name).all()

    def create(self, data: dict) -> BuhFolder:
        item = BuhFolder(id=str(uuid.uuid4()), **data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: BuhFolder) -> BuhFolder:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: BuhFolder) -> None:
        self.db.delete(item)
        self.db.commit()

    def delete_by_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        self.db.query(BuhFolder).filter(BuhFolder.id.in_(ids)).delete(synchronize_session="fetch")
        self.db.commit()


class BuhFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self, folder_id: str | None = None) -> list[BuhFile]:
        query = self.db.query(BuhFile)
        if folder_id is not None:
            query = query.filter(BuhFile.folder_id == folder_id)
        else:
            query = query.filter(BuhFile.folder_id.is_(None))
        return query.order_by(BuhFile.uploaded_at.desc()).all()

    def get_all_files(self) -> list[BuhFile]:
        return self.db.query(BuhFile).order_by(BuhFile.uploaded_at.desc()).all()

    def get_by_id(self, file_id: str) -> BuhFile | None:
        return self.db.query(BuhFile).filter(BuhFile.id == file_id).first()

    def get_by_folder_ids(self, folder_ids: list[str]) -> list[BuhFile]:
        if not folder_ids:
            return []
        return self.db.query(BuhFile).filter(BuhFile.folder_id.in_(folder_ids)).all()

    def get_by_uploaded_by(self, user_id: str) -> list[BuhFile]:
        return self.db.query(BuhFile).filter(BuhFile.uploaded_by == user_id).all()

    def get_by_ids(self, file_ids: list[str]) -> list[BuhFile]:
        if not file_ids:
            return []
        return self.db.query(BuhFile).filter(BuhFile.id.in_(file_ids)).all()

    def create(self, data: dict) -> BuhFile:
        item = BuhFile(id=str(uuid.uuid4()), **data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: BuhFile) -> BuhFile:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: BuhFile) -> None:
        self.db.delete(item)
        self.db.commit()

    def delete_by_folder_ids(self, folder_ids: list[str]) -> None:
        if not folder_ids:
            return
        self.db.query(BuhFile).filter(BuhFile.folder_id.in_(folder_ids)).delete(synchronize_session="fetch")
        self.db.commit()


class BuhAccessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[BuhAccess]:
        return self.db.query(BuhAccess).order_by(BuhAccess.created_at.desc()).all()

    def get_by_id(self, access_id: str) -> BuhAccess | None:
        return self.db.query(BuhAccess).filter(BuhAccess.id == access_id).first()

    def get_by_user_id(self, user_id: str) -> list[BuhAccess]:
        return self.db.query(BuhAccess).filter(BuhAccess.user_id == user_id).all()

    def get_user_ids_with_access(self) -> list[str]:
        rows = (
            self.db.query(BuhAccess.user_id)
            .filter(BuhAccess.user_id.isnot(None))
            .distinct()
            .all()
        )
        return [row[0] for row in rows if row[0]]

    def get_department_ids_with_access(self) -> list[int]:
        rows = (
            self.db.query(BuhAccess.department_id)
            .filter(BuhAccess.department_id.isnot(None))
            .distinct()
            .all()
        )
        return [row[0] for row in rows if row[0] is not None]

    def has_global_access(self) -> bool:
        return (
            self.db.query(BuhAccess)
            .filter(BuhAccess.user_id == "__all__")
            .first()
            is not None
        )

    def create(self, data: dict) -> BuhAccess:
        item = BuhAccess(id=str(uuid.uuid4()), **data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: BuhAccess) -> None:
        self.db.delete(item)
        self.db.commit()

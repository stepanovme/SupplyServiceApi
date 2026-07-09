import uuid

from sqlalchemy.orm import Session

from app.models.wiki_file import WikiFile


class WikiFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> WikiFile:
        row = WikiFile(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, file_id: str) -> WikiFile | None:
        return self.db.query(WikiFile).filter(WikiFile.id == file_id).first()

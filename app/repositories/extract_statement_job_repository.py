from sqlalchemy.orm import Session

from app.models.extract_statement_job import ExtractStatementJob


class ExtractStatementJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, job_id: str) -> ExtractStatementJob | None:
        return self.db.query(ExtractStatementJob).filter(ExtractStatementJob.id == job_id).first()

    def get_list(self, settings_api_bank_id: str | None = None, limit: int = 50, offset: int = 0) -> list[ExtractStatementJob]:
        q = self.db.query(ExtractStatementJob)
        if settings_api_bank_id is not None:
            q = q.filter(ExtractStatementJob.settings_api_bank_id == settings_api_bank_id)
        return q.order_by(ExtractStatementJob.created_at.desc()).offset(offset).limit(limit).all()

    def create(self, row: ExtractStatementJob) -> ExtractStatementJob:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ExtractStatementJob) -> ExtractStatementJob:
        self.db.commit()
        self.db.refresh(row)
        return row

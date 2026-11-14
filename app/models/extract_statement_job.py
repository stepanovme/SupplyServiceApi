from datetime import date, datetime, timedelta

from sqlalchemy import CHAR, Column, Date, DateTime, Enum, Integer, JSON, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ExtractStatementJob(SupplyBase):
    __tablename__ = "extract_statement_jobs"

    id = Column(CHAR(36), primary_key=True)
    settings_api_bank_id = Column(CHAR(36), nullable=False, index=True)
    account_number = Column(String(50), nullable=False)
    statement_date_from = Column(Date, nullable=False)
    statement_date_to = Column(Date, nullable=False)
    status = Column(Enum("pending", "running", "completed", "failed"), nullable=False, default="pending")
    days_requested = Column(Integer, nullable=False, default=0)
    days_processed = Column(Integer, nullable=False, default=0)
    days_succeeded = Column(Integer, nullable=False, default=0)
    days_failed = Column(Integer, nullable=False, default=0)
    current_date_processing = Column(Date, nullable=True)
    fetched = Column(Integer, nullable=False, default=0)
    created_count = Column(Integer, nullable=False, default=0)
    skipped_duplicates = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)

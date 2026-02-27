from datetime import datetime

from sqlalchemy import JSON, CHAR, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class FileType(SupplyBase):
    __tablename__ = "file_types"

    id = Column(CHAR(36), primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    allowed_extensions = Column(JSON, nullable=True)
    max_size_mb = Column(Integer, nullable=True, default=10)
    is_active = Column(Boolean, nullable=True, default=True)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)


class FileDB(SupplyBase):
    __tablename__ = "files"

    id = Column(CHAR(36), primary_key=True)
    original_name = Column(String(512), nullable=False)
    storage_name = Column(String(255), nullable=False, unique=True)
    file_type_id = Column(CHAR(36), ForeignKey("file_types.id"), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    extension = Column(String(20), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    md5_hash = Column(String(32), nullable=True)
    file_path = Column(String(512), nullable=False)
    version = Column(Integer, nullable=True, default=1)
    parent_file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=True, index=True)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    status = Column(String(20), nullable=True, default="active")


class RequestFile(SupplyBase):
    __tablename__ = "request_files"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=False, index=True)
    link_type = Column(String(20), nullable=False, default="attachment")
    description = Column(Text, nullable=True)
    is_main = Column(Boolean, nullable=True, default=False)
    sort_order = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=True, index=True)


class FileAudit(SupplyBase):
    __tablename__ = "file_audit"

    id = Column(CHAR(36), primary_key=True)
    file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    user_id = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)

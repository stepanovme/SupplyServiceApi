"""Shared EDO exchange state; document data is a snapshot, not a live foreign row."""
from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import DeclarativeBase


class EdoBase(DeclarativeBase):
    pass


class EdoParticipant(EdoBase):
    __tablename__ = "edo_participants"
    id = Column(CHAR(36), primary_key=True)
    tenant = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


class EdoRelationship(EdoBase):
    __tablename__ = "edo_relationships"
    id = Column(CHAR(36), primary_key=True)
    participant_low = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    participant_high = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    invited_by = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    status = Column(String(16), nullable=False)
    created_by = Column(String(36), nullable=False)
    decided_by = Column(String(36))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    decided_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("participant_low", "participant_high", name="uq_edo_pair"),)


class EdoDocument(EdoBase):
    __tablename__ = "edo_documents"
    id = Column(CHAR(36), primary_key=True)
    relationship_id = Column(CHAR(36), ForeignKey("edo_relationships.id"), nullable=False, index=True)
    sender_id = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    recipient_id = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    document_type = Column(String(16), nullable=False)
    source_id = Column(String(36), nullable=False)
    snapshot = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False)
    sent_by = Column(String(36), nullable=False)
    decided_by = Column(String(36))
    decision_comment = Column(Text)
    sent_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    decided_at = Column(DateTime)
    __table_args__ = (Index("ix_edo_recipient_status", "recipient_id", "status"),)


class EdoFile(EdoBase):
    __tablename__ = "edo_files"
    id = Column(CHAR(36), primary_key=True)
    document_id = Column(CHAR(36), ForeignKey("edo_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    data = Column(LONGBLOB, nullable=False)
    size = Column(Integer, nullable=False)
    sha256 = Column(CHAR(64), nullable=False)


class EdoEvent(EdoBase):
    __tablename__ = "edo_events"
    id = Column(CHAR(36), primary_key=True)
    object_type = Column(String(16), nullable=False)
    object_id = Column(CHAR(36), nullable=False)
    participant_id = Column(CHAR(36), ForeignKey("edo_participants.id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    action = Column(String(32), nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (Index("ix_edo_events_object", "object_type", "object_id"),)

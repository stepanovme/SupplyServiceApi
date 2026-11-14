import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Integer, String

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


DOCUMENT_TYPES = ("contract", "act", "letter_outgoing", "letter_incoming", "document", "upd")

# ── Block definitions per document type ──────────────────────────────────────

CONTRACT_BLOCKS = [
    "parties", "requisites", "dates", "financial",
    "object", "work_types", "responsible", "notes",
    "files", "tasks", "history",
]

ACT_BLOCKS = [
    "parties", "requisites", "financial",
    "object", "responsible", "files", "history",
]

LETTER_OUTGOING_BLOCKS = [
    "parties", "requisites", "object", "responsible",
    "notes", "constructor", "files", "tasks", "history",
]

LETTER_INCOMING_BLOCKS = [
    "parties", "requisites", "object", "responsible",
    "notes", "constructor", "files", "tasks", "history",
]

DOCUMENT_BLOCKS = [
    "files", "history",
]

UPD_BLOCKS = [
    "parties", "financial", "object", "responsible", "files", "history",
]

BLOCKS_BY_TYPE = {
    "contract": CONTRACT_BLOCKS,
    "act": ACT_BLOCKS,
    "letter_outgoing": LETTER_OUTGOING_BLOCKS,
    "letter_incoming": LETTER_INCOMING_BLOCKS,
    "document": DOCUMENT_BLOCKS,
    "upd": UPD_BLOCKS,
}


class DocumentAccessSetting(SupplyBase):
    __tablename__ = "document_access_settings"

    id = Column(String(36), primary_key=True)
    document_type = Column(
        Enum("contract", "act", "letter_outgoing", "letter_incoming", "document", "upd",
             name="doc_access_doc_type"),
        nullable=False, index=True,
    )
    user_id = Column(String(36), nullable=True, index=True)
    department_id = Column(Integer, nullable=True, index=True)

    # ── Visibility / Edit / Delete ──
    # "all" = все, "specific" = определённых контрагентов, NULL = без изменений
    visibility_mode = Column(Enum("all", "specific", name="doc_access_mode"), nullable=True)
    edit_mode = Column(Enum("all", "specific", name="doc_access_edit_mode"), nullable=True)
    delete_mode = Column(Enum("all", "specific", name="doc_access_delete_mode"), nullable=True)

    # ── Allowed counterparty IDs (when mode = "specific") ──
    allowed_counterparty_ids = Column(JSON, nullable=True)

    # ── Block visibility (JSON: {"parties": true, "financial": false, ...}) ──
    visible_blocks = Column(JSON, nullable=True)

    # ── Audit ──
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String(36), nullable=True)


# ── Pydantic schemas ─────────────────────────────────────────────────────────

LiteralMode = Literal["all", "specific"]

class DocumentAccessSettingCreate(BaseModel):
    document_type: Literal["contract", "act", "letter_outgoing", "letter_incoming", "document", "upd"]
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    visibility_mode: LiteralMode | None = Field(default=None)
    edit_mode: LiteralMode | None = Field(default=None)
    delete_mode: LiteralMode | None = Field(default=None)
    allowed_counterparty_ids: list[str] | None = Field(default=None)
    visible_blocks: dict[str, bool] | None = Field(default=None)


class DocumentAccessSettingUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    visibility_mode: LiteralMode | None = Field(default=None)
    edit_mode: LiteralMode | None = Field(default=None)
    delete_mode: LiteralMode | None = Field(default=None)
    allowed_counterparty_ids: list[str] | None = Field(default=None)
    visible_blocks: dict[str, bool] | None = Field(default=None)


class DocumentAccessSettingsBulkUpdate(BaseModel):
    """Обновление всех настроек для конкретного пользователя/отдела за раз."""
    settings: list[DocumentAccessSettingCreate]

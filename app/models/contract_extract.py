from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Column, Integer, String

from app.database import SupplyBase


class ContractExtract(SupplyBase):
    __tablename__ = "contract_extracts"

    id = Column(String(36), primary_key=True)
    contract_id = Column(Integer, nullable=False, index=True)
    extract_id = Column(String(36), nullable=False, index=True)


class ContractExtractCreate(BaseModel):
    contract_id: int
    extract_id: str


class ContractExtractUpdate(BaseModel):
    contract_id: int = Field(...)


class ContractExtractMatchAllRequest(BaseModel):
    # Explicit set of extract_items to process - takes priority over date_from/date_to/limit
    # if provided.
    extract_ids: list[str] | None = Field(default=None)
    # Otherwise: pick unmatched extract_items within this operationDate range (both optional).
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=1000)

    @model_validator(mode="after")
    def _check(self):
        if self.extract_ids is not None and len(self.extract_ids) == 0:
            raise ValueError("extract_ids не может быть пустым списком")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from не может быть позже date_to")
        return self

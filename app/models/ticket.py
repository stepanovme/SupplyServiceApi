from __future__ import annotations
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import CHAR, Column, DateTime, Enum, Integer

from app.database import SupplyBase, msk_now


class Ticket(SupplyBase):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum("suggestion", "question", "problem"), nullable=False)
    status_id = Column(CHAR(36), nullable=False)
    chat_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class TicketCreate(BaseModel):
    type: Literal["suggestion", "question", "problem"]
    status_id: str
    chat_id: int | None = None


class TicketUpdate(BaseModel):
    type: Literal["suggestion", "question", "problem"] | None = None
    status_id: str | None = None
    chat_id: int | None = None


class TicketUser(SupplyBase):
    __tablename__ = "tickets_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, nullable=False)
    user_id = Column(CHAR(36), nullable=False)
    role_id = Column(Enum("author", "assignee"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class TicketUserCreate(BaseModel):
    ticket_id: int
    user_id: str
    role_id: Literal["author", "assignee"]


class TicketUserUpdate(BaseModel):
    role_id: Literal["author", "assignee"] | None = None

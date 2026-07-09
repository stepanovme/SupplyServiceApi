import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Enum, Integer, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class Task(SupplyBase):
    __tablename__ = "tasks"

    id = Column(CHAR(36), primary_key=True)
    connection_id = Column(CHAR(36), nullable=True, index=True)
    connection_type = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    object_type = Column(Enum("object_id", "object_levels_id"), nullable=True)
    urgent = Column(Enum("low", "medium", "high", "charred"), nullable=True)
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    date_completed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    status_id = Column(CHAR(36), nullable=False, default="e0896c9d-7646-11f1-b481-bc241127d0bd", index=True)
    vertical_num = Column(Integer, nullable=True)


class TaskItem(SupplyBase):
    __tablename__ = "task_item"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=False, index=True)
    num = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    urgent = Column(Enum("low", "medium", "high", "charred"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    status_id = Column(CHAR(36), nullable=False, default="e0896c9d-7646-11f1-b481-bc241127d0bd", index=True)


class TaskUserRole(SupplyBase):
    __tablename__ = "task_user_roles"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=True, index=True)
    task_item_id = Column(CHAR(36), nullable=True, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("responsible", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class TaskResult(SupplyBase):
    __tablename__ = "task_result"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class TaskFile(SupplyBase):
    __tablename__ = "task_files"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=True, index=True)
    task_result_id = Column(CHAR(36), nullable=True, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class TaskBoard(SupplyBase):
    __tablename__ = "task_boards"

    id = Column(CHAR(36), primary_key=True)
    name = Column(Text, nullable=False)
    object_id = Column(CHAR(36), nullable=False, index=True)
    object_type = Column(Enum("object_id", "object_levels_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class TaskBoardColumn(SupplyBase):
    __tablename__ = "task_boards_columns"

    id = Column(CHAR(36), primary_key=True)
    task_board_id = Column(CHAR(36), nullable=False, index=True)
    num = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class TaskBoardUserRole(SupplyBase):
    __tablename__ = "task_boards_user_roles"

    id = Column(CHAR(36), primary_key=True)
    task_boards_id = Column(CHAR(36), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("responsible", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class TaskAccomplishment(SupplyBase):
    __tablename__ = "task_accomplishment"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=False, index=True)
    date_start = Column(DateTime, nullable=False, default=msk_now)
    date_end = Column(DateTime, nullable=True)
    status_id = Column(CHAR(36), nullable=False, default="6b4fbf85-7901-11f1-b481-bc241127d0bd", index=True)
    date_stop = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)


class TaskTag(SupplyBase):
    __tablename__ = "task_tags"

    id = Column(CHAR(36), primary_key=True)
    task_id = Column(CHAR(36), nullable=False, index=True)
    tag = Column(Text, nullable=False)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


# --- Pydantic schemas ---

class TaskCreate(BaseModel):
    connection_id: str | None = Field(default=None)
    connection_type: str | None = Field(default=None)
    name: str
    description: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object_id", "object_levels_id"] | None = Field(default=None)
    urgent: Literal["low", "medium", "high", "charred"] | None = Field(default=None)
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)
    vertical_num: int | None = Field(default=None)


class TaskUpdate(BaseModel):
    connection_id: str | None = Field(default=None)
    connection_type: str | None = Field(default=None)
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object_id", "object_levels_id"] | None = Field(default=None)
    urgent: Literal["low", "medium", "high", "charred"] | None = Field(default=None)
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)
    vertical_num: int | None = Field(default=None)


class TaskItemCreate(BaseModel):
    task_id: str
    num: int
    name: str
    urgent: Literal["low", "medium", "high", "charred"] | None = Field(default=None)
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)


class TaskItemUpdate(BaseModel):
    num: int | None = Field(default=None)
    name: str | None = Field(default=None)
    urgent: Literal["low", "medium", "high", "charred"] | None = Field(default=None)
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)


class TaskUserRoleCreate(BaseModel):
    task_id: str | None = Field(default=None)
    task_item_id: str | None = Field(default=None)
    user_id: str
    role: Literal["responsible", "co-executor", "observer"]


class TaskUserRoleUpdate(BaseModel):
    task_id: str | None = Field(default=None)
    task_item_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    role: Literal["responsible", "co-executor", "observer"] | None = Field(default=None)


class TaskResultCreate(BaseModel):
    task_id: str
    text: str


class TaskResultUpdate(BaseModel):
    text: str | None = Field(default=None)


class TaskBoardCreate(BaseModel):
    name: str
    object_id: str
    object_type: Literal["object_id", "object_levels_id"]


class TaskBoardUpdate(BaseModel):
    name: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object_id", "object_levels_id"] | None = Field(default=None)


class TaskBoardColumnCreate(BaseModel):
    task_board_id: str
    num: int
    name: str


class TaskBoardColumnUpdate(BaseModel):
    num: int | None = Field(default=None)
    name: str | None = Field(default=None)


class TaskBoardUserRoleCreate(BaseModel):
    task_boards_id: str
    user_id: str
    role: Literal["responsible", "co-executor", "observer"]


class TaskBoardUserRoleUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    role: Literal["responsible", "co-executor", "observer"] | None = Field(default=None)


class TaskTagCreate(BaseModel):
    task_id: str
    tag: str


class TaskTagUpdate(BaseModel):
    tag: str


class TaskAccomplishmentCreate(BaseModel):
    task_id: str
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)
    date_stop: datetime | None = Field(default=None)


class TaskAccomplishmentUpdate(BaseModel):
    date_start: datetime | None = Field(default=None)
    date_end: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)
    date_stop: datetime | None = Field(default=None)

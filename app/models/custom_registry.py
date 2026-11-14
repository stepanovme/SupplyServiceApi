from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, BigInteger, CHAR, Boolean, Column, DateTime, Enum, Integer, String, Text

from app.database import SupplyBase, msk_now

FIELD_TYPES = ("text", "textarea", "number", "money", "date", "boolean", "select", "multiselect", "counterparty", "user", "object")
FieldType = Literal["text", "textarea", "number", "money", "date", "boolean", "select", "multiselect", "counterparty", "user", "object"]


class CustomRegistry(SupplyBase):
    __tablename__ = "custom_registries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class CustomRegistryBlock(SupplyBase):
    __tablename__ = "custom_registry_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registry_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class CustomRegistryField(SupplyBase):
    __tablename__ = "custom_registry_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registry_id = Column(Integer, nullable=False, index=True)
    block_id = Column(Integer, nullable=True, index=True)
    field_key = Column(String(64), nullable=False)
    label = Column(String(200), nullable=False)
    field_type = Column(Enum(*FIELD_TYPES), nullable=False)
    required = Column(Boolean, nullable=False, default=False)
    multiple = Column(Boolean, nullable=False, default=False)
    options = Column(JSON, nullable=True)
    show_in_list = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)


class CustomRegistryRecord(SupplyBase):
    __tablename__ = "custom_registry_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registry_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class CustomRegistryValue(SupplyBase):
    __tablename__ = "custom_registry_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, nullable=False, index=True)
    field_id = Column(Integer, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    search_text = Column(Text, nullable=True)


class CustomRegistryFile(SupplyBase):
    __tablename__ = "custom_registry_files"

    id = Column(CHAR(36), primary_key=True)
    record_id = Column(Integer, nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=False)
    size = Column(BigInteger, nullable=True)
    uploaded_by = Column(CHAR(36), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)


class CustomRegistryHistory(SupplyBase):
    __tablename__ = "custom_registry_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registry_id = Column(Integer, nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    user_id = Column(CHAR(36), nullable=False)
    action = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    changes = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class CustomRegistryAccess(SupplyBase):
    __tablename__ = "custom_registry_access"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=True, index=True)
    department_id = Column(Integer, nullable=True, index=True)
    all_registries = Column(Boolean, nullable=False, default=False)
    registry_ids = Column(JSON, nullable=True)
    can_create_registries = Column(Boolean, nullable=False, default=False)
    can_view = Column(Boolean, nullable=False, default=False)
    can_add_records = Column(Boolean, nullable=False, default=False)
    can_edit_records = Column(Boolean, nullable=False, default=False)
    can_delete_records = Column(Boolean, nullable=False, default=False)
    can_manage_files = Column(Boolean, nullable=False, default=False)
    can_edit_structure = Column(Boolean, nullable=False, default=False)
    can_delete_registry = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


ACCESS_FLAGS = ("can_create_registries", "can_view", "can_add_records", "can_edit_records", "can_delete_records",
                "can_manage_files", "can_edit_structure", "can_delete_registry")


# --- Pydantic schemas ---

class RegistryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Название реестра, например «Накладные» или «Заявки на технику»")
    description: Optional[str] = None


class RegistryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None


class BlockCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BlockUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)


class FieldCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200, description="Название поля, например «Покупатель»")
    field_type: FieldType
    key: Optional[str] = Field(default=None, max_length=64, description="Системное имя (латиница); если не задано - строится из названия")
    block_id: Optional[int] = Field(default=None, description="Блок, в котором стоит поле; null - вне блоков")
    required: bool = False
    multiple: bool = Field(default=False, description="counterparty/user/object: можно выбрать несколько")
    options: Optional[list[str]] = Field(default=None, description="select/multiselect: варианты выбора")
    show_in_list: bool = Field(default=False, description="Показывать колонкой в списке записей")


class FieldUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    block_id: Optional[int] = Field(default=None, description="Перенести в блок; null - вынести из блоков")
    required: Optional[bool] = None
    multiple: Optional[bool] = None
    options: Optional[list[str]] = None
    show_in_list: Optional[bool] = None
    field_type: Optional[FieldType] = Field(default=None, description="Менять тип можно, только пока в поле нет значений")


class LayoutField(BaseModel):
    id: int
    block_id: Optional[int] = None


class LayoutUpdate(BaseModel):
    blocks: Optional[list[int]] = Field(default=None, description="id блоков в нужном порядке")
    fields: Optional[list[LayoutField]] = Field(default=None, description="поля в нужном порядке; block_id - в каком блоке стоит")


class RecordValues(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict, description="{ключ_поля: значение}; null или пустое - очистить поле")


class AccessCreate(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Пользователь (или department_id)")
    department_id: Optional[int] = Field(default=None, description="Отдел (или user_id)")
    all_registries: bool = Field(default=False, description="true - правила действуют на все реестры, включая будущие")
    registry_ids: list[int] = Field(default_factory=list, description="Выбранные реестры (если all_registries=false)")
    can_create_registries: bool = False
    can_view: bool = False
    can_add_records: bool = False
    can_edit_records: bool = False
    can_delete_records: bool = False
    can_manage_files: bool = False
    can_edit_structure: bool = False
    can_delete_registry: bool = False


class AccessUpdate(BaseModel):
    all_registries: Optional[bool] = None
    registry_ids: Optional[list[int]] = None
    can_create_registries: Optional[bool] = None
    can_view: Optional[bool] = None
    can_add_records: Optional[bool] = None
    can_edit_records: Optional[bool] = None
    can_delete_records: Optional[bool] = None
    can_manage_files: Optional[bool] = None
    can_edit_structure: Optional[bool] = None
    can_delete_registry: Optional[bool] = None

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import ReferenceBase


class ObjectLevel(ReferenceBase):
    __tablename__ = "object_levels"

    id = Column(String(36), primary_key=True)
    object_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    level_type = Column(String(20), nullable=False)
    level_number = Column(Integer, nullable=False)
    work_type = Column(String(36), nullable=True)
    contract_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False)
    parent_id = Column(String(36), nullable=True, index=True)


class RefObject(ReferenceBase):
    __tablename__ = "objects"

    id = Column(String(36), primary_key=True)
    short_name = Column(String(255), nullable=True)
    full_name = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)


class ContractRef(ReferenceBase):
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True)
    contract_id = Column(String(36), nullable=True)
    name = Column(Text, nullable=False)


class WorkTypeRef(ReferenceBase):
    __tablename__ = "work_types"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=True)

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


class CounterpartyRef(ReferenceBase):
    __tablename__ = "counterparties"

    id = Column(String(36), primary_key=True)
    short_name = Column(String(255), nullable=True)
    full_name = Column(String(500), nullable=True)
    type = Column(String(10), nullable=True)
    is_internal = Column(Integer, nullable=True)


class DetailsLLC(ReferenceBase):
    __tablename__ = "details_llc"

    id = Column(String(36), primary_key=True)
    counterparties_id = Column(String(36), nullable=False, index=True)
    inn = Column(String(12), nullable=True)
    kpp = Column(String(9), nullable=True)
    ogrn = Column(String(15), nullable=True)
    legal_address = Column(Text, nullable=True)
    director_person_id = Column(String(36), nullable=True)


class DetailsIP(ReferenceBase):
    __tablename__ = "details_ip"

    id = Column(String(36), primary_key=True)
    counterparty_id = Column("counterparty_id", String(36), nullable=False, index=True)
    inn = Column(String(12), nullable=True)
    ogrnip = Column("ogrnip", String(15), nullable=True)
    person_id = Column("person_id", String(36), nullable=True)


class Person(ReferenceBase):
    __tablename__ = "persons"

    id = Column(String(36), primary_key=True)
    last_naem = Column(String(100), nullable=True)
    name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    phone_personal = Column(String(20), nullable=True)
    email_personal = Column(String(100), nullable=True)


class Employee(ReferenceBase):
    __tablename__ = "employees"

    id = Column(String(36), primary_key=True)
    person_id = Column(String(36), nullable=False, index=True)
    counterparty_id = Column(String(36), nullable=False, index=True)
    position = Column(String(255), nullable=True)


class BankAccount(ReferenceBase):
    __tablename__ = "bank_accounts"

    id = Column(String(36), primary_key=True)
    counterparty_id = Column(String(36), nullable=False, index=True)
    bank_name = Column(String(255), nullable=True)
    bik = Column(String(9), nullable=True)
    correspondent_account = Column(String(20), nullable=True)
    account_number = Column(String(20), nullable=True)

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.custom_registry import (
    CustomRegistry, CustomRegistryAccess, CustomRegistryBlock, CustomRegistryField, CustomRegistryFile, CustomRegistryHistory,
    CustomRegistryRecord, CustomRegistryValue,
)


class CustomRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def add(self, row):
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, row) -> None:
        self.db.delete(row)
        self.db.flush()

    # registries
    def list_registries(self) -> list[CustomRegistry]:
        return self.db.query(CustomRegistry).order_by(CustomRegistry.name).all()

    def get_registry(self, registry_id: int) -> CustomRegistry | None:
        return self.db.query(CustomRegistry).filter(CustomRegistry.id == registry_id).first()

    def get_registry_by_name(self, name: str) -> CustomRegistry | None:
        return self.db.query(CustomRegistry).filter(func.lower(CustomRegistry.name) == name.lower()).first()

    def records_counts(self) -> dict[int, int]:
        rows = self.db.query(CustomRegistryRecord.registry_id, func.count(CustomRegistryRecord.id)).group_by(CustomRegistryRecord.registry_id).all()
        return {r[0]: r[1] for r in rows}

    def count_records(self, registry_id: int) -> int:
        return self.db.query(func.count(CustomRegistryRecord.id)).filter(CustomRegistryRecord.registry_id == registry_id).scalar() or 0

    # blocks
    def get_blocks(self, registry_id: int) -> list[CustomRegistryBlock]:
        return self.db.query(CustomRegistryBlock).filter(CustomRegistryBlock.registry_id == registry_id).order_by(CustomRegistryBlock.sort_order, CustomRegistryBlock.id).all()

    def get_block(self, block_id: int) -> CustomRegistryBlock | None:
        return self.db.query(CustomRegistryBlock).filter(CustomRegistryBlock.id == block_id).first()

    # fields
    def get_fields(self, registry_id: int) -> list[CustomRegistryField]:
        return self.db.query(CustomRegistryField).filter(CustomRegistryField.registry_id == registry_id).order_by(CustomRegistryField.sort_order, CustomRegistryField.id).all()

    def get_field(self, field_id: int) -> CustomRegistryField | None:
        return self.db.query(CustomRegistryField).filter(CustomRegistryField.id == field_id).first()

    def count_field_values(self, field_id: int) -> int:
        return self.db.query(func.count(CustomRegistryValue.id)).filter(CustomRegistryValue.field_id == field_id, CustomRegistryValue.value.isnot(None)).scalar() or 0

    # records
    def get_record(self, record_id: int) -> CustomRegistryRecord | None:
        return self.db.query(CustomRegistryRecord).filter(CustomRegistryRecord.id == record_id).first()

    def list_records(self, registry_id: int, q: str | None, limit: int, offset: int):
        query = self.db.query(CustomRegistryRecord).filter(CustomRegistryRecord.registry_id == registry_id)
        if q:
            sub = self.db.query(CustomRegistryValue.record_id).filter(CustomRegistryValue.search_text.ilike(f"%{q}%"))
            query = query.filter(CustomRegistryRecord.id.in_(sub))
        total = query.count()
        rows = query.order_by(CustomRegistryRecord.created_at.desc(), CustomRegistryRecord.id.desc()).offset(offset).limit(limit).all()
        return total, rows

    def get_values(self, record_ids: list[int]) -> dict[int, dict[int, CustomRegistryValue]]:
        result: dict[int, dict[int, CustomRegistryValue]] = {}
        if not record_ids:
            return result
        for v in self.db.query(CustomRegistryValue).filter(CustomRegistryValue.record_id.in_(record_ids)).all():
            result.setdefault(v.record_id, {})[v.field_id] = v
        return result

    def touch(self, row, user_id: str) -> None:
        row.updated_at = msk_now()
        row.updated_by = user_id

    # files
    def get_files(self, record_id: int) -> list[CustomRegistryFile]:
        return self.db.query(CustomRegistryFile).filter(CustomRegistryFile.record_id == record_id).order_by(CustomRegistryFile.uploaded_at.desc(), CustomRegistryFile.id).all()

    def get_file(self, file_id: str) -> CustomRegistryFile | None:
        return self.db.query(CustomRegistryFile).filter(CustomRegistryFile.id == file_id).first()

    def files_counts(self, record_ids: list[int]) -> dict[int, int]:
        if not record_ids:
            return {}
        rows = self.db.query(CustomRegistryFile.record_id, func.count(CustomRegistryFile.id)).filter(CustomRegistryFile.record_id.in_(record_ids)).group_by(CustomRegistryFile.record_id).all()
        return {r[0]: r[1] for r in rows}

    def record_ids(self, registry_id: int) -> list[int]:
        return [r[0] for r in self.db.query(CustomRegistryRecord.id).filter(CustomRegistryRecord.registry_id == registry_id).all()]

    def file_paths_for_registry(self, registry_id: int) -> list[str]:
        sub = self.db.query(CustomRegistryRecord.id).filter(CustomRegistryRecord.registry_id == registry_id)
        return [r[0] for r in self.db.query(CustomRegistryFile.file_path).filter(CustomRegistryFile.record_id.in_(sub)).all()]

    # history
    def add_history(self, registry_id: int, record_id: int | None, user_id: str, action: str, message: str, changes: list | None = None) -> None:
        self.db.add(CustomRegistryHistory(registry_id=registry_id, record_id=record_id, user_id=user_id, action=action, message=message, changes=changes or None))
        self.db.flush()

    def get_history(self, registry_id: int | None, record_id: int | None, limit: int, offset: int):
        query = self.db.query(CustomRegistryHistory)
        if record_id is not None:
            query = query.filter(CustomRegistryHistory.record_id == record_id)
        else:
            query = query.filter(CustomRegistryHistory.registry_id == registry_id)
        return query.count(), query.order_by(CustomRegistryHistory.id.desc()).offset(offset).limit(limit).all()

    def history_registry_of_record(self, record_id: int) -> int | None:
        row = self.db.query(CustomRegistryHistory.registry_id).filter(CustomRegistryHistory.record_id == record_id).first()
        return row[0] if row else None

    # access rules
    def get_access_rules(self, user_id: str | None = None, department_id: int | None = None) -> list[CustomRegistryAccess]:
        query = self.db.query(CustomRegistryAccess)
        if user_id:
            query = query.filter(CustomRegistryAccess.user_id == user_id)
        if department_id:
            query = query.filter(CustomRegistryAccess.department_id == department_id)
        return query.order_by(CustomRegistryAccess.created_at, CustomRegistryAccess.id).all()

    def get_access_rules_for(self, user_id: str, department_ids: list[int]) -> list[CustomRegistryAccess]:
        cond = [CustomRegistryAccess.user_id == user_id]
        if department_ids:
            cond.append(CustomRegistryAccess.department_id.in_(department_ids))
        return self.db.query(CustomRegistryAccess).filter(or_(*cond)).all()

    def get_access_rule(self, rule_id: str) -> CustomRegistryAccess | None:
        return self.db.query(CustomRegistryAccess).filter(CustomRegistryAccess.id == rule_id).first()

    def all_access_rules(self) -> list[CustomRegistryAccess]:
        return self.db.query(CustomRegistryAccess).all()

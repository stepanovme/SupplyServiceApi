import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.supply_request import StatusRef
from app.models.upd_registry import (
    UpdRegistry, UpdRegistryFile, UpdRegistryFolder, UpdRegistryLog,
    UpdRegistryObject, UpdRegistryStatus, UpdRegistryUserRole,
)


class UpdRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- UPD ---
    def get_all(self) -> list[UpdRegistry]:
        return self.db.query(UpdRegistry).order_by(UpdRegistry.created_at.desc(), UpdRegistry.id.desc()).all()

    def get_by_id(self, upd_id: int) -> UpdRegistry | None:
        return self.db.query(UpdRegistry).filter(UpdRegistry.id == upd_id).first()

    def get_by_ids(self, ids: list[int]) -> list[UpdRegistry]:
        if not ids:
            return []
        return self.db.query(UpdRegistry).filter(UpdRegistry.id.in_(ids)).order_by(UpdRegistry.created_at.desc(), UpdRegistry.id.desc()).all()

    def get_ids_by_user(self, user_id: str) -> list[int]:
        rows = self.db.query(UpdRegistryUserRole.upd_id).filter(UpdRegistryUserRole.user_id == user_id).all()
        return [r[0] for r in rows]

    def get_all_ids(self) -> list[int]:
        return [r[0] for r in self.db.query(UpdRegistry.id).all()]

    def get_ids_by_counterparty(self, counterparty_ids: list[str]) -> list[int]:
        if not counterparty_ids:
            return []
        rows = self.db.query(UpdRegistry.id).filter(or_(
            UpdRegistry.buyer_id.in_(counterparty_ids), UpdRegistry.seller_id.in_(counterparty_ids),
            UpdRegistry.shipper_id.in_(counterparty_ids), UpdRegistry.consignee_id.in_(counterparty_ids),
        )).all()
        return [r[0] for r in rows]

    def get_ids_by_object(self, object_id: str) -> list[int]:
        rows = self.db.query(UpdRegistryObject.upd_id).filter(UpdRegistryObject.object_id == object_id).distinct().all()
        return [r[0] for r in rows]

    def create(self, data: dict) -> UpdRegistry:
        row = UpdRegistry(**data)
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, row: UpdRegistry) -> None:
        self.db.delete(row)
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()

    # --- objects ---
    def get_objects(self, upd_id: int) -> list[UpdRegistryObject]:
        return self.db.query(UpdRegistryObject).filter(UpdRegistryObject.upd_id == upd_id).order_by(UpdRegistryObject.id).all()

    def get_objects_by_upd_ids(self, ids: list[int]) -> dict[int, list[UpdRegistryObject]]:
        result: dict[int, list[UpdRegistryObject]] = {}
        if not ids:
            return result
        rows = self.db.query(UpdRegistryObject).filter(UpdRegistryObject.upd_id.in_(ids)).order_by(UpdRegistryObject.id).all()
        for r in rows:
            result.setdefault(r.upd_id, []).append(r)
        return result

    def get_object(self, upd_id: int, obj_id: int) -> UpdRegistryObject | None:
        return self.db.query(UpdRegistryObject).filter(UpdRegistryObject.upd_id == upd_id, UpdRegistryObject.id == obj_id).first()

    def add_object(self, upd_id: int, object_id: str, object_type: str, user_id: str) -> None:
        self.db.add(UpdRegistryObject(upd_id=upd_id, object_id=object_id, object_type=object_type, created_by=user_id))

    def delete_object(self, row: UpdRegistryObject) -> None:
        self.db.delete(row)

    # --- roles ---
    def get_user_roles(self, upd_id: int) -> list[UpdRegistryUserRole]:
        return self.db.query(UpdRegistryUserRole).filter(UpdRegistryUserRole.upd_id == upd_id).order_by(UpdRegistryUserRole.created_at).all()

    def get_user_role(self, role_id: str) -> UpdRegistryUserRole | None:
        return self.db.query(UpdRegistryUserRole).filter(UpdRegistryUserRole.id == role_id).first()

    def create_user_role(self, upd_id: int, user_id: str, role: str, created_by: str) -> UpdRegistryUserRole:
        row = UpdRegistryUserRole(id=str(uuid.uuid4()), upd_id=upd_id, user_id=user_id, role=role, created_by=created_by)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_user_role(self, row: UpdRegistryUserRole, data: dict) -> UpdRegistryUserRole:
        for k, v in data.items():
            setattr(row, k, v)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user_role(self, row: UpdRegistryUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- statuses ---
    def create_status(self, upd_id: int, status_id: str, created_by: str) -> UpdRegistryStatus:
        row = UpdRegistryStatus(id=str(uuid.uuid4()), upd_id=upd_id, status_id=status_id, created_by=created_by)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_statuses(self, upd_id: int) -> list[UpdRegistryStatus]:
        return self.db.query(UpdRegistryStatus).filter(UpdRegistryStatus.upd_id == upd_id).order_by(UpdRegistryStatus.created_at.desc(), UpdRegistryStatus.id).all()

    def get_current_status(self, upd_id: int) -> UpdRegistryStatus | None:
        rows = self.get_statuses(upd_id)
        return rows[0] if rows else None

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        if not status_ids:
            return {}
        rows = self.db.query(StatusRef).filter(StatusRef.id.in_(status_ids)).all()
        return {r.id: r.name for r in rows}

    # --- folders ---
    def get_folders(self, upd_id: int) -> list[UpdRegistryFolder]:
        return self.db.query(UpdRegistryFolder).filter(UpdRegistryFolder.upd_id == upd_id).order_by(UpdRegistryFolder.created_at).all()

    def get_folder(self, folder_id: str) -> UpdRegistryFolder | None:
        return self.db.query(UpdRegistryFolder).filter(UpdRegistryFolder.id == folder_id).first()

    def create_folder(self, upd_id: int, name: str, created_by: str, parent_id: str | None) -> UpdRegistryFolder:
        row = UpdRegistryFolder(id=str(uuid.uuid4()), upd_id=upd_id, name=name, parent_id=parent_id, created_by=created_by)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_folder(self, row: UpdRegistryFolder, data: dict) -> UpdRegistryFolder:
        for k, v in data.items():
            setattr(row, k, v)
        row.updated_at = msk_now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_folder(self, row: UpdRegistryFolder) -> None:
        self.db.query(UpdRegistryFile).filter(UpdRegistryFile.folder_id == row.id).update({"folder_id": row.parent_id})
        self.db.query(UpdRegistryFolder).filter(UpdRegistryFolder.parent_id == row.id).update({"parent_id": row.parent_id})
        self.db.delete(row)
        self.db.commit()

    # --- files ---
    def get_files(self, upd_id: int) -> list[UpdRegistryFile]:
        return self.db.query(UpdRegistryFile).filter(UpdRegistryFile.upd_id == upd_id).order_by(UpdRegistryFile.uploaded_at.desc()).all()

    def get_file(self, file_id: str) -> UpdRegistryFile | None:
        return self.db.query(UpdRegistryFile).filter(UpdRegistryFile.id == file_id).first()

    def create_file(self, data: dict) -> UpdRegistryFile:
        row = UpdRegistryFile(**data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_file(self, row: UpdRegistryFile, data: dict) -> UpdRegistryFile:
        for k, v in data.items():
            setattr(row, k, v)
        row.updated_at = msk_now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: UpdRegistryFile) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- log ---
    def add_log(self, upd_id: int, user_id: str, message: str) -> None:
        self.db.add(UpdRegistryLog(id=str(uuid.uuid4()), upd_id=upd_id, user_id=user_id, message=message))
        self.db.commit()

    def get_logs(self, upd_id: int) -> list[UpdRegistryLog]:
        return self.db.query(UpdRegistryLog).filter(UpdRegistryLog.upd_id == upd_id).order_by(UpdRegistryLog.seq.desc()).all()

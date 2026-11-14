import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.documents_link import DocumentsLink
from app.models.act import (
    Act,
    ActObject,
    ActFile,
    ActFolder,
    ActStatus,
    ActType,
    ActUserRole,
)
from app.models.supply_request import StatusRef


class ActRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Act types ---

    def get_act_types(self) -> list[ActType]:
        return self.db.query(ActType).order_by(ActType.id).all()

    def get_act_type(self, act_type_id: int) -> ActType | None:
        return self.db.query(ActType).filter(ActType.id == act_type_id).first()

    def create_act_type(self, payload: dict) -> ActType:
        row = ActType(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # --- Acts ---

    def get_all(self) -> list[Act]:
        return self.db.query(Act).order_by(Act.created_at.desc(), Act.id.desc()).all()

    def get_by_id(self, act_id: int) -> Act | None:
        return self.db.query(Act).filter(Act.id == act_id).first()

    def get_contract_act_links(self, contract_id: int) -> dict[int, DocumentsLink]:
        """act id -> its documents_links row for the given contract. A link may have been saved in
        either order (act first or contract first), so both are looked at; if an act is linked
        more than once the earliest link is kept."""
        cid = str(contract_id)
        rows = (
            self.db.query(DocumentsLink)
            .filter(
                or_(
                    and_(
                        DocumentsLink.document_type_first == "act",
                        DocumentsLink.document_type_second == "contract",
                        DocumentsLink.document_linked_second == cid,
                    ),
                    and_(
                        DocumentsLink.document_type_first == "contract",
                        DocumentsLink.document_type_second == "act",
                        DocumentsLink.document_linked_first == cid,
                    ),
                )
            )
            .order_by(DocumentsLink.created_at, DocumentsLink.id)
            .all()
        )
        result: dict[int, DocumentsLink] = {}
        for link in rows:
            act_ref = link.document_linked_first if link.document_type_first == "act" else link.document_linked_second
            if str(act_ref).isdigit():
                result.setdefault(int(act_ref), link)
        return result

    # --- Act objects ---

    def get_objects(self, act_id: int) -> list[ActObject]:
        return self.db.query(ActObject).filter(ActObject.act_id == act_id).order_by(ActObject.id).all()

    def get_objects_by_act_ids(self, act_ids: list[int]) -> dict[int, list[ActObject]]:
        if not act_ids:
            return {}
        result: dict[int, list[ActObject]] = {}
        for row in self.db.query(ActObject).filter(ActObject.act_id.in_(act_ids)).order_by(ActObject.id).all():
            result.setdefault(row.act_id, []).append(row)
        return result

    def get_object_by_id(self, act_id: int, obj_id: int) -> ActObject | None:
        return self.db.query(ActObject).filter(ActObject.act_id == act_id, ActObject.id == obj_id).first()

    def add(self, row) -> None:
        self.db.add(row)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def delete_object(self, row: ActObject) -> None:
        self.db.delete(row)

    def get_acts_by_ids(self, act_ids: list[int]) -> list[Act]:
        if not act_ids:
            return []
        return self.db.query(Act).filter(Act.id.in_(act_ids)).order_by(Act.created_at.desc(), Act.id.desc()).all()

    def get_by_user_id(self, user_id: str) -> list[Act]:
        sub = self.db.query(ActUserRole.act_id).filter(ActUserRole.user_id == user_id).subquery()
        return (
            self.db.query(Act)
            .filter(Act.id.in_(sub))
            .order_by(Act.created_at.desc(), Act.id.desc())
            .all()
        )

    def get_act_ids_by_user(self, user_id: str) -> list[int]:
        sub = self.db.query(ActUserRole.act_id).filter(ActUserRole.user_id == user_id).subquery()
        rows = self.db.query(Act.id).filter(Act.id.in_(sub)).all()
        return [row[0] for row in rows]

    def get_all_act_ids(self) -> list[int]:
        rows = self.db.query(Act.id).all()
        return [row[0] for row in rows]

    def get_act_ids_by_counterparty(self, counterparty_ids: list[str]) -> list[int]:
        from sqlalchemy import or_
        if not counterparty_ids:
            return []
        rows = self.db.query(Act.id).filter(
            or_(
                Act.customer_id.in_(counterparty_ids),
                Act.contractor_id.in_(counterparty_ids),
            )
        ).all()
        return [row[0] for row in rows]

    def create(self, payload: dict) -> Act:
        row = Act(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Act) -> Act:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Act) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- User roles ---

    def get_user_roles(self, act_id: int) -> list[ActUserRole]:
        return self.db.query(ActUserRole).filter(ActUserRole.act_id == act_id).all()

    def create_user_role(self, act_id: int, user_id: str, role: str, created_by: str) -> ActUserRole:
        row = ActUserRole(
            id=str(uuid.uuid4()),
            act_id=act_id,
            user_id=user_id,
            role=role,
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_user_role(self, row: ActUserRole, payload: dict) -> ActUserRole:
        for key, value in payload.items():
            setattr(row, key, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user_role(self, row: ActUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_user_role(self, role_id: str) -> ActUserRole | None:
        return self.db.query(ActUserRole).filter(ActUserRole.id == role_id).first()

    def get_user_role_by_user_and_act(self, act_id: int, user_id: str) -> ActUserRole | None:
        return (
            self.db.query(ActUserRole)
            .filter(ActUserRole.act_id == act_id, ActUserRole.user_id == user_id)
            .first()
        )

    # --- Statuses ---

    def create_status(self, act_id: int, status_id: str, created_by: str) -> ActStatus:
        row = ActStatus(
            id=str(uuid.uuid4()),
            act_id=act_id,
            status_id=status_id,
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_statuses(self, act_id: int) -> list[ActStatus]:
        return (
            self.db.query(ActStatus)
            .filter(ActStatus.act_id == act_id)
            .order_by(ActStatus.created_at)
            .all()
        )

    def get_current_status(self, act_id: int) -> ActStatus | None:
        return (
            self.db.query(ActStatus)
            .filter(ActStatus.act_id == act_id)
            .order_by(ActStatus.created_at.desc())
            .first()
        )

    def get_status_name(self, status_id: str) -> str | None:
        row = self.db.query(StatusRef).filter(StatusRef.id == status_id).first()
        return row.name if row else None

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        rows = self.db.query(StatusRef).filter(StatusRef.id.in_(status_ids)).all()
        return {r.id: r.name for r in rows}

    # --- Folders ---

    def get_folders(self, act_id: int) -> list[ActFolder]:
        return (
            self.db.query(ActFolder)
            .filter(ActFolder.act_id == act_id)
            .order_by(ActFolder.name)
            .all()
        )

    def create_folder(self, act_id: int, name: str, created_by: str, parent_id: str | None = None) -> ActFolder:
        row = ActFolder(
            id=str(uuid.uuid4()),
            act_id=act_id,
            name=name,
            parent_id=parent_id,
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_folder(self, row: ActFolder, payload: dict) -> ActFolder:
        for key, value in payload.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_folder(self, row: ActFolder) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_folder(self, folder_id: str) -> ActFolder | None:
        return self.db.query(ActFolder).filter(ActFolder.id == folder_id).first()

    # --- Files ---

    def create_file(self, payload: dict) -> ActFile:
        row = ActFile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_file(self, row: ActFile, payload: dict) -> ActFile:
        for key, value in payload.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: ActFile) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_file(self, file_id: str) -> ActFile | None:
        return self.db.query(ActFile).filter(ActFile.id == file_id).first()

    def get_files(self, act_id: int) -> list[ActFile]:
        return self.db.query(ActFile).filter(ActFile.act_id == act_id).order_by(ActFile.uploaded_at).all()

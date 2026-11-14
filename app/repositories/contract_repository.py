import uuid

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.act import Act, ActType
from app.models.documents_link import DocumentsLink

from app.models.contract import (
    Contract,
    ContractFile,
    ContractFolder,
    ContractLog,
    ContractObject,
    ContractParty,
    ContractStatus,
    ContractUserRole,
    ContractWorkType,
    DocumentType,
    WorkContract,
    msk_now,
)


class ContractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_contract_by_id(self, contract_id: int) -> Contract | None:
        return self.db.query(Contract).filter(Contract.id == contract_id).first()

    def get_contracts(self) -> list[Contract]:
        return self.db.query(Contract).order_by(Contract.id.desc()).all()

    def get_contracts_by_ids(self, contract_ids: list[int]) -> list[Contract]:
        if not contract_ids:
            return []
        return self.db.query(Contract).filter(Contract.id.in_(contract_ids)).order_by(Contract.id.desc()).all()

    def get_contract_by_num_and_date(self, num: str, contract_date) -> Contract | None:
        return (
            self.db.query(Contract)
            .filter(Contract.num == num, Contract.date == contract_date)
            .first()
        )

    def get_contract_ids_by_user(self, user_id: str) -> list[int]:
        from sqlalchemy import union
        from app.models.contract import ContractUserRole
        created_q = self.db.query(Contract.id).filter(Contract.created_by == user_id)
        role_q = self.db.query(ContractUserRole.contract_id).filter(ContractUserRole.user_id == user_id)
        union_q = union(created_q, role_q).subquery()
        rows = self.db.query(Contract.id).filter(Contract.id.in_(union_q)).all()
        return [row[0] for row in rows]

    def get_all_contract_ids(self) -> list[int]:
        rows = self.db.query(Contract.id).all()
        return [row[0] for row in rows]

    def get_contract_ids_by_counterparty(self, counterparty_ids: list[str]) -> list[int]:
        from sqlalchemy import or_
        if not counterparty_ids:
            return []
        rows = self.db.query(Contract.id).filter(
            or_(
                Contract.customer_id.in_(counterparty_ids),
                Contract.contractor_id.in_(counterparty_ids),
            )
        ).all()
        return [row[0] for row in rows]

    def count_contracts_by_internal_party(
        self, counterparty_id: str, role: str, contract_type: str, year: int | None = None
    ) -> int:
        from sqlalchemy import func
        column = Contract.customer_id if role == "customer" else Contract.contractor_id
        q = self.db.query(func.count(Contract.id)).filter(
            column == counterparty_id,
            Contract.type == contract_type,
        )
        if year is not None:
            from sqlalchemy import extract
            q = q.filter(extract("year", Contract.date) == year)
        else:
            q = q.filter(Contract.date.is_(None))
        return q.scalar() or 0

    def create_contract(self, payload: dict) -> Contract:
        row = Contract(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_contract(self, row: Contract) -> Contract:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_contract(self, row: Contract) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractWorkType ---

    def get_work_types(self) -> list[ContractWorkType]:
        return self.db.query(ContractWorkType).order_by(ContractWorkType.name.asc()).all()

    def get_work_type_by_id(self, work_type_id: int) -> ContractWorkType | None:
        return self.db.query(ContractWorkType).filter(ContractWorkType.id == work_type_id).first()

    def create_work_type(self, payload: dict) -> ContractWorkType:
        row = ContractWorkType(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_work_type(self, row: ContractWorkType) -> ContractWorkType:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_work_type(self, row: ContractWorkType) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- DocumentType ---

    def get_document_types(self) -> list[DocumentType]:
        return self.db.query(DocumentType).order_by(DocumentType.name.asc()).all()

    def get_document_type_by_id(self, doc_type_id: str) -> DocumentType | None:
        return self.db.query(DocumentType).filter(DocumentType.id == doc_type_id).first()

    def create_document_type(self, payload: dict) -> DocumentType:
        row = DocumentType(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_document_type(self, row: DocumentType) -> DocumentType:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_document_type(self, row: DocumentType) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractLog ---

    def create_log(self, log_object_id: str, log_object_type: str, message: str, created_by: str) -> ContractLog:
        row = ContractLog(
            id=str(uuid.uuid4()),
            log_object_id=log_object_id,
            log_object_type=log_object_type,
            message=message,
            created_at=msk_now(),
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_logs(
        self,
        log_object_id: str | None = None,
        log_object_type: str | None = None,
        created_by: str | None = None,
    ) -> list[ContractLog]:
        q = self.db.query(ContractLog)
        if log_object_id is not None:
            q = q.filter(ContractLog.log_object_id == log_object_id)
        if log_object_type is not None:
            q = q.filter(ContractLog.log_object_type == log_object_type)
        if created_by is not None:
            q = q.filter(ContractLog.created_by == created_by)
        return q.order_by(ContractLog.created_at.desc()).all()

    # --- ContractParty ---

    def get_parties(self, contract_id: int | None = None) -> list[ContractParty]:
        q = self.db.query(ContractParty)
        if contract_id is not None:
            q = q.filter(ContractParty.contract_id == contract_id)
        return q.order_by(ContractParty.created_at.desc()).all()

    def get_parties_by_contract_ids(self, contract_ids: list[int]) -> list[ContractParty]:
        if not contract_ids:
            return []
        return (
            self.db.query(ContractParty)
            .filter(ContractParty.contract_id.in_(contract_ids))
            .order_by(ContractParty.created_at.desc())
            .all()
        )

    def get_party_by_id(self, party_id: str) -> ContractParty | None:
        return self.db.query(ContractParty).filter(ContractParty.id == party_id).first()

    def create_party(self, payload: dict) -> ContractParty:
        row = ContractParty(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_party(self, row: ContractParty) -> ContractParty:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_party(self, row: ContractParty) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractUserRole ---

    def get_user_roles(self, contract_id: int | None = None, role: str | None = None) -> list[ContractUserRole]:
        q = self.db.query(ContractUserRole)
        if contract_id is not None:
            q = q.filter(ContractUserRole.contract_id == contract_id)
        if role is not None:
            q = q.filter(ContractUserRole.role == role)
        return q.order_by(ContractUserRole.created_at.desc()).all()

    def get_user_roles_by_contract_ids(self, contract_ids: list[int]) -> list[ContractUserRole]:
        if not contract_ids:
            return []
        return (
            self.db.query(ContractUserRole)
            .filter(ContractUserRole.contract_id.in_(contract_ids))
            .order_by(ContractUserRole.created_at.desc())
            .all()
        )

    def get_user_role_by_id(self, role_id: str) -> ContractUserRole | None:
        return self.db.query(ContractUserRole).filter(ContractUserRole.id == role_id).first()

    def create_user_role(self, payload: dict) -> ContractUserRole:
        row = ContractUserRole(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_user_role(self, row: ContractUserRole) -> ContractUserRole:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user_role(self, row: ContractUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- WorkContract ---

    def get_work_contracts(self, contract_id: int | None = None) -> list[WorkContract]:
        q = self.db.query(WorkContract)
        if contract_id is not None:
            q = q.filter(WorkContract.contract_id == contract_id)
        return q.order_by(WorkContract.created_at.desc()).all()

    def get_work_contracts_by_contract_ids(self, contract_ids: list[int]) -> list[WorkContract]:
        if not contract_ids:
            return []
        return (
            self.db.query(WorkContract)
            .filter(WorkContract.contract_id.in_(contract_ids))
            .order_by(WorkContract.created_at.desc())
            .all()
        )

    def get_work_contract_by_id(self, wc_id: str) -> WorkContract | None:
        return self.db.query(WorkContract).filter(WorkContract.id == wc_id).first()

    def create_work_contract(self, payload: dict) -> WorkContract:
        row = WorkContract(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_work_contract(self, row: WorkContract) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractObject ---

    def get_contract_objects(self, contract_id: int | None = None) -> list[ContractObject]:
        q = self.db.query(ContractObject)
        if contract_id is not None:
            q = q.filter(ContractObject.contract_id == contract_id)
        return q.order_by(ContractObject.id.asc()).all()

    def get_linked_acts_by_contract_ids(self, contract_ids: list[int]) -> dict[int, list[dict]]:
        """contract id -> the acts linked to it through documents_links (a link may be stored in
        either order). One act is listed once per contract however many links point at it."""
        result: dict[int, list[dict]] = {cid: [] for cid in contract_ids}
        if not contract_ids:
            return result

        ids = [str(c) for c in contract_ids]
        links = (
            self.db.query(DocumentsLink)
            .filter(
                or_(
                    and_(
                        DocumentsLink.document_type_first == "act",
                        DocumentsLink.document_type_second == "contract",
                        DocumentsLink.document_linked_second.in_(ids),
                    ),
                    and_(
                        DocumentsLink.document_type_first == "contract",
                        DocumentsLink.document_type_second == "act",
                        DocumentsLink.document_linked_first.in_(ids),
                    ),
                )
            )
            .all()
        )
        pairs: set[tuple[int, int]] = set()
        for link in links:
            contract_ref, act_ref = (
                (link.document_linked_second, link.document_linked_first)
                if link.document_type_first == "act"
                else (link.document_linked_first, link.document_linked_second)
            )
            if str(contract_ref).isdigit() and str(act_ref).isdigit():
                pairs.add((int(contract_ref), int(act_ref)))
        if not pairs:
            return result

        rows = (
            self.db.query(Act, ActType.name)
            .outerjoin(ActType, ActType.id == Act.act_type_id)
            .filter(Act.id.in_({act_id for _c, act_id in pairs}))
            .all()
        )
        acts = {
            act.id: {
                "id": act.id,
                "act_type_id": act.act_type_id,
                "act_type_name": type_name or "",
                "num": act.num,
                "fullname": f"{type_name or ''} №{act.num}".strip(),
                "date": act.date,
                "sum": float(act.sum) if act.sum is not None else None,
            }
            for act, type_name in rows
        }
        for contract_id, act_id in sorted(pairs):
            if act_id in acts and contract_id in result:
                result[contract_id].append(acts[act_id])
        return result

    def get_contract_objects_by_contract_ids(self, contract_ids: list[int]) -> list[ContractObject]:
        if not contract_ids:
            return []
        return (
            self.db.query(ContractObject)
            .filter(ContractObject.contract_id.in_(contract_ids))
            .order_by(ContractObject.id.asc())
            .all()
        )

    def get_contract_objects_by_object_ids(self, object_ids: list[str]) -> list[ContractObject]:
        if not object_ids:
            return []
        return (
            self.db.query(ContractObject)
            .filter(ContractObject.object_id.in_(object_ids))
            .order_by(ContractObject.id.asc())
            .all()
        )

    def get_contract_object_by_id(self, obj_id: int) -> ContractObject | None:
        return self.db.query(ContractObject).filter(ContractObject.id == obj_id).first()

    def create_contract_object(self, payload: dict) -> ContractObject:
        row = ContractObject(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_contract_object(self, row: ContractObject) -> ContractObject:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_contract_object(self, row: ContractObject) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractFolder ---

    def get_folders(self, contract_id: int | None = None) -> list[ContractFolder]:
        q = self.db.query(ContractFolder)
        if contract_id is not None:
            q = q.filter(ContractFolder.contract_id == contract_id)
        return q.order_by(ContractFolder.created_at.asc()).all()

    def get_folder_by_id(self, folder_id: str) -> ContractFolder | None:
        return self.db.query(ContractFolder).filter(ContractFolder.id == folder_id).first()

    def create_folder(self, payload: dict) -> ContractFolder:
        row = ContractFolder(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_folder(self, row: ContractFolder) -> ContractFolder:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_folder(self, row: ContractFolder) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractFile ---

    def get_files(self, contract_id: int | None = None, folder_id: str | None = None) -> list[ContractFile]:
        q = self.db.query(ContractFile)
        if contract_id is not None:
            q = q.filter(ContractFile.contract_id == contract_id)
        if folder_id is not None:
            q = q.filter(ContractFile.contract_folder_id == folder_id)
        return q.order_by(ContractFile.uploaded_at.desc()).all()

    def get_file_by_id(self, file_id: str) -> ContractFile | None:
        return self.db.query(ContractFile).filter(ContractFile.id == file_id).first()

    def get_files_history(self, contract_id: int) -> list[ContractFile]:
        return (
            self.db.query(ContractFile)
            .filter(ContractFile.contract_id == contract_id, ContractFile.type.in_(["original", "version"]))
            .order_by(ContractFile.uploaded_at.desc())
            .all()
        )

    def get_files_by_contract_ids(self, contract_ids: list[int]) -> list[ContractFile]:
        if not contract_ids:
            return []
        return (
            self.db.query(ContractFile)
            .filter(ContractFile.contract_id.in_(contract_ids))
            .order_by(ContractFile.uploaded_at.desc())
            .all()
        )

    def create_file(self, payload: dict) -> ContractFile:
        row = ContractFile(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_file(self, row: ContractFile) -> ContractFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: ContractFile) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- ContractStatus ---

    def get_contract_statuses(self, contract_id: int | None = None) -> list[ContractStatus]:
        q = self.db.query(ContractStatus)
        if contract_id is not None:
            q = q.filter(ContractStatus.contract_id == contract_id)
        return q.order_by(ContractStatus.created_at.desc()).all()

    def get_contract_statuses_by_contract_ids(self, contract_ids: list[int]) -> list[ContractStatus]:
        if not contract_ids:
            return []
        return (
            self.db.query(ContractStatus)
            .filter(ContractStatus.contract_id.in_(contract_ids))
            .order_by(ContractStatus.created_at.desc())
            .all()
        )

    def get_contract_status_by_id(self, status_id: str) -> ContractStatus | None:
        return self.db.query(ContractStatus).filter(ContractStatus.id == status_id).first()

    def create_contract_status(self, payload: dict) -> ContractStatus:
        row = ContractStatus(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_contract_status(self, row: ContractStatus) -> None:
        self.db.delete(row)
        self.db.commit()

    def save_contract_status(self, row: ContractStatus) -> ContractStatus:
        self.db.commit()
        self.db.refresh(row)
        return row

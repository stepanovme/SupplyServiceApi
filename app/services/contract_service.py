import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status

from app.models.contract import (
    ContractCreate,
    ContractFileCreate,
    ContractFileUpdate,
    ContractFolderCreate,
    ContractFolderUpdate,
    ContractObjectCreate,
    ContractObjectUpdate,
    ContractPartyCreate,
    ContractPartyUpdate,
    ContractUpdate,
    ContractUserRoleCreate,
    ContractUserRoleUpdate,
    ContractWorkTypeCreate,
    ContractWorkTypeUpdate,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    WorkContractCreate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

BASE_CONTRACT_FILES_DIR = "/home/webserver/models/documents"


class ContractService:
    def __init__(
        self,
        repo: ContractRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    # --- helpers ---

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        users = self.auth_user_repo.get_by_ids([uid for uid in user_ids if uid])
        return {user.id: user for user in users}

    @staticmethod
    def _map_user(user):
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        short_fio = " ".join(part for part in [user.surname, name_initial, patronymic_initial] if part).strip()
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
            "short_fio": short_fio,
        }

    def _get_counterparty_names(self, counterparty_ids: list[str]) -> dict[str, str]:
        if not self.reference_repo:
            return {}
        return self.reference_repo.get_counterparty_names(counterparty_ids)

    def _require_contract(self, contract_id: int):
        contract = self.repo.get_contract_by_id(contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    # --- ContractWorkType ---

    def get_work_types(self):
        rows = self.repo.get_work_types()
        user_ids = {row.created_by for row in rows} | {row.updated_by for row in rows if row.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_work_type(r, users_by_id) for r in rows]

    def get_work_type(self, work_type_id: int):
        row = self.repo.get_work_type_by_id(work_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work type not found")
        user_ids = {row.created_by}
        if row.updated_by:
            user_ids.add(row.updated_by)
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_work_type(row, users_by_id)

    def create_work_type(self, payload: ContractWorkTypeCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_work_type(data)
        self.repo.create_log(created.id, "worktype", f"создал вид работ {created.name}", created_by)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_work_type(created, users_by_id)

    def update_work_type(self, work_type_id: int, payload: ContractWorkTypeUpdate, user_id: str):
        row = self.repo.get_work_type_by_id(work_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work type not found")
        old_name = row.name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        row.updated_by = user_id
        updated = self.repo.save_work_type(row)
        if "name" in data and old_name != data["name"]:
            self.repo.create_log(updated.id, "worktype", f"изменил название вида работ с {old_name} -> {data['name']}", user_id)
        user_ids = {updated.created_by, updated.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_work_type(updated, users_by_id)

    def delete_work_type(self, work_type_id: int, user_id: str):
        row = self.repo.get_work_type_by_id(work_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work type not found")
        self.repo.create_log(row.id, "worktype", f"удалил вид работ {row.name}", user_id)
        self.repo.delete_work_type(row)

    def _serialize_work_type(self, row, users_by_id: dict | None = None):
        return {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if users_by_id else None,
        }

    # --- DocumentType ---

    def get_document_types(self):
        rows = self.repo.get_document_types()
        user_ids = {row.created_by for row in rows} | {row.updated_by for row in rows if row.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_document_type(r, users_by_id) for r in rows]

    def get_document_type(self, doc_type_id: str):
        row = self.repo.get_document_type_by_id(doc_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
        user_ids = {row.created_by}
        if row.updated_by:
            user_ids.add(row.updated_by)
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_document_type(row, users_by_id)

    def create_document_type(self, payload: DocumentTypeCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_document_type(data)
        self.repo.create_log(0, "document_type", f"создал вид документа {created.name}", created_by)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_document_type(created, users_by_id)

    def update_document_type(self, doc_type_id: str, payload: DocumentTypeUpdate, user_id: str):
        row = self.repo.get_document_type_by_id(doc_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
        old_name = row.name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        row.updated_by = user_id
        updated = self.repo.save_document_type(row)
        if "name" in data and old_name != data["name"]:
            self.repo.create_log(0, "document_type", f"изменил название вида документа с {old_name} -> {data['name']}", user_id)
        user_ids = {updated.created_by, updated.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_document_type(updated, users_by_id)

    def delete_document_type(self, doc_type_id: str, user_id: str):
        row = self.repo.get_document_type_by_id(doc_type_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
        self.repo.create_log(0, "document_type", f"удалил вид документа {row.name}", user_id)
        self.repo.delete_document_type(row)

    def _serialize_document_type(self, row, users_by_id: dict | None = None):
        return {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if users_by_id else None,
        }

    # --- ContractLog ---

    def get_logs(self, log_object_id: int | None = None, log_object_type: str | None = None, created_by: str | None = None):
        rows = self.repo.get_logs(log_object_id, log_object_type, created_by)
        user_ids = {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        result = []
        for row in rows:
            user = users_by_id.get(row.created_by)
            user_info = self._map_user(user)
            short_fio = user_info["short_fio"] if user_info else row.created_by
            result.append({
                "id": row.id,
                "log_object_id": row.log_object_id,
                "log_object_type": row.log_object_type,
                "message": row.message,
                "created_at": row.created_at,
                "created_by": row.created_by,
                "created_by_user": user_info,
                "full_log": f"{short_fio} {row.message}",
            })
        return result

    # --- ContractParty ---

    def get_parties(self, contract_id: int | None = None):
        rows = self.repo.get_parties(contract_id)
        counterparty_ids = {row.counterparties_id for row in rows}
        counterparty_names = self._get_counterparty_names(list(counterparty_ids))
        user_ids = {row.created_by for row in rows} | {row.updated_by for row in rows if row.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_party(r, counterparty_names, users_by_id) for r in rows]

    def get_party(self, party_id: str):
        row = self.repo.get_party_by_id(party_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
        counterparty_names = self._get_counterparty_names([row.counterparties_id])
        user_ids = {row.created_by}
        if row.updated_by:
            user_ids.add(row.updated_by)
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_party(row, counterparty_names, users_by_id)

    def create_party(self, payload: ContractPartyCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_party(data)
        counterparty_names = self._get_counterparty_names([created.counterparties_id])
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_party(created, counterparty_names, users_by_id)

    def update_party(self, party_id: str, payload: ContractPartyUpdate, user_id: str):
        row = self.repo.get_party_by_id(party_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        row.updated_by = user_id
        updated = self.repo.save_party(row)
        counterparty_names = self._get_counterparty_names([updated.counterparties_id])
        user_ids = {updated.created_by, updated.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_party(updated, counterparty_names, users_by_id)

    def delete_party(self, party_id: str):
        row = self.repo.get_party_by_id(party_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
        self.repo.delete_party(row)

    def _serialize_party(self, row, counterparty_names: dict, users_by_id: dict):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "counterparties_id": row.counterparties_id,
            "counterparty_name": counterparty_names.get(row.counterparties_id),
            "name": row.name,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if users_by_id else None,
        }

    # --- ContractUserRole ---

    def get_user_roles(self, contract_id: int | None = None):
        rows = self.repo.get_user_roles(contract_id)
        user_ids = {row.user_id for row in rows} | {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_user_role(r, users_by_id) for r in rows]

    def get_user_role(self, role_id: str):
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return self._serialize_user_role(row, users_by_id)

    def create_user_role(self, payload: ContractUserRoleCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_user_role(data)
        users_by_id = self._get_users_map([created.user_id, created.created_by])
        return self._serialize_user_role(created, users_by_id)

    def update_user_role(self, role_id: str, payload: ContractUserRoleUpdate, user_id: str):
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_user_role(row)
        users_by_id = self._get_users_map([updated.user_id, updated.created_by])
        return self._serialize_user_role(updated, users_by_id)

    def delete_user_role(self, role_id: str):
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        self.repo.delete_user_role(row)

    def _serialize_user_role(self, row, users_by_id: dict):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)) if users_by_id else None,
            "role": row.role,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
        }

    # --- WorkContract ---

    def get_work_contracts(self, contract_id: int | None = None):
        rows = self.repo.get_work_contracts(contract_id)
        work_type_ids = {row.contract_work_type_id for row in rows}
        work_types = {wt.id: wt.name for wt in self.repo.get_work_types() if wt.id in work_type_ids} if work_type_ids else {}
        user_ids = {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_work_contract(r, work_types, users_by_id) for r in rows]

    def get_work_contract(self, wc_id: str):
        row = self.repo.get_work_contract_by_id(wc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work contract not found")
        work_type = self.repo.get_work_type_by_id(row.contract_work_type_id)
        work_type_name = work_type.name if work_type else None
        users_by_id = self._get_users_map([row.created_by])
        return self._serialize_work_contract(row, {row.contract_work_type_id: work_type_name} if work_type_name else {}, users_by_id)

    def create_work_contract(self, payload: WorkContractCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_work_contract(data)
        work_type = self.repo.get_work_type_by_id(created.contract_work_type_id)
        work_type_name = work_type.name if work_type else None
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_work_contract(created, {created.contract_work_type_id: work_type_name} if work_type_name else {}, users_by_id)

    def delete_work_contract(self, wc_id: str):
        row = self.repo.get_work_contract_by_id(wc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work contract not found")
        self.repo.delete_work_contract(row)

    def _serialize_work_contract(self, row, work_types: dict, users_by_id: dict):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "contract_work_type_id": row.contract_work_type_id,
            "contract_work_type_name": work_types.get(row.contract_work_type_id),
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
        }

    # --- ContractObject ---

    def get_contract_objects(self, contract_id: int | None = None):
        rows = self.repo.get_contract_objects(contract_id)
        return [self._serialize_contract_object(r) for r in rows]

    def get_contract_object(self, obj_id: int):
        row = self.repo.get_contract_object_by_id(obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract object not found")
        return self._serialize_contract_object(row)

    def create_contract_object(self, payload: ContractObjectCreate):
        data = payload.model_dump(exclude_unset=True)
        created = self.repo.create_contract_object(data)
        return self._serialize_contract_object(created)

    def update_contract_object(self, obj_id: int, payload: ContractObjectUpdate):
        row = self.repo.get_contract_object_by_id(obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract object not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_contract_object(row)
        return self._serialize_contract_object(updated)

    def delete_contract_object(self, obj_id: int):
        row = self.repo.get_contract_object_by_id(obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract object not found")
        self.repo.delete_contract_object(row)

    # --- Contract ---

    def get_contracts(self):
        rows = self.repo.get_contracts()
        return [self._build_contract_response(r, detail=True) for r in rows]

    def get_contract(self, contract_id: int):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        return self._build_contract_response(row, detail=True)

    def get_my_contracts(self, user_id: str):
        ids = self.repo.get_contract_ids_by_user(user_id)
        if not ids:
            return []
        rows = [self.repo.get_contract_by_id(cid) for cid in ids]
        rows = [r for r in rows if r]
        return [self._build_contract_response(r, detail=True) for r in rows]

    def _build_contract_response(self, row, detail: bool = False):
        doc_type_name = None
        if row.document_type_id:
            dt = self.repo.get_document_type_by_id(row.document_type_id)
            if dt:
                doc_type_name = dt.name

        counterparty_ids = {row.customer_id, row.contractor_id}
        counterparty_names = self._get_counterparty_names(list(counterparty_ids))

        user_ids = {row.created_by}
        users_by_id = self._get_users_map(list(user_ids))

        full_name = " ".join(part for part in [doc_type_name, row.name, "№", row.num] if part).strip()

        result = {
            "id": row.id,
            "num": row.num,
            "internal_num": row.internal_num,
            "date": row.date,
            "document_type_id": row.document_type_id,
            "document_type_name": doc_type_name,
            "name": row.name,
            "full_name": full_name,
            "date_start": row.date_start,
            "date_end": row.date_end,
            "date_completed": row.date_completed,
            "customer_id": row.customer_id,
            "customer_name": counterparty_names.get(row.customer_id),
            "contractor_id": row.contractor_id,
            "contractor_name": counterparty_names.get(row.contractor_id),
            "type": row.type,
            "sum": row.sum,
            "comment": row.comment,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
        }

        if detail:
            parties = self.repo.get_parties(contract_id=row.id)
            party_counterparty_ids = {p.counterparties_id for p in parties}
            all_counterparty_ids = counterparty_ids | party_counterparty_ids
            all_counterparty_names = self._get_counterparty_names(list(all_counterparty_ids))

            party_user_ids = {p.created_by for p in parties} | {p.updated_by for p in parties if p.updated_by}
            all_user_ids = user_ids | party_user_ids

            for role in self.repo.get_user_roles(contract_id=row.id):
                all_user_ids.add(role.user_id)
                all_user_ids.add(role.created_by)

            for wc in self.repo.get_work_contracts(contract_id=row.id):
                all_user_ids.add(wc.created_by)

            users_by_id = self._get_users_map(list(all_user_ids))
            work_types_map = {}
            for wt in self.repo.get_work_types():
                work_types_map[wt.id] = wt.name

            result["created_by_user"] = self._map_user(users_by_id.get(row.created_by))

            result["parties"] = [
                self._serialize_party(p, all_counterparty_names, users_by_id) for p in parties
            ]
            result["user_roles"] = [
                self._serialize_user_role(r, users_by_id) for r in self.repo.get_user_roles(contract_id=row.id)
            ]
            result["work_types"] = [
                self._serialize_work_contract(wc, work_types_map, users_by_id) for wc in self.repo.get_work_contracts(contract_id=row.id)
            ]
            result["objects"] = [
                self._serialize_contract_object(o, self.reference_repo) for o in self.repo.get_contract_objects(contract_id=row.id)
            ]

        return result

    def create_contract(self, payload: ContractCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by

        contractor_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("contractor_id", ""))
        customer_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("customer_id", ""))

        if contractor_internal:
            data["type"] = "buyer"
            data["internal_num"] = self.repo.count_contracts_by_internal_party(data["contractor_id"]) + 1
        elif customer_internal:
            data["type"] = "provider"
            data["internal_num"] = self.repo.count_contracts_by_internal_party(data["customer_id"]) + 1

        created = self.repo.create_contract(data)
        doc_type_name = None
        if created.document_type_id:
            dt = self.repo.get_document_type_by_id(created.document_type_id)
            if dt:
                doc_type_name = dt.name
        log_msg = f"создал договор {doc_type_name or ''} {created.name or ''} № {created.num or ''}".strip()
        self.repo.create_log(created.id, "contract", log_msg, created_by)
        return self._build_contract_response(created)

    def update_contract(self, contract_id: int, payload: ContractUpdate, user_id: str):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        updated = self.repo.save_contract(row)
        return self._build_contract_response(updated)

    def delete_contract(self, contract_id: int):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        self.repo.delete_contract(row)

    # --- ContractFolder ---

    def get_folders(self, contract_id: int | None = None):
        rows = self.repo.get_folders(contract_id)
        user_ids = {r.created_by for r in rows} | {r.updated_by for r in rows if r.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_folder(r, users_by_id) for r in rows]

    def get_folder_tree(self, contract_id: int):
        folders = self.repo.get_folders(contract_id)
        files = self.repo.get_files(contract_id=contract_id)
        user_ids = {f.created_by for f in folders} | {f.updated_by for f in folders if f.updated_by}
        for f in files:
            user_ids.add(f.uploaded_by)
            if f.updated_by:
                user_ids.add(f.updated_by)
        users_by_id = self._get_users_map(list(user_ids))

        folders_map = {}
        for f in folders:
            folders_map[f.id] = {**self._serialize_folder(f, users_by_id), "children": [], "files": []}

        root_files = []
        for f in files:
            file_data = self._serialize_file(f)
            parent_id = f.contract_folder_id
            if parent_id and parent_id in folders_map:
                folders_map[parent_id]["files"].append(file_data)
            elif not parent_id:
                root_files.append(file_data)

        roots = []
        for f_id, f_data in folders_map.items():
            parent_id = None
            for f in folders:
                if f.id == f_id:
                    parent_id = f.parent_id
                    break
            if parent_id and parent_id in folders_map:
                folders_map[parent_id]["children"].append(f_data)
            else:
                roots.append(f_data)

        if root_files:
            roots.append({"id": None, "name": "Без папки", "children": [], "files": root_files})

        return roots

    def get_folder(self, folder_id: str):
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        users_by_id = self._get_users_map([row.created_by, row.updated_by] if row.updated_by else [row.created_by])
        return self._serialize_folder(row, users_by_id)

    def create_folder(self, payload: ContractFolderCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_folder(data)
        self.repo.create_log(created.contract_id, "contract", f"создал папку {created.name}", created_by)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_folder(created, users_by_id)

    def update_folder(self, folder_id: str, payload: ContractFolderUpdate, user_id: str):
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        old_name = row.name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        row.updated_by = user_id
        updated = self.repo.save_folder(row)
        if "name" in data and data["name"] != old_name:
            self.repo.create_log(updated.contract_id, "contract", f"изменил название папки с {old_name} на {data['name']}", user_id)
        users_by_id = self._get_users_map([updated.created_by, updated.updated_by])
        return self._serialize_folder(updated, users_by_id)

    def delete_folder(self, folder_id: str, user_id: str):
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        contract_id = row.contract_id
        name = row.name
        self.repo.delete_folder(row)
        self.repo.create_log(contract_id, "contract", f"удалил папку {name}", user_id)

    def _serialize_folder(self, row, users_by_id: dict | None = None):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "name": row.name,
            "parent_id": row.parent_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if users_by_id else None,
        }

    # --- ContractFile ---

    def get_files(self, contract_id: int | None = None, folder_id: str | None = None):
        rows = self.repo.get_files(contract_id, folder_id)
        return [self._serialize_file(r) for r in rows]

    def get_file(self, file_id: str):
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return self._serialize_file(row)

    def upload(self, contract_id: int, original_name: str, file_bytes: bytes, uploaded_by: str, contract_folder_id: str | None = None):
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_CONTRACT_FILES_DIR, str(contract_id))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        created = self.repo.create_file({
            "contract_id": contract_id,
            "contract_folder_id": contract_folder_id,
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": uploaded_by,
        })
        self.repo.create_log(contract_id, "contract", f"загрузил файл {original_name}", uploaded_by)
        return self._serialize_file(created)

    def get_download(self, file_id: str) -> tuple[str, str]:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    def update_file(self, file_id: str, payload: ContractFileUpdate, user_id: str):
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        old_name = row.original_name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        row.updated_by = user_id
        updated = self.repo.save_file(row)
        if "original_name" in data and data["original_name"] != old_name:
            self.repo.create_log(updated.contract_id, "contract", f"изменил название файла с {old_name} на {data['original_name']}", user_id)
        return self._serialize_file(updated)

    def delete_file(self, file_id: str, user_id: str):
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        contract_id = row.contract_id
        original_name = row.original_name
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)
        self.repo.create_log(contract_id, "contract", f"удалил файл {original_name}", user_id)

    @staticmethod
    def _serialize_file(row):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
            "contract_folder_id": row.contract_folder_id,
            "type": row.type,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def _serialize_contract_object(self, row, reference_repo=None):
        object_name = None
        if reference_repo:
            if row.object_type == "object":
                objs = reference_repo.get_objects_by_ids([row.object_id])
                if objs:
                    object_name = objs[0].short_name
            elif row.object_type == "object_levels_id":
                object_name = reference_repo.resolve_object_name(row.object_id)
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": object_name,
        }

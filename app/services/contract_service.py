import os
import subprocess
import uuid
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
    ContractStatusCreate,
    ContractStatusUpdate,
    ContractUpdate,
    ContractUserRoleCreate,
    ContractUserRoleUpdate,
    ContractWorkTypeCreate,
    ContractWorkTypeUpdate,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    WorkContractCreate,
    msk_now,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_extract_repository import ContractExtractRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

BASE_CONTRACT_FILES_DIR = "/home/webserver/models/documents"


class ContractService:
    def __init__(
        self,
        repo: ContractRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        documents_list_repo: DocumentsListRepository | None = None,
        department_repo=None,
        doc_access_service=None,
        contract_extract_repo: ContractExtractRepository | None = None,
        extract_item_repo: ExtractItemRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.documents_list_repo = documents_list_repo
        self.department_repo = department_repo
        self.doc_access_service = doc_access_service
        self.contract_extract_repo = contract_extract_repo
        self.extract_item_repo = extract_item_repo

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

    def _get_payments_by_contract_ids(self, contract_ids: list[int]) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = {cid: [] for cid in contract_ids}
        if not self.contract_extract_repo or not self.extract_item_repo or not contract_ids:
            return result

        links = self.contract_extract_repo.get_by_contract_ids(contract_ids)
        if not links:
            return result

        extract_ids = list({link.extract_id for link in links})
        extract_items_by_id = {item.id: item for item in self.extract_item_repo.get_by_ids(extract_ids)}

        for link in links:
            item = extract_items_by_id.get(link.extract_id)
            result.setdefault(link.contract_id, []).append(
                {
                    "contract_extract_id": link.id,
                    "extract_id": link.extract_id,
                    "amount": item.amount if item else None,
                    "operationDate": item.operationDate if item else None,
                    "paymentPurpose": item.paymentPurpose if item else None,
                    "payerName": item.payerName if item else None,
                    "payeeName": item.payeeName if item else None,
                }
            )
        return result

    # --- Acts: completed work, debt and receivable ---

    @staticmethod
    def _count_acts(acts: list[dict]) -> list[dict]:
        """Marks which acts count towards the completed-work sum.

        A КС-2 and a КС-3 (or any acts of different types) for the same work carry the same sum and
        must be counted once. So for every sum the type that has the most acts with it is counted
        in full and the acts of other types with that very sum are skipped; several acts of ONE type
        with equal sums are still separate works and all count. Acts without a sum count nothing."""
        by_sum: dict[float, dict[int, list[dict]]] = {}
        for act in acts:
            if act["sum"]:
                by_sum.setdefault(round(act["sum"], 2), {}).setdefault(act["act_type_id"], []).append(act)

        counted_ids: set[int] = set()
        for groups in by_sum.values():
            # the type with the most acts of this sum; a tie goes to the lowest type id
            main_type = min(groups, key=lambda t: (-len(groups[t]), t))
            counted_ids.update(a["id"] for a in groups[main_type])

        return [{**a, "counted": a["id"] in counted_ids} for a in acts]

    def _acts_summary(self, acts: list[dict], paid_sum: float, contract_type: str | None = None) -> dict:
        marked = self._count_acts(acts)
        acts_sum = round(float(sum(a["sum"] for a in marked if a["counted"])), 2)
        paid = round(paid_sum, 2)

        if contract_type == "provider":
            # Supplier contract: there is no receivable, only debt. Any payment means there is no debt;
            # acts without any payment mean the whole acts sum is owed.
            debt_sum = acts_sum if (acts_sum > 0 and paid <= 0) else 0.0
            receivable_sum = 0.0
        else:
            # paid more than the acts show -> debt; the acts exceed the payments -> receivable
            debt_sum = round(paid - acts_sum, 2) if paid > acts_sum else 0.0
            receivable_sum = round(acts_sum - paid, 2) if acts_sum > paid else 0.0

        return {
            # sum of the work done = sum of the counted acts
            "acts_sum": acts_sum,
            "acts_count": len(marked),
            "acts_counted": sum(1 for a in marked if a["counted"]),
            "debt_sum": debt_sum,
            "receivable_sum": receivable_sum,
            "acts": marked,
        }

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
        row.updated_at = msk_now()
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
        row.updated_at = msk_now()
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

    def get_logs(self, log_object_id: str | None = None, log_object_type: str | None = None, created_by: str | None = None):
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
        org_name = counterparty_names.get(created.counterparties_id, "")
        self.repo.create_log(created.contract_id, "contract", f"добавил сторону договора {created.name} {org_name}".strip(), created_by)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_party(created, counterparty_names, users_by_id)

    def update_party(self, party_id: str, payload: ContractPartyUpdate, user_id: str):
        row = self.repo.get_party_by_id(party_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
        old_name = row.name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save_party(row)
        if "name" in data and data["name"] != old_name:
            self.repo.create_log(updated.contract_id, "contract", f"изменил название стороны договора с {old_name} на {data['name']}", user_id)
        counterparty_names = self._get_counterparty_names([updated.counterparties_id])
        user_ids = {updated.created_by, updated.updated_by}
        users_by_id = self._get_users_map(list(user_ids))
        return self._serialize_party(updated, counterparty_names, users_by_id)

    def delete_party(self, party_id: str, user_id: str):
        row = self.repo.get_party_by_id(party_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
        contract_id = row.contract_id
        name = row.name
        self.repo.delete_party(row)
        self.repo.create_log(contract_id, "contract", f"удалил сторону договора {name}", user_id)

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
        self._sync_information_status(created.contract_id, created_by)
        users_by_id = self._get_users_map([created.user_id, created.created_by])
        user_info = users_by_id.get(created.user_id)
        user_name = user_info.get("short_fio", created.user_id) if user_info else created.user_id
        self.repo.create_log(created.contract_id, "contract", f"добавил роль {created.role} для {user_name}", created_by)
        return self._serialize_user_role(created, users_by_id)

    def update_user_role(self, role_id: str, payload: ContractUserRoleUpdate, user_id: str):
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        old_role = row.role
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_user_role(row)
        if "role" in data and data["role"] != old_role:
            self.repo.create_log(updated.contract_id, "contract", f"изменил роль с {old_role} на {data['role']}", user_id)
        self._sync_information_status(updated.contract_id, user_id)
        users_by_id = self._get_users_map([updated.user_id, updated.created_by])
        return self._serialize_user_role(updated, users_by_id)

    def delete_user_role(self, role_id: str, user_id: str):
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        contract_id = row.contract_id
        role = row.role
        self.repo.delete_user_role(row)
        self._sync_information_status(contract_id, user_id)
        self.repo.create_log(contract_id, "contract", f"удалил роль {role}", user_id)

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
        self._sync_information_status(created.contract_id, created_by)
        work_type = self.repo.get_work_type_by_id(created.contract_work_type_id)
        work_type_name = work_type.name if work_type else str(created.contract_work_type_id)
        self.repo.create_log(created.contract_id, "contract", f"добавил вид работ {work_type_name}", created_by)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_work_contract(created, {created.contract_work_type_id: work_type_name} if work_type_name else {}, users_by_id)

    def delete_work_contract(self, wc_id: str, user_id: str):
        row = self.repo.get_work_contract_by_id(wc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work contract not found")
        contract_id = row.contract_id
        work_type = self.repo.get_work_type_by_id(row.contract_work_type_id)
        work_type_name = work_type.name if work_type else str(row.contract_work_type_id)
        self.repo.delete_work_contract(row)
        self._sync_information_status(contract_id, user_id)
        self.repo.create_log(contract_id, "contract", f"удалил вид работ {work_type_name}", user_id)

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

    def create_contract_object(self, payload: ContractObjectCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        created = self.repo.create_contract_object(data)
        self._sync_information_status(created.contract_id, created_by)
        object_name = self._resolve_object_name(created)
        self.repo.create_log(created.contract_id, "contract", f"добавил объект {object_name or created.object_id}", created_by)
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

    def delete_contract_object(self, obj_id: int, user_id: str):
        row = self.repo.get_contract_object_by_id(obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract object not found")
        contract_id = row.contract_id
        object_name = self._resolve_object_name(row)
        self.repo.delete_contract_object(row)
        self._sync_information_status(contract_id, user_id)
        self.repo.create_log(contract_id, "contract", f"удалил объект {object_name or row.object_id}", user_id)

    # --- ContractStatus ---

    def get_contract_statuses(self, contract_id: int | None = None):
        rows = self.repo.get_contract_statuses(contract_id)
        return [self._serialize_contract_status(r) for r in rows]

    def create_contract_status(self, payload: ContractStatusCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create_contract_status(data)
        self.repo.create_log(created.contract_id, "contract", f"присвоил статус {self.STATUS_LABELS.get(created.status, created.status)}", created_by)
        return self._serialize_contract_status(created)

    def update_contract_status(self, status_id: str, payload: ContractStatusUpdate, user_id: str):
        row = self.repo.get_contract_status_by_id(status_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract status not found")
        old_status = row.status
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_contract_status(row)
        if "status" in data and data["status"] != old_status:
            self.repo.create_log(updated.contract_id, "contract", f"изменил статус с {self.STATUS_LABELS.get(old_status, old_status)} на {self.STATUS_LABELS.get(data['status'], data['status'])}", user_id)
        return self._serialize_contract_status(updated)

    def delete_contract_status(self, status_id: str, user_id: str):
        row = self.repo.get_contract_status_by_id(status_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract status not found")
        contract_id = row.contract_id
        status_label = self.STATUS_LABELS.get(row.status, row.status)
        self.repo.delete_contract_status(row)
        self.repo.create_log(contract_id, "contract", f"удалил статус {status_label}", user_id)

    STATUS_LABELS = {"information": "Заполнен", "signed": "Подписан", "original": "Оригинал", "verified": "Сверен"}

    def _sync_information_status(self, contract_id: int, user_id: str):
        contract = self.repo.get_contract_by_id(contract_id)
        if not contract:
            return

        has_data = (
            contract.internal_num
            and contract.document_type_id
            and contract.date
            and contract.sum is not None
            and self.repo.get_work_contracts(contract_id=contract_id)
            and self.repo.get_user_roles(contract_id=contract_id, role="executor")
            and self.repo.get_contract_objects(contract_id=contract_id)
        )

        existing = [s for s in self.repo.get_contract_statuses(contract_id=contract_id) if s.status == "information"]
        info_status = existing[0] if existing else None

        if has_data and not info_status:
            self.repo.create_contract_status({
                "contract_id": contract_id,
                "status": "information",
                "created_by": user_id,
            })
            self.repo.create_log(contract_id, "contract", f"присвоил статус {self.STATUS_LABELS['information']}", user_id)
        elif not has_data and info_status:
            self.repo.delete_contract_status(info_status)
            self.repo.create_log(contract_id, "contract", f"удалил статус {self.STATUS_LABELS['information']}", user_id)

    @staticmethod
    def _serialize_contract_status(row):
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "status": row.status,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    # --- Contract ---

    def get_contracts(self):
        rows = self.repo.get_contracts()
        payments_by_contract = self._get_payments_by_contract_ids([r.id for r in rows])
        acts_by_contract = self.repo.get_linked_acts_by_contract_ids([r.id for r in rows])
        return [
            self._build_contract_response(
                r, detail=True, payments=payments_by_contract.get(r.id, []), acts=acts_by_contract.get(r.id, [])
            )
            for r in rows
        ]

    def get_contracts_list(self):
        rows = self.repo.get_contracts()
        result = []
        for row in rows:
            doc_type_name = None
            if row.document_type_id:
                dt = self.repo.get_document_type_by_id(row.document_type_id)
                if dt:
                    doc_type_name = dt.name
            full_name = " ".join(part for part in [doc_type_name, row.name, "№", row.num] if part).strip()
            result.append({"id": row.id, "full_name": full_name})
        return result

    def get_contract(self, contract_id: int):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        return self._build_contract_response(row, detail=True)

    def get_my_contracts(self, user_id: str):
        ids = self.repo.get_contract_ids_by_user(user_id)

        # Добавляем ID на основе document_access_settings
        if self.doc_access_service and self.department_repo:
            dept_ids = self.department_repo.get_department_ids_for_user(user_id)
            extra_ids = self.doc_access_service.get_additional_visible_ids(
                "contract", user_id, dept_ids,
                self.repo.get_all_contract_ids,
                self.repo.get_contract_ids_by_counterparty,
            )
            ids = list(set(ids + extra_ids))

        if not ids:
            return []

        rows = self.repo.get_contracts_by_ids(ids)
        rows.sort(key=lambda r: r.id, reverse=True)

        contract_ids = [r.id for r in rows]

        doc_types = self.repo.get_document_types()
        doc_type_map = {dt.id: dt.name for dt in doc_types}

        counterparty_ids = set()
        user_ids = set()
        for r in rows:
            counterparty_ids.add(r.customer_id)
            counterparty_ids.add(r.contractor_id)
            user_ids.add(r.created_by)

        counterparty_names = self._get_counterparty_names(list(counterparty_ids))

        parties_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for p in self.repo.get_parties_by_contract_ids(contract_ids):
            parties_by_contract.setdefault(p.contract_id, []).append(p)
            counterparty_ids.add(p.counterparties_id)
            user_ids.add(p.created_by)
            if p.updated_by:
                user_ids.add(p.updated_by)

        role_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for role in self.repo.get_user_roles_by_contract_ids(contract_ids):
            role_by_contract.setdefault(role.contract_id, []).append(role)
            user_ids.update({role.user_id, role.created_by})

        wc_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for wc in self.repo.get_work_contracts_by_contract_ids(contract_ids):
            wc_by_contract.setdefault(wc.contract_id, []).append(wc)
            user_ids.add(wc.created_by)

        object_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for obj in self.repo.get_contract_objects_by_contract_ids(contract_ids):
            object_by_contract.setdefault(obj.contract_id, []).append(obj)

        status_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for s in self.repo.get_contract_statuses_by_contract_ids(contract_ids):
            status_by_contract.setdefault(s.contract_id, []).append(s)

        all_counterparty_names = self._get_counterparty_names(list(counterparty_ids))
        users_by_id = self._get_users_map(list(user_ids))
        work_types_map = {wt.id: wt.name for wt in self.repo.get_work_types()}
        payments_by_contract = self._get_payments_by_contract_ids(contract_ids)
        acts_by_contract = self.repo.get_linked_acts_by_contract_ids(contract_ids)

        result = []
        for r in rows:
            parties = parties_by_contract[r.id]
            result.append(
                self._build_contract_response(
                    r,
                    detail=True,
                    doc_type_map=doc_type_map,
                    counterparty_names=all_counterparty_names,
                    users_by_id=users_by_id,
                    parties=parties,
                    roles=role_by_contract[r.id],
                    work_contracts=wc_by_contract[r.id],
                    statuses=status_by_contract[r.id],
                    objects=object_by_contract[r.id],
                    work_types_map=work_types_map,
                    payments=payments_by_contract.get(r.id, []),
                    acts=acts_by_contract.get(r.id, []),
                )
            )
        return result

    def get_contracts_by_object(self, object_id: str):
        level_ids = self.reference_repo.get_level_ids_by_object_ids([object_id]) if self.reference_repo else set()
        object_ids = [object_id, *level_ids]

        contract_objects = self.repo.get_contract_objects_by_object_ids(object_ids)
        contract_ids = sorted({obj.contract_id for obj in contract_objects}, reverse=True)

        if not contract_ids:
            return []

        rows = self.repo.get_contracts_by_ids(contract_ids)
        rows.sort(key=lambda r: r.id, reverse=True)

        doc_types = self.repo.get_document_types()
        doc_type_map = {dt.id: dt.name for dt in doc_types}

        counterparty_ids = set()
        user_ids = set()
        for r in rows:
            counterparty_ids.add(r.customer_id)
            counterparty_ids.add(r.contractor_id)
            user_ids.add(r.created_by)

        parties_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for p in self.repo.get_parties_by_contract_ids(contract_ids):
            parties_by_contract.setdefault(p.contract_id, []).append(p)
            counterparty_ids.add(p.counterparties_id)
            user_ids.add(p.created_by)
            if p.updated_by:
                user_ids.add(p.updated_by)

        role_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for role in self.repo.get_user_roles_by_contract_ids(contract_ids):
            role_by_contract.setdefault(role.contract_id, []).append(role)
            user_ids.update({role.user_id, role.created_by})

        wc_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for wc in self.repo.get_work_contracts_by_contract_ids(contract_ids):
            wc_by_contract.setdefault(wc.contract_id, []).append(wc)
            user_ids.add(wc.created_by)

        object_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for obj in self.repo.get_contract_objects_by_contract_ids(contract_ids):
            object_by_contract.setdefault(obj.contract_id, []).append(obj)

        status_by_contract: dict[int, list] = {cid: [] for cid in contract_ids}
        for s in self.repo.get_contract_statuses_by_contract_ids(contract_ids):
            status_by_contract.setdefault(s.contract_id, []).append(s)

        all_counterparty_names = self._get_counterparty_names(list(counterparty_ids))
        users_by_id = self._get_users_map(list(user_ids))
        work_types_map = {wt.id: wt.name for wt in self.repo.get_work_types()}
        payments_by_contract = self._get_payments_by_contract_ids(contract_ids)
        acts_by_contract = self.repo.get_linked_acts_by_contract_ids(contract_ids)

        result = []
        for r in rows:
            parties = parties_by_contract[r.id]
            result.append(
                self._build_contract_response(
                    r,
                    detail=True,
                    doc_type_map=doc_type_map,
                    counterparty_names=all_counterparty_names,
                    users_by_id=users_by_id,
                    parties=parties,
                    roles=role_by_contract[r.id],
                    work_contracts=wc_by_contract[r.id],
                    statuses=status_by_contract[r.id],
                    objects=object_by_contract[r.id],
                    work_types_map=work_types_map,
                    payments=payments_by_contract.get(r.id, []),
                    acts=acts_by_contract.get(r.id, []),
                )
            )
        return result

    def _build_contract_response(
        self,
        row,
        detail: bool = False,
        doc_type_map: dict | None = None,
        counterparty_names: dict | None = None,
        users_by_id: dict | None = None,
        parties: list | None = None,
        roles: list | None = None,
        statuses: list | None = None,
        objects: list | None = None,
        work_contracts: list | None = None,
        work_types_map: dict | None = None,
        payments: list | None = None,
        acts: list | None = None,
    ):
        doc_type_name = None
        if row.document_type_id:
            dt_name = doc_type_map.get(row.document_type_id) if doc_type_map is not None else None
            if dt_name is None:
                dt = self.repo.get_document_type_by_id(row.document_type_id)
                if dt:
                    dt_name = dt.name
            doc_type_name = dt_name

        if counterparty_names is None:
            counterparty_names = self._get_counterparty_names([row.customer_id, row.contractor_id])

        base_users_by_id = users_by_id if users_by_id is not None else self._get_users_map([row.created_by])

        full_name = " ".join(part for part in [doc_type_name, row.name, "№", row.num] if part).strip()

        if statuses is None:
            statuses = [self._serialize_contract_status(s) for s in self.repo.get_contract_statuses(contract_id=row.id)]
        else:
            statuses = [self._serialize_contract_status(s) for s in statuses]

        current_payments = payments if payments is not None else self._get_payments_by_contract_ids([row.id]).get(row.id, [])
        paid_sum = sum(float(p["amount"]) for p in current_payments if p.get("amount") is not None)
        contract_sum = float(row.sum) if row.sum is not None else None
        remaining_sum = (contract_sum - paid_sum) if contract_sum is not None else None
        paid_label = f"{paid_sum} из {contract_sum}" if contract_sum is not None else None
        current_acts = acts if acts is not None else self.repo.get_linked_acts_by_contract_ids([row.id]).get(row.id, [])
        acts_summary = self._acts_summary(current_acts, paid_sum, row.type)

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
            "paid_sum": paid_sum,
            "remaining_sum": remaining_sum,
            "paid_label": paid_label,
            "acts_sum": acts_summary["acts_sum"],
            "acts_count": acts_summary["acts_count"],
            "acts_counted": acts_summary["acts_counted"],
            "debt_sum": acts_summary["debt_sum"],
            "receivable_sum": acts_summary["receivable_sum"],
            "acts": acts_summary["acts"],
            "payments": current_payments,
            "comment": row.comment,
            "statuses": statuses,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(base_users_by_id.get(row.created_by)),
        }

        if detail:
            current_parties = parties if parties is not None else self.repo.get_parties(contract_id=row.id)

            all_counterparty_ids = {row.customer_id, row.contractor_id}
            for p in current_parties:
                all_counterparty_ids.add(p.counterparties_id)
            if counterparty_names is None:
                all_counterparty_names = self._get_counterparty_names(list(all_counterparty_ids))
            else:
                all_counterparty_names = counterparty_names

            current_roles = roles if roles is not None else self.repo.get_user_roles(contract_id=row.id)
            current_work_contracts = (
                work_contracts if work_contracts is not None else self.repo.get_work_contracts(contract_id=row.id)
            )

            all_user_ids = {row.created_by}
            for p in current_parties:
                all_user_ids.add(p.created_by)
                if p.updated_by:
                    all_user_ids.add(p.updated_by)
            for role in current_roles:
                all_user_ids.update({role.user_id, role.created_by})
            for wc in current_work_contracts:
                all_user_ids.add(wc.created_by)

            current_users = users_by_id if users_by_id is not None else self._get_users_map(list(all_user_ids))
            if work_types_map is None:
                current_work_types_map = {wt.id: wt.name for wt in self.repo.get_work_types()}
            else:
                current_work_types_map = work_types_map

            result["created_by_user"] = self._map_user(current_users.get(row.created_by))

            result["parties"] = [
                self._serialize_party(p, all_counterparty_names, current_users) for p in current_parties
            ]
            result["user_roles"] = [
                self._serialize_user_role(r, current_users) for r in current_roles
            ]
            result["work_types"] = [
                self._serialize_work_contract(wc, current_work_types_map, current_users) for wc in current_work_contracts
            ]
            current_objects = objects if objects is not None else self.repo.get_contract_objects(contract_id=row.id)
            result["objects"] = [
                self._serialize_contract_object(o) for o in current_objects
            ]

        return result

    def create_contract(self, payload: ContractCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data.pop("objects", None)
        objects = [o.model_dump() for o in payload.objects]  # object_type keeps its default "object"
        data["created_by"] = created_by

        contractor_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("contractor_id", ""))
        customer_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("customer_id", ""))

        contract_year = data.get("date").year if data.get("date") else None

        if contractor_internal:
            data["type"] = "buyer"
            data["internal_num"] = str(self.repo.count_contracts_by_internal_party(data["contractor_id"], "contractor", "buyer", contract_year) + 1)
        elif customer_internal:
            data["type"] = "provider"
            data["internal_num"] = str(self.repo.count_contracts_by_internal_party(data["customer_id"], "customer", "provider", contract_year) + 1)

        if "type" not in data:
            if payload.type:
                data["type"] = payload.type
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contract type is required when neither party is internal",
                )

        created = self.repo.create_contract(data)
        doc_type_name = None
        if created.document_type_id:
            dt = self.repo.get_document_type_by_id(created.document_type_id)
            if dt:
                doc_type_name = dt.name
        log_msg = f"создал договор {doc_type_name or ''} {created.name or ''} № {created.num or ''}".strip()
        self.repo.create_log(created.id, "contract", log_msg, created_by)
        seen = set()
        for obj in objects:  # several objects can be given right in the create request
            key = (obj["object_id"], obj["object_type"])
            if key in seen:
                continue
            seen.add(key)
            added = self.repo.create_contract_object({"contract_id": created.id, **obj})
            object_name = self._resolve_object_name(added)
            self.repo.create_log(created.id, "contract", f"добавил объект {object_name or added.object_id}", created_by)
        if seen:
            self._sync_information_status(created.id, created_by)
        # with objects in the request the full view (which lists them) is returned
        return self._build_contract_response(created, detail=bool(seen))

    def update_contract(self, contract_id: int, payload: ContractUpdate, user_id: str):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        old = {
            "num": row.num,
            "internal_num": row.internal_num,
            "date": row.date,
            "document_type_id": row.document_type_id,
            "name": row.name,
            "customer_id": row.customer_id,
            "contractor_id": row.contractor_id,
            "type": row.type,
            "sum": row.sum,
            "comment": row.comment,
        }

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        updated = self.repo.save_contract(row)

        logs = []
        type_labels = {"provider": "поставщик", "buyer": "покупатель"}

        if "customer_id" in data and data["customer_id"] != old["customer_id"]:
            names = self._get_counterparty_names([old["customer_id"], data["customer_id"]])
            logs.append(f"изменил заказчика с {names.get(old['customer_id'], old['customer_id'])} на {names.get(data['customer_id'], data['customer_id'])}")

        if "contractor_id" in data and data["contractor_id"] != old["contractor_id"]:
            names = self._get_counterparty_names([old["contractor_id"], data["contractor_id"]])
            logs.append(f"изменил подрядчика с {names.get(old['contractor_id'], old['contractor_id'])} на {names.get(data['contractor_id'], data['contractor_id'])}")

        if "date" in data:
            old_date_str = old["date"].strftime("%d.%m.%Y") if old["date"] else None
            new_date_str = data["date"].strftime("%d.%m.%Y") if data["date"] else None
            if old_date_str != new_date_str:
                if data["date"] is None:
                    logs.append(f"удалил дату договора {old_date_str}")
                elif old["date"] is None:
                    logs.append(f"добавил дату договора {new_date_str}")
                else:
                    logs.append(f"изменил дату договора с {old_date_str} на {new_date_str}")

        if "num" in data and data["num"] != old["num"]:
            if data["num"] is None and old["num"] is not None:
                logs.append(f"удалил номер договора {old['num']}")
            else:
                logs.append(f"изменил номер договора с {old['num'] or '—'} на {data['num']}")

        if "internal_num" in data and data["internal_num"] != old["internal_num"]:
            if data["internal_num"] is None and old["internal_num"] is not None:
                logs.append(f"удалил внутренний номер договора {old['internal_num']}")
            else:
                logs.append(f"изменил внутренний номер договора с {old['internal_num'] or '—'} на {data['internal_num']}")

        if "document_type_id" in data and data["document_type_id"] != old["document_type_id"]:
            old_dt = self.repo.get_document_type_by_id(old["document_type_id"])
            new_dt = self.repo.get_document_type_by_id(data["document_type_id"])
            logs.append(f"изменил тип документа с {(old_dt.name if old_dt else old['document_type_id'])} на {(new_dt.name if new_dt else data['document_type_id'])}")

        if "name" in data and data["name"] != old["name"]:
            if data["name"] is None and old["name"] is not None:
                logs.append(f"удалил наименование договора {old['name']}")
            else:
                logs.append(f"изменил наименование договора с {old['name'] or '—'} на {data['name']}")

        if "type" in data and data["type"] != old["type"]:
            logs.append(f"изменил тип договора с {type_labels.get(old['type'], old['type'])} на {type_labels.get(data['type'], data['type'])}")

        if "sum" in data and data["sum"] != old["sum"]:
            if data["sum"] is None and old["sum"] is not None:
                logs.append(f"удалил сумму договора {old['sum']}")
            else:
                logs.append(f"изменил сумму договора с {old['sum'] or '—'} на {data['sum']}")

        if "comment" in data and data["comment"] != old["comment"]:
            if old["comment"] is None:
                logs.append(f"добавил примечание: {data['comment']}")
            else:
                logs.append(f"изменил примечание с {old['comment']} на {data['comment']}")

        for msg in logs:
            self.repo.create_log(contract_id, "contract", msg, user_id)

        self._sync_information_status(contract_id, user_id)

        return self._build_contract_response(updated)

    def delete_contract(self, contract_id: int, user_id: str):
        row = self.repo.get_contract_by_id(contract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        doc_type_name = None
        if row.document_type_id:
            dt = self.repo.get_document_type_by_id(row.document_type_id)
            if dt:
                doc_type_name = dt.name
        parts = [p for p in [doc_type_name, row.name, "№", row.num] if p]
        full_name = " ".join(parts)
        self.repo.create_log(contract_id, "contract", f"удалил договор {full_name}", user_id)
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
        row.updated_at = msk_now()
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

    def get_my_files(self, user_id: str) -> list[dict]:
        contract_ids = self.repo.get_contract_ids_by_user(user_id)
        if not contract_ids:
            return []
        contracts = self.repo.get_contracts_by_ids(contract_ids)
        files = self.repo.get_files_by_contract_ids(contract_ids)
        files_by_contract: dict[int, list[dict]] = {}
        for f in files:
            files_by_contract.setdefault(f.contract_id, []).append(self._serialize_file(f))
        result = []
        for c in contracts:
            doc_type_name = None
            if c.document_type_id:
                dt = self.repo.get_document_type_by_id(c.document_type_id)
                if dt:
                    doc_type_name = dt.name
            full_name = " ".join(part for part in [doc_type_name, c.name, "№", c.num] if part).strip()
            entry = {
                "id": c.id,
                "full_name": full_name,
                "type": c.type,
                "files": files_by_contract.get(c.id, []),
            }
            result.append(entry)
        return result

    def get_files_history(self, contract_id: int):
        rows = self.repo.get_files_history(contract_id)
        return [self._serialize_file(r) for r in rows]

    def get_file(self, file_id: str):
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return self._serialize_file(row)

    def upload(self, contract_id: int, original_name: str, file_bytes: bytes, uploaded_by: str, contract_folder_id: str | None = None, file_type: str | None = None):
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_CONTRACT_FILES_DIR, str(contract_id))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        effective_type = file_type if extension in {"pdf", "doc", "docx", "xls", "xlsx"} else None
        created = self.repo.create_file({
            "contract_id": contract_id,
            "contract_folder_id": contract_folder_id,
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": uploaded_by,
            "type": effective_type,
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

    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def get_preview(self, file_id: str) -> str:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        ext = Path(row.file_path).suffix.lower()
        if ext == ".pdf":
            return row.file_path

        if ext not in self.PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")

        cached = Path(row.file_path).parent / f"{Path(row.file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), row.file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(row.file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversion produced no output")

        return str(cached)

    def update_file(self, file_id: str, payload: ContractFileUpdate, user_id: str):
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        old_name = row.original_name
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save_file(row)
        if "original_name" in data and data["original_name"] != old_name:
            self.repo.create_log(updated.contract_id, "contract", f"изменил название файла с {old_name} на {data['original_name']}", user_id)
            if self.documents_list_repo:
                self.documents_list_repo.rename_by_linked_file_id(updated.id, data["original_name"])
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
        if self.documents_list_repo:
            self.documents_list_repo.unlink_by_linked_file_id(file_id)
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

    def _resolve_object_name(self, row):
        if not self.reference_repo:
            return None
        if row.object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([row.object_id])
            return objs[0].short_name if objs else None
        elif row.object_type == "object_levels_id":
            return self.reference_repo.resolve_object_name(row.object_id)
        return None

    def _serialize_contract_object(self, row, reference_repo=None):
        object_name = self._resolve_object_name(row)
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": object_name,
        }

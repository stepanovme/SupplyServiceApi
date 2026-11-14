from fastapi import HTTPException, status

from app.models.receipt_contract import ReceiptContractCreate, ReceiptContractUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.receipt_contract_repository import ReceiptContractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository


class ReceiptContractService:
    def __init__(
        self,
        repo: ReceiptContractRepository,
        auth_user_repo: AuthUserRepository | None = None,
        contract_repo: ContractRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.contract_repo = contract_repo
        self.reference_repo = reference_repo

    def _get_users_map(self, user_ids):
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
        return {"id": user.id, "short_fio": short_fio or None}

    def _serialize(self, row, users_by_id=None):
        users_by_id = users_by_id if users_by_id is not None else self._get_users_map([row.created_by])
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "sum": row.sum,
            "date": row.date,
            "comment": row.comment,
            "created_by": row.created_by,
            "created_by_name": self._map_user(users_by_id.get(row.created_by)),
            "created_at": row.created_at,
        }

    def _serialize_list(self, rows):
        user_ids = {row.created_by for row in rows if row.created_by}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize(row, users_by_id) for row in rows]

    def _require_contract(self, contract_id: int) -> None:
        if not self.contract_repo:
            return
        contract = self.contract_repo.get_contract_by_id(contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    def get_by_contract(self, contract_id: int):
        rows = self.repo.get_by_contract_id(contract_id)
        return self._serialize_list(rows)

    def get_by_object(self, object_id: str):
        if not self.contract_repo:
            return []

        level_ids = self.reference_repo.get_level_ids_by_object_ids([object_id]) if self.reference_repo else set()
        object_ids = [object_id, *level_ids]

        contract_objects = self.contract_repo.get_contract_objects_by_object_ids(object_ids)
        contract_ids = sorted({obj.contract_id for obj in contract_objects}, reverse=True)
        if not contract_ids:
            return []

        rows = self.repo.get_by_contract_ids(contract_ids)
        return self._serialize_list(rows)

    def create(self, payload: ReceiptContractCreate, created_by: str):
        self._require_contract(payload.contract_id)
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create(data)
        return self._serialize(created)

    def update(self, receipt_id: int, payload: ReceiptContractUpdate):
        row = self.repo.get_by_id(receipt_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, receipt_id: int):
        row = self.repo.get_by_id(receipt_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
        self.repo.delete(row)

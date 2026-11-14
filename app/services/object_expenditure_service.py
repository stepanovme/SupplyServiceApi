from fastapi import HTTPException, status

from app.models.object_expenditure import ObjectExpenditureCreate, ObjectExpenditureUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.object_expenditure_repository import ObjectExpenditureRepository


class ObjectExpenditureService:
    def __init__(
        self,
        repo: ObjectExpenditureRepository,
        auth_user_repo: AuthUserRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

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
            "object_id": row.object_id,
            "type": row.type,
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

    def get_by_object(self, object_id: str):
        rows = self.repo.get_by_object_id(object_id)
        return self._serialize_list(rows)

    def create(self, payload: ObjectExpenditureCreate, created_by: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        created = self.repo.create(data)
        return self._serialize(created)

    def update(self, expenditure_id: int, payload: ObjectExpenditureUpdate):
        row = self.repo.get_by_id(expenditure_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expenditure not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, expenditure_id: int):
        row = self.repo.get_by_id(expenditure_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expenditure not found")
        self.repo.delete(row)

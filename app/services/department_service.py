from fastapi import HTTPException, status

from app.database import msk_now
from app.models.department import (
    Department,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentUser,
    DepartmentUserCreate,
    DepartmentUserUpdate,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.auth_user_repository import AuthUserRepository


class DepartmentService:
    def __init__(self, repo: DepartmentRepository, auth_user_repo: AuthUserRepository | None = None) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    # --- Department ---

    def get_all(self) -> list[dict]:
        return [self._serialize(r) for r in self.repo.get_all()]

    def get_my(self, user_id: str) -> list[dict]:
        return [self._serialize(r) for r in self.repo.get_by_user(user_id)]

    def get_by_id(self, dept_id: int) -> dict:
        row = self.repo.get_by_id(dept_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        return self._serialize(row)

    def create(self, payload: DepartmentCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, dept_id: int, payload: DepartmentUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(dept_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, dept_id: int) -> None:
        row = self.repo.get_by_id(dept_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        self.repo.delete(row)

    # --- DepartmentUser ---

    def get_users_by_department(self, departament_id: int) -> list[dict]:
        rows = self.repo.get_users_by_department(departament_id)
        return [self._serialize_user(r) for r in rows]

    def create_user(self, payload: DepartmentUserCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create_user(data)
        return self._serialize_user(row)

    def update_user(self, membership_id: str, payload: DepartmentUserUpdate) -> dict:
        row = self.repo.get_user_by_id(membership_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department user not found")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        updated = self.repo.save_user(row)
        return self._serialize_user(updated)

    def delete_user(self, membership_id: str) -> None:
        row = self.repo.get_user_by_id(membership_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department user not found")
        self.repo.delete_user(row)

    # --- Serialization ---

    def _map_user(self, user) -> dict | None:
        if not user:
            return None
        surname = getattr(user, "surname", "") or ""
        name = getattr(user, "name", "") or ""
        patronymic = getattr(user, "patronymic", "") or ""
        short_fio = f"{surname} {name[0]}.{patronymic[0]}." if surname and name else (surname or name or "")
        return {
            "id": user.id,
            "surname": surname,
            "name": name,
            "patronymic": patronymic,
            "short_fio": short_fio,
        }

    def _get_users_map(self, user_ids: list[str]) -> dict:
        if not self.auth_user_repo or not user_ids:
            return {}
        users = self.auth_user_repo.get_by_ids(user_ids)
        return {u.id: u for u in users}

    def _serialize(self, row: Department) -> dict:
        users_by_id = self._get_users_map([row.created_by, row.updated_by] if row.updated_by else [row.created_by])
        return {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if row.updated_by else None,
        }

    def _serialize_user(self, row: DepartmentUser) -> dict:
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return {
            "id": row.id,
            "departament_id": row.departament_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)),
            "role_id": row.role_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
        }

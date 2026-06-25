from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.specification import (
    DEFAULT_SPECIFICATION_STATUS_ID,
    SpecificationCreate,
    SpecificationFileCreate,
    SpecificationFileUpdate,
    SpecificationItemCreate,
    SpecificationItemUpdate,
    SpecificationResponse,
    SpecificationUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.specification_repository import SpecificationRepository
from app.services.project_name_builder import build_project_name, load_project_reference_maps

BASE_SPECIFICATION_FILES_DIR = os.getenv(
    "SUPPLY_SPECIFICATION_FILES_DIR",
    "/home/webserver/models/supply/specification",
)


class SpecificationService:
    def __init__(
        self,
        repo: SpecificationRepository,
        auth_user_repo: AuthUserRepository,
        reference_repo: ReferenceObjectRepository,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    def get_all(self, object_levels_id: str | None = None):
        rows = self.repo.get_by_object_levels_id(object_levels_id) if object_levels_id else self.repo.get_all()
        return self._serialize(rows)

    def get_by_object_levels_id(self, object_levels_id: str, status_id: str | None = None):
        return self._serialize(self.repo.get_by_object_levels_id(object_levels_id, status_id))

    def get_by_id(self, specification_id: str):
        row = self.repo.get_by_id(specification_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")
        return self._serialize([row])[0]

    def create(self, payload: SpecificationCreate, user_id: str):
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        data["created_by"] = user_id
        data.setdefault("status_id", DEFAULT_SPECIFICATION_STATUS_ID)
        created = self.repo.create(data)
        return self.get_by_id(created.id)

    def update(self, specification_id: str, payload: SpecificationUpdate):
        row = self.repo.get_by_id(specification_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self.get_by_id(updated.id)

    def delete(self, specification_id: str):
        row = self.repo.get_by_id(specification_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")
        self.repo.delete(row)
        return None

    def get_summary(self, specification_id: str) -> list[dict]:
        return self.repo.get_summary(specification_id)

    def get_files(self, specification_id: str):
        self._ensure_parent_exists(specification_id)
        return [self._serialize_file(row) for row in self.repo.get_files(specification_id)]

    def upload_file(
        self,
        specification_id: str,
        original_name: str,
        file_bytes: bytes,
        user_id: str,
    ):
        self._ensure_parent_exists(specification_id)
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_SPECIFICATION_FILES_DIR, specification_id)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        created = self.repo.create_file(
            specification_id,
            {
                "original_name": original_name,
                "storage_name": storage_name,
                "file_path": file_path,
                "created_by": user_id,
            },
        )
        return self._serialize_file(created)

    def update_file(self, specification_id: str, file_id: str, payload: SpecificationFileUpdate):
        row = self.repo.get_file_by_id(specification_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification file not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_file(row)
        return self._serialize_file(updated)

    def delete_file(self, specification_id: str, file_id: str):
        row = self.repo.get_file_by_id(specification_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification file not found")
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)
        return None

    def get_file_download(self, specification_id: str, file_id: str) -> tuple[str, str]:
        row = self.repo.get_file_by_id(specification_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification file not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification file not found on server")
        return row.file_path, row.original_name or row.storage_name or "file"

    def get_items(self, specification_id: str):
        self._ensure_parent_exists(specification_id)
        return [self._serialize_item(row) for row in self.repo.get_items(specification_id)]

    def get_item_by_id(self, specification_id: str, item_id: str):
        row = self.repo.get_item_by_id(specification_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification item not found")
        return self._serialize_item(row)

    def create_item(self, specification_id: str, payload: SpecificationItemCreate, user_id: str):
        self._ensure_parent_exists(specification_id)
        data = self._normalize_item_payload(payload.model_dump(exclude_unset=True))
        data.setdefault("num", self.repo.get_next_item_num(specification_id))
        data["created_by"] = user_id
        created = self.repo.create_item(specification_id, data)
        return self._serialize_item(created)

    def update_item(self, specification_id: str, item_id: str, payload: SpecificationItemUpdate):
        row = self.repo.get_item_by_id(specification_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification item not found")
        data = self._normalize_item_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_item(row)
        return self._serialize_item(updated)

    def delete_item(self, specification_id: str, item_id: str):
        row = self.repo.get_item_by_id(specification_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification item not found")
        self.repo.delete_item(row)
        return None

    def _serialize(self, rows) -> list[dict]:
        status_ids = [row.status_id for row in rows]
        user_ids = [row.created_by for row in rows]
        object_level_ids = [row.object_levels_id for row in rows if row.object_levels_id]
        status_names = self.repo.get_status_names(status_ids)
        users = {user.id: user for user in self.auth_user_repo.get_by_ids(user_ids)}
        project_names = self._build_project_names(object_level_ids)
        spec_ids = [row.id for row in rows if row.id]
        chat_ids_map = self.repo.get_chat_ids_by_specification(spec_ids)
        return [
            {
                "id": row.id,
                "chat_id": chat_ids_map.get(row.id),
                "name": row.name,
                "comment": row.comment,
                "object_levels_id": row.object_levels_id,
                "project_name": project_names.get(row.object_levels_id),
                "created_at": row.created_at,
                "created_by": row.created_by,
                "created_by_user": self._get_user_full_name(users.get(row.created_by)),
                "status_id": row.status_id,
                "status_name": status_names.get(row.status_id),
                "files": [self._serialize_file(file_row) for file_row in self.repo.get_files(row.id)],
            }
            for row in rows
        ]

    @staticmethod
    def _serialize_file(row) -> dict:
        return {
            "id": row.id,
            "specification_id": row.specification_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "file_path": row.file_path,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def _serialize_item(self, row) -> dict:
        user = None
        users = self.auth_user_repo.get_by_ids([row.created_by])
        if users:
            user = users[0]
        return {
            "id": row.id,
            "specification_id": row.specification_id,
            "num": row.num,
            "section_name": row.section_name,
            "name": row.name,
            "nomenclature_id": row.nomenclature_id,
            "unit_name": row.unit_name,
            "unit_id": row.unit_id,
            "quantity": row.quantity,
            "price": row.price,
            "sum": row.sum,
            "warehouse_category_name": row.warehouse_category_name,
            "warehouse_category_id": row.warehouse_category_id,
            "comment": row.comment,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._get_user_full_name(user),
        }

    def _ensure_parent_exists(self, specification_id: str) -> None:
        if not self.repo.get_by_id(specification_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")

    @staticmethod
    def _get_user_full_name(user) -> str:
        if not user:
            return ""
        parts = [getattr(user, "surname", None), getattr(user, "name", None), getattr(user, "patronymic", None)]
        return " ".join(part for part in parts if part)

    @staticmethod
    def _normalize_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("name", "comment", "object_levels_id", "status_id"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized

    @staticmethod
    def _normalize_item_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in (
            "section_name",
            "name",
            "nomenclature_id",
            "unit_name",
            "unit_id",
            "warehouse_category_name",
            "warehouse_category_id",
            "comment",
        ):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized

    def _build_project_names(self, object_level_ids: list[str]) -> dict[str, str]:
        unique_ids = list({object_level_id for object_level_id in object_level_ids if object_level_id})
        if not unique_ids or not self.reference_repo:
            return {}
        levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(self.reference_repo, unique_ids)
        return {
            object_level_id: build_project_name(
                object_level_id,
                levels_by_id,
                objects_by_id,
                contracts_by_id,
                work_types_by_id,
            )
            for object_level_id in unique_ids
        }

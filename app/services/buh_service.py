import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.database import msk_now
from app.models.buh import BuhAccessCreate, BuhFileUpdate, BuhFolderCreate, BuhFolderUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.buh_repository import BuhAccessRepository, BuhFileRepository, BuhFolderRepository
from app.repositories.department_repository import DepartmentRepository

BASE_BUH_DIR = os.getenv(
    "SUPPLY_BUH_FILES_DIR",
    "/home/webserver/models/supply/documents/buh",
)


class BuhService:
    def __init__(
        self,
        folder_repo: BuhFolderRepository,
        file_repo: BuhFileRepository,
        access_repo: BuhAccessRepository,
        auth_user_repo: AuthUserRepository | None = None,
        department_repo: DepartmentRepository | None = None,
    ) -> None:
        self.folder_repo = folder_repo
        self.file_repo = file_repo
        self.access_repo = access_repo
        self.auth_user_repo = auth_user_repo
        self.department_repo = department_repo

    # --- Folders ---

    def get_folders(self) -> list[dict]:
        rows = self.folder_repo.get_all()
        return [self._serialize_folder(r) for r in rows]

    def get_folder_tree(self) -> list[dict]:
        folders = self.folder_repo.get_all()
        files = self.file_repo.get_all_files()

        folders_map: dict[str, dict] = {}
        for f in folders:
            folders_map[f.id] = {**self._serialize_folder(f), "children": [], "files": []}

        root_files = []
        for f in files:
            file_data = self._serialize_file(f)
            if f.folder_id and f.folder_id in folders_map:
                folders_map[f.folder_id]["files"].append(file_data)
            else:
                root_files.append(file_data)

        roots = []
        for f_id, f_data in folders_map.items():
            folder_row = next((f for f in folders if f.id == f_id), None)
            if not folder_row:
                continue
            if folder_row.parent_id and folder_row.parent_id in folders_map:
                folders_map[folder_row.parent_id]["children"].append(f_data)
            else:
                roots.append(f_data)

        if root_files:
            roots.append({"id": None, "name": "Без папки", "children": [], "files": root_files})

        return roots

    def get_folder(self, folder_id: str) -> dict:
        row = self.folder_repo.get_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        return self._serialize_folder(row)

    def create_folder(self, payload: BuhFolderCreate, user_id: str) -> dict:
        if payload.parent_id:
            parent = self.folder_repo.get_by_id(payload.parent_id)
            if not parent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.folder_repo.create(data)
        return self._serialize_folder(created)

    def update_folder(self, folder_id: str, payload: BuhFolderUpdate, user_id: str) -> dict:
        row = self.folder_repo.get_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.folder_repo.save(row)
        return self._serialize_folder(updated)

    def delete_folder(self, folder_id: str) -> None:
        row = self.folder_repo.get_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        child_ids = self._collect_all_child_folder_ids(folder_id)
        all_ids = [folder_id] + child_ids
        files_in_folders = self.file_repo.get_by_folder_ids(all_ids)
        for f in files_in_folders:
            if f.file_path and os.path.exists(f.file_path):
                os.remove(f.file_path)
        self.file_repo.delete_by_folder_ids(all_ids)
        self.folder_repo.delete_by_ids(all_ids)

    def _collect_all_child_folder_ids(self, parent_id: str) -> list[str]:
        result: list[str] = []
        children = self.folder_repo.get_children(parent_id)
        for child in children:
            result.append(child.id)
            result.extend(self._collect_all_child_folder_ids(child.id))
        return result

    # --- Files ---

    def get_files(self, folder_id: str | None = None) -> list[dict]:
        rows = self.file_repo.get_all(folder_id)
        return [self._serialize_file(r) for r in rows]

    def get_file(self, file_id: str) -> dict:
        row = self.file_repo.get_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return self._serialize_file(row)

    def update_file(self, file_id: str, payload: BuhFileUpdate) -> dict:
        row = self.file_repo.get_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        self.file_repo.save(row)
        return self._serialize_file(row)

    def upload(
        self,
        original_name: str,
        mime_type: str | None,
        file_bytes: bytes,
        user_id: str,
        folder_id: str | None = None,
    ) -> dict:
        if folder_id:
            folder = self.folder_repo.get_by_id(folder_id)
            if not folder:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_BUH_DIR, folder_id or "_root")
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        md5_hash = hashlib.md5(file_bytes).hexdigest()

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        created = self.file_repo.create({
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or None,
            "mime_type": mime_type or "application/octet-stream",
            "file_size": len(file_bytes),
            "md5_hash": md5_hash,
            "file_path": file_path,
            "folder_id": folder_id,
            "uploaded_by": user_id,
        })
        return self._serialize_file(created)

    def get_download(self, file_id: str) -> tuple[str, str]:
        row = self.file_repo.get_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    def delete_file(self, file_id: str) -> None:
        row = self.file_repo.get_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.file_repo.delete(row)

    # --- My ---

    def get_my_files(self, user_id: str) -> list[dict]:
        if self.access_repo.has_global_access():
            files = self.file_repo.get_all()
            return [self._serialize_file(f) for f in files]

        accessible_user_ids = self.access_repo.get_user_ids_with_access()
        accessible_department_ids = self.access_repo.get_department_ids_with_access()

        user_department_ids: set[int] = set()
        if accessible_department_ids and self.department_repo:
            user_departments = self.department_repo.get_by_user(user_id)
            user_department_ids = {d.id for d in user_departments}

        file_ids: set[str] = set()

        uploaded_files = self.file_repo.get_by_uploaded_by(user_id)
        for f in uploaded_files:
            file_ids.add(f.id)

        if user_id in accessible_user_ids:
            all_files = self.file_repo.get_all_files()
            for f in all_files:
                file_ids.add(f.id)

        if user_department_ids & set(accessible_department_ids):
            all_files = self.file_repo.get_all_files()
            for f in all_files:
                file_ids.add(f.id)

        if not file_ids:
            return []

        files = self.file_repo.get_by_ids(list(file_ids))
        return [self._serialize_file(f) for f in files]

    # --- Access ---

    def get_access_list(self) -> list[dict]:
        rows = self.access_repo.get_all()
        result = []
        user_ids = {r.user_id for r in rows if r.user_id and r.user_id != "__all__"}
        department_ids = {r.department_id for r in rows if r.department_id is not None}

        users_by_id: dict = {}
        if user_ids and self.auth_user_repo:
            contacts = self.auth_user_repo.get_contacts_by_ids(list(user_ids))
            users_by_id = {c.id: c for c in contacts}

        departments_by_id: dict = {}
        if department_ids and self.department_repo:
            departments = [self.department_repo.get_by_id(did) for did in department_ids]
            departments_by_id = {d.id: d for d in departments if d}

        for r in rows:
            entry: dict = {
                "id": r.id,
                "created_at": r.created_at,
                "created_by": r.created_by,
            }
            if r.user_id == "__all__":
                entry["type"] = "all"
            elif r.user_id:
                user = users_by_id.get(r.user_id)
                entry["type"] = "user"
                entry["user_id"] = r.user_id
                entry["user_name"] = (
                    f"{user.surname} {user.name} {user.patronymic}".strip()
                    if user
                    else None
                )
            elif r.department_id:
                dept = departments_by_id.get(r.department_id)
                entry["type"] = "department"
                entry["department_id"] = r.department_id
                entry["department_name"] = dept.name if dept else None
            result.append(entry)
        return result

    def create_access(self, payload: BuhAccessCreate, user_id: str) -> dict:
        if not payload.user_id and not payload.department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or department_id is required",
            )
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.access_repo.create(data)
        return {"id": created.id, "user_id": created.user_id, "department_id": created.department_id}

    def delete_access(self, access_id: str) -> None:
        row = self.access_repo.get_by_id(access_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access rule not found")
        self.access_repo.delete(row)

    # --- Serialization ---

    @staticmethod
    def _serialize_folder(row) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "parent_id": row.parent_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _serialize_file(row) -> dict:
        return {
            "id": row.id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "mime_type": row.mime_type,
            "file_size": row.file_size,
            "md5_hash": row.md5_hash,
            "folder_id": row.folder_id,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
        }

import os
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.database import msk_now
from app.models.upd_registry import (
    UpdCreate, UpdFileUpdate, UpdFolderCreate, UpdFolderUpdate, UpdObjectsAdd,
    UpdRegistry, UpdStatusCreate, UpdUpdate, UpdUserRoleCreate, UpdUserRoleUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.documents_link_repository import DocumentsLinkRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.upd_registry_repository import UpdRegistryRepository

UPD_REGISTRY_FILES_DIR = os.getenv("SUPPLY_UPD_REGISTRY_FILES_DIR", "/home/webserver/models/supply/upd_registry")
PARTY_FIELDS = {
    "buyer_id": "Покупатель", "seller_id": "Продавец",
    "shipper_id": "Грузоотправитель", "consignee_id": "Грузополучатель",
}
LOGGED_FIELDS = {"num": "номер", "date": "дата", "sum": "сумма", "comment": "комментарий", "is_signed": "подпись", **{k: v.lower() for k, v in PARTY_FIELDS.items()}}


class UpdRegistryService:
    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def __init__(
        self,
        repo: UpdRegistryRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        documents_list_repo: DocumentsListRepository | None = None,
        department_repo=None,
        doc_access_service=None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.documents_list_repo = documents_list_repo
        self.department_repo = department_repo
        self.doc_access_service = doc_access_service

    # --- CRUD ---
    def get_all(self, signed: bool | None = None) -> list[dict]:
        return self._filter_signed(self._serialize_many(self.repo.get_all()), signed)

    @staticmethod
    def _filter_signed(items: list[dict], signed: bool | None) -> list[dict]:
        return items if signed is None else [i for i in items if i["is_signed"] == signed]

    def get_my(self, user_id: str, signed: bool | None = None) -> list[dict]:
        ids = self.repo.get_ids_by_user(user_id)
        if self.doc_access_service and self.department_repo:
            dept_ids = self.department_repo.get_department_ids_for_user(user_id)
            extra = self.doc_access_service.get_additional_visible_ids(
                "upd", user_id, dept_ids, self.repo.get_all_ids, self.repo.get_ids_by_counterparty,
            )
            ids = list(set(ids + extra))
        return self._filter_signed(self._serialize_many(self.repo.get_by_ids(ids)), signed)

    def get_by_object(self, object_id: str, signed: bool | None = None) -> list[dict]:
        return self._filter_signed(self._serialize_many(self.repo.get_by_ids(self.repo.get_ids_by_object(object_id))), signed)

    def get_by_id(self, upd_id: int) -> dict:
        return self._serialize(self._get(upd_id), detail=True)

    def create(self, payload: UpdCreate, user_id: str) -> dict:
        data = payload.model_dump()
        objects = data.pop("objects", []) or []
        self._check_parties(data)
        self._check_objects(objects)
        data["created_by"] = user_id
        if data.get("is_signed"):
            data["signed_at"], data["signed_by"] = msk_now(), user_id
        try:
            row = self.repo.create(data)
            self.repo.db.add(self._role(row.id, user_id, "creator", user_id))
            self._attach_objects(row.id, objects, user_id)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.add_log(row.id, user_id, "УПД добавлен")
        return self._serialize(row, detail=True)

    def update(self, upd_id: int, payload: UpdUpdate, user_id: str) -> dict:
        row = self._get(upd_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize(row, detail=True)
        self._check_parties(updates)
        changed = [LOGGED_FIELDS[k] for k, v in updates.items() if k in LOGGED_FIELDS and getattr(row, k) != v and k != "is_signed"]
        if updates.get("is_signed") is not None and bool(row.is_signed) != updates["is_signed"]:
            changed.append("УПД подписан" if updates["is_signed"] else "подпись снята")
        if updates.get("is_signed") is None:
            updates.pop("is_signed", None)  # null = не менять
        was_signed = bool(row.is_signed)
        for key, value in updates.items():
            setattr(row, key, value)
        if "is_signed" in updates and bool(row.is_signed) != was_signed:
            row.signed_at, row.signed_by = (msk_now(), user_id) if row.is_signed else (None, None)
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.commit()
        if changed:
            self.repo.add_log(upd_id, user_id, "Изменено: " + ", ".join(changed))
        return self._serialize(row, detail=True)

    def delete(self, upd_id: int) -> None:
        row = self._get(upd_id)
        for f in self.repo.get_files(upd_id):
            self._remove_from_disk(f.file_path)
        DocumentsLinkRepository(self.repo.db).delete_for_document("upd", str(upd_id))
        self.repo.delete(row)

    def get_history(self, upd_id: int) -> list[dict]:
        self._get(upd_id)
        rows = self.repo.get_logs(upd_id)
        users = self._get_users_map([r.user_id for r in rows])
        return [{"id": r.id, "upd_id": r.upd_id, "message": r.message, "created_at": r.created_at,
                 "user_id": r.user_id, "user": self._map_user(users.get(r.user_id))} for r in rows]

    # --- objects ---
    def get_objects(self, upd_id: int) -> list[dict]:
        self._get(upd_id)
        return [self._serialize_object(o) for o in self.repo.get_objects(upd_id)]

    def add_objects(self, upd_id: int, payload: UpdObjectsAdd, user_id: str) -> list[dict]:
        self._get(upd_id)
        objects = [o.model_dump() for o in payload.objects]
        self._check_objects(objects)
        try:
            self._attach_objects(upd_id, objects, user_id)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.add_log(upd_id, user_id, "Добавлены объекты")
        return [self._serialize_object(o) for o in self.repo.get_objects(upd_id)]

    def delete_object(self, upd_id: int, obj_id: int, user_id: str) -> list[dict]:
        self._get(upd_id)
        row = self.repo.get_object(upd_id, obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD object not found")
        self.repo.delete_object(row)
        self.repo.commit()
        self.repo.add_log(upd_id, user_id, "Объект убран")
        return [self._serialize_object(o) for o in self.repo.get_objects(upd_id)]

    def _attach_objects(self, upd_id: int, objects: list[dict], user_id: str) -> None:
        existing = {(o.object_id, o.object_type) for o in self.repo.get_objects(upd_id)}
        for obj in objects:
            key = (obj["object_id"], obj["object_type"])
            if key in existing:
                continue
            existing.add(key)
            self.repo.add_object(upd_id, key[0], key[1], user_id)
        self.repo.flush()

    def _check_objects(self, objects: list[dict]) -> None:
        if not self.reference_repo:
            return
        missing = [o["object_id"] for o in objects if not self._object_name(o["object_id"], o["object_type"])]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Объекты не найдены: {', '.join(missing)}")

    def _check_parties(self, data: dict) -> None:
        if not self.reference_repo:
            return
        ids = [data[k] for k in PARTY_FIELDS if data.get(k)]
        if not ids:
            return
        names = self.reference_repo.get_counterparty_names(list(set(ids)))
        for field, label in PARTY_FIELDS.items():
            if data.get(field) and data[field] not in names:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label}: контрагент не найден")

    # --- roles ---
    @staticmethod
    def _role(upd_id: int, user_id: str, role: str, created_by: str):
        from app.models.upd_registry import UpdRegistryUserRole
        return UpdRegistryUserRole(id=str(uuid.uuid4()), upd_id=upd_id, user_id=user_id, role=role, created_by=created_by)

    def get_user_roles(self, upd_id: int) -> list[dict]:
        rows = self.repo.get_user_roles(upd_id)
        users = self._get_users_map([r.user_id for r in rows])
        return [self._serialize_role(r, users) for r in rows]

    def create_user_role(self, upd_id: int, payload: UpdUserRoleCreate, created_by: str) -> dict:
        self._get(upd_id)
        row = self.repo.create_user_role(upd_id, payload.user_id, payload.role, created_by)
        return self._serialize_role(row, self._get_users_map([row.user_id]))

    def update_user_role(self, role_id: str, payload: UpdUserRoleUpdate) -> dict:
        row = self.repo.get_user_role(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates:
            row = self.repo.update_user_role(row, updates)
        return self._serialize_role(row, self._get_users_map([row.user_id]))

    def delete_user_role(self, role_id: str) -> None:
        row = self.repo.get_user_role(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        self.repo.delete_user_role(row)

    # --- statuses ---
    def create_status(self, upd_id: int, payload: UpdStatusCreate, created_by: str) -> dict:
        self._get(upd_id)
        names = self.repo.get_status_names([payload.status_id])
        if payload.status_id not in names:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status not found")
        row = self.repo.create_status(upd_id, payload.status_id, created_by)
        self.repo.add_log(upd_id, created_by, f"Статус: {names[payload.status_id]}")
        return {"id": row.id, "upd_id": upd_id, "status_id": row.status_id, "status_name": names[payload.status_id],
                "created_by": row.created_by, "created_at": row.created_at}

    def get_statuses(self, upd_id: int) -> list[dict]:
        self._get(upd_id)
        rows = self.repo.get_statuses(upd_id)
        names = self.repo.get_status_names([r.status_id for r in rows])
        users = self._get_users_map([r.created_by for r in rows])
        return [{"id": r.id, "upd_id": r.upd_id, "status_id": r.status_id, "status_name": names.get(r.status_id),
                 "created_by": r.created_by, "created_by_user": self._map_user(users.get(r.created_by)),
                 "created_at": r.created_at} for r in rows]

    # --- folders ---
    def get_folders(self, upd_id: int) -> list[dict]:
        rows = self.repo.get_folders(upd_id)
        users = self._get_users_map([r.created_by for r in rows])
        return [self._serialize_folder(r, users) for r in rows]

    def create_folder(self, payload: UpdFolderCreate, created_by: str) -> dict:
        self._get(payload.upd_id)
        if payload.parent_id:
            parent = self.repo.get_folder(payload.parent_id)
            if not parent or parent.upd_id != payload.upd_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
        row = self.repo.create_folder(payload.upd_id, payload.name, created_by, payload.parent_id)
        return self._serialize_folder(row, self._get_users_map([row.created_by]))

    def update_folder(self, folder_id: str, payload: UpdFolderUpdate, user_id: str) -> dict:
        row = self.repo.get_folder(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("parent_id") == folder_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Папка не может быть вложена в себя")
        if updates:
            row.updated_by = user_id
            row = self.repo.update_folder(row, updates)
        return self._serialize_folder(row, self._get_users_map([row.created_by]))

    def delete_folder(self, folder_id: str) -> None:
        row = self.repo.get_folder(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        self.repo.delete_folder(row)

    def get_folder_tree(self, upd_id: int) -> list[dict]:
        folders = self.repo.get_folders(upd_id)
        files = self.repo.get_files(upd_id)
        users = self._get_users_map(list({f.created_by for f in folders} | {f.uploaded_by for f in files}))
        nodes = {f.id: {**self._serialize_folder(f, users), "children": [], "files": []} for f in folders}
        root_files = []
        for f in files:
            data = self._serialize_file(f, users)
            if f.folder_id and f.folder_id in nodes:
                nodes[f.folder_id]["files"].append(data)
            elif not f.folder_id:
                root_files.append(data)
        roots = []
        for f in folders:
            if f.parent_id and f.parent_id in nodes:
                nodes[f.parent_id]["children"].append(nodes[f.id])
            else:
                roots.append(nodes[f.id])
        if root_files:
            roots.append({"id": None, "name": "Без папки", "children": [], "files": root_files})
        return roots

    # --- files ---
    def upload_file(self, upd_id: int, file: UploadFile, user_id: str, folder_id: str | None = None, file_type: str | None = None) -> dict:
        self._get(upd_id)
        if folder_id:
            folder = self.repo.get_folder(folder_id)
            if not folder or folder.upd_id != upd_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        Path(UPD_REGISTRY_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{UPD_REGISTRY_FILES_DIR}/{storage_name}"
        with open(file_path, "wb") as out:
            out.write(file.file.read())
        record = self.repo.create_file({
            "id": str(uuid.uuid4()), "upd_id": upd_id, "original_name": file.filename or storage_name,
            "storage_name": storage_name, "extension": ext.lstrip("."), "file_path": file_path,
            "type": file_type or "original", "uploaded_by": user_id, "folder_id": folder_id,
        })
        self.repo.add_log(upd_id, user_id, f"Загружен файл: {record.original_name}")
        return self._serialize_file(record, self._get_users_map([user_id]))

    def get_files(self, upd_id: int) -> list[dict]:
        rows = self.repo.get_files(upd_id)
        users = self._get_users_map([r.uploaded_by for r in rows])
        return [self._serialize_file(r, users) for r in rows]

    def get_file(self, file_id: str) -> dict:
        row = self._get_file(file_id)
        return self._serialize_file(row, self._get_users_map([row.uploaded_by]))

    def update_file(self, file_id: str, payload: UpdFileUpdate, user_id: str) -> dict:
        row = self._get_file(file_id)
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("folder_id"):
            folder = self.repo.get_folder(updates["folder_id"])
            if not folder or folder.upd_id != row.upd_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        if updates:
            old_name = row.original_name
            row.updated_by = user_id
            row = self.repo.update_file(row, updates)
            if updates.get("original_name") and updates["original_name"] != old_name and self.documents_list_repo:
                self.documents_list_repo.rename_by_linked_file_id(row.id, updates["original_name"])
        return self._serialize_file(row, self._get_users_map([row.uploaded_by]))

    def get_download(self, file_id: str) -> tuple[str, str]:
        row = self._get_file(file_id)
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    def get_preview(self, file_id: str) -> str:
        path, _name = self.get_download(file_id)
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            return path
        if ext not in self.PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")
        cached = Path(path).parent / f"{Path(path).name}.preview.pdf"
        if cached.exists():
            return str(cached)
        result = subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), path],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")
        produced = cached.parent / f"{Path(path).stem}.pdf"
        if produced.exists():
            os.rename(str(produced), str(cached))
        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Preview generation failed")
        return str(cached)

    def delete_file(self, file_id: str, user_id: str | None = None) -> None:
        row = self._get_file(file_id)
        upd_id, name, path = row.upd_id, row.original_name, row.file_path
        self.repo.delete_file(row)
        self._remove_from_disk(path)
        if self.documents_list_repo:
            self.documents_list_repo.unlink_by_linked_file_id(file_id)
        if user_id:
            self.repo.add_log(upd_id, user_id, f"Удалён файл: {name}")

    @staticmethod
    def _remove_from_disk(path: str | None) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    # --- helpers / serialization ---
    def _get(self, upd_id: int) -> UpdRegistry:
        row = self.repo.get_by_id(upd_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD not found")
        return row

    def _get_file(self, file_id: str):
        row = self.repo.get_file(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return row

    def _serialize_many(self, rows: list[UpdRegistry]) -> list[dict]:
        objects = self.repo.get_objects_by_upd_ids([r.id for r in rows])
        return [self._serialize(r, objects=objects.get(r.id, [])) for r in rows]

    def _serialize(self, row: UpdRegistry, detail: bool = False, objects: list | None = None) -> dict:
        names = self._counterparty_names([getattr(row, f) for f in PARTY_FIELDS])
        current = self.repo.get_current_status(row.id)
        status_name = self.repo.get_status_names([current.status_id]).get(current.status_id) if current else None
        users = self._get_users_map([row.created_by])
        result = {
            "id": row.id, "num": row.num, "date": row.date, "sum": row.sum, "comment": row.comment,
            "is_signed": bool(row.is_signed), "signed_at": row.signed_at, "signed_by": row.signed_by,
            "objects": [self._serialize_object(o) for o in (objects if objects is not None else self.repo.get_objects(row.id))],
            "status_id": current.status_id if current else None, "status_name": status_name,
            "created_at": row.created_at, "created_by": row.created_by,
            "created_by_user": self._map_user(users.get(row.created_by)),
            "updated_at": row.updated_at, "updated_by": row.updated_by,
        }
        for field in PARTY_FIELDS:
            value = getattr(row, field)
            result[field] = value
            result[field.replace("_id", "_name")] = names.get(value) if value else None
        if detail:
            result["user_roles"] = self.get_user_roles(row.id)
            result["files"] = self.get_files(row.id)
            result["folders"] = self.get_folders(row.id)
            result["statuses"] = self.get_statuses(row.id)
        return result

    def _serialize_object(self, row) -> dict:
        return {"id": row.id, "upd_id": row.upd_id, "object_id": row.object_id, "object_type": row.object_type,
                "object_name": self._object_name(row.object_id, row.object_type),
                "created_at": row.created_at, "created_by": row.created_by}

    def _serialize_role(self, row, users: dict) -> dict:
        return {"id": row.id, "upd_id": row.upd_id, "user_id": row.user_id, "user": self._map_user(users.get(row.user_id)),
                "role": row.role, "created_at": row.created_at, "created_by": row.created_by}

    def _serialize_folder(self, row, users: dict) -> dict:
        return {"id": row.id, "upd_id": row.upd_id, "name": row.name, "parent_id": row.parent_id,
                "created_at": row.created_at, "created_by": row.created_by,
                "created_by_user": self._map_user(users.get(row.created_by)),
                "updated_at": row.updated_at, "updated_by": row.updated_by}

    def _serialize_file(self, row, users: dict | None = None) -> dict:
        users = users or {}
        return {"id": row.id, "upd_id": row.upd_id, "original_name": row.original_name, "storage_name": row.storage_name,
                "extension": row.extension, "type": row.type, "folder_id": row.folder_id,
                "uploaded_by": row.uploaded_by, "uploaded_by_user": self._map_user(users.get(row.uploaded_by)),
                "uploaded_at": row.uploaded_at, "updated_at": row.updated_at, "updated_by": row.updated_by}

    @staticmethod
    def _map_user(user) -> dict | None:
        if not user:
            return None
        surname = getattr(user, "surname", "") or ""
        name = getattr(user, "name", "") or ""
        patronymic = getattr(user, "patronymic", "") or ""
        short = f"{surname} {name[0]}.{patronymic[0]}." if surname and name and patronymic else (surname or name or "")
        return {"id": user.id, "surname": surname, "name": name, "patronymic": patronymic, "short_fio": short}

    def _get_users_map(self, user_ids: list[str]) -> dict:
        if not self.auth_user_repo or not user_ids:
            return {}
        return {u.id: u for u in self.auth_user_repo.get_by_ids(list(set(user_ids)))}

    def _counterparty_names(self, ids: list[str | None]) -> dict[str, str]:
        ids = [i for i in set(ids) if i]
        if not self.reference_repo or not ids:
            return {}
        return self.reference_repo.get_counterparty_names(ids)

    def _object_name(self, object_id: str | None, object_type: str | None) -> str | None:
        if not self.reference_repo or not object_id:
            return None
        if object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            return (objs[0].short_name or objs[0].full_name) if objs else None
        if object_type == "object_levels_id":
            return self.reference_repo.resolve_object_name(object_id)
        return None

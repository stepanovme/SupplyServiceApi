import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.database import msk_now
from app.models.act import (
    Act,
    ActCreate,
    ActObject,
    ActObjectsAdd,
    ActTypeCreate,
    ActFolderCreate,
    ActFolderUpdate,
    ActFileUpdate,
    ActUpdate,
    ActUserRoleCreate,
    ActUserRoleUpdate,
    ActStatusCreate,
)
from app.repositories.act_repository import ActRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

ACTS_FILES_DIR = "/home/webserver/models/supply/acts"


class ActService:
    def __init__(
        self,
        repo: ActRepository,
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

    # --- Types ---

    def get_act_types(self) -> list[dict]:
        return [{"id": t.id, "name": t.name} for t in self.repo.get_act_types()]

    def create_act_type(self, payload: ActTypeCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        data["created_at"] = msk_now()
        row = self.repo.create_act_type(data)
        return {"id": row.id, "name": row.name}

    # --- CRUD ---

    def get_all(self) -> list[dict]:
        return self._serialize_many(self.repo.get_all())

    def _serialize_many(self, rows: list[Act]) -> list[dict]:
        objects = self.repo.get_objects_by_act_ids([a.id for a in rows])
        return [self._serialize(a, objects=objects.get(a.id, [])) for a in rows]

    def get_by_id(self, act_id: int) -> dict:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        return self._serialize(row, detail=True)

    def get_by_contract(self, contract_id: int) -> list[dict]:
        """Acts linked to a contract through documents_links, each shown exactly as in the acts
        list (GET /acts) plus the link it came from."""
        from app.models.contract import Contract

        if not self.repo.db.query(Contract.id).filter(Contract.id == contract_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        links = self.repo.get_contract_act_links(contract_id)
        result = []
        acts = self.repo.get_acts_by_ids(list(links))
        objects = self.repo.get_objects_by_act_ids([a.id for a in acts])
        for act in acts:
            item = self._serialize(act, objects=objects.get(act.id, []))
            link = links[act.id]
            item["documents_link_id"] = link.id
            item["linked_at"] = link.created_at
            item["linked_by"] = link.created_by
            result.append(item)
        return result

    def get_my(self, user_id: str) -> list[dict]:
        ids = self.repo.get_act_ids_by_user(user_id)

        # Добавляем ID на основе document_access_settings
        if self.doc_access_service and self.department_repo:
            dept_ids = self.department_repo.get_department_ids_for_user(user_id)
            extra_ids = self.doc_access_service.get_additional_visible_ids(
                "act", user_id, dept_ids,
                self.repo.get_all_act_ids,
                self.repo.get_act_ids_by_counterparty,
            )
            ids = list(set(ids + extra_ids))

        if not ids:
            return []
        rows = self.repo.get_acts_by_ids(ids)
        return self._serialize_many(rows)

    def create(self, payload: ActCreate, created_by: str) -> dict:
        data = payload.model_dump()
        extra_objects = data.pop("objects", []) or []
        data["created_by"] = created_by
        row = self.repo.create(data)
        self.repo.create_user_role(row.id, created_by, "creator", created_by)

        # the legacy single object (the "main" one) and the new list end up in act_objects together
        wanted = []
        if row.object_id and row.object_type:
            wanted.append({"object_id": row.object_id, "object_type": row.object_type})
        wanted.extend(extra_objects)
        self._attach_objects(row, wanted, created_by)
        return self._serialize(row, detail=True)

    def update(self, act_id: int, payload: ActUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize(row, detail=True)
        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save(row)
        # a new main object is added to the list; the other objects stay (remove them via DELETE .../objects/{id})
        if updates.get("object_id") and row.object_type:
            self._attach_objects(row, [{"object_id": row.object_id, "object_type": row.object_type}], user_id)
        return self._serialize(row, detail=True)

    # --- Objects (several per act) ---

    def _attach_objects(self, act: Act, objects: list[dict], user_id: str) -> None:
        """Adds objects the act doesn't have yet (duplicates are ignored) and keeps the legacy
        acts.object_id / object_type pointing at the first one."""
        existing = {(o.object_id, o.object_type) for o in self.repo.get_objects(act.id)}
        try:
            for obj in objects:
                key = (obj["object_id"], obj["object_type"])
                if key in existing:
                    continue
                existing.add(key)
                self.repo.add(ActObject(act_id=act.id, object_id=key[0], object_type=key[1], created_by=user_id))
            self.repo.flush()
            self._sync_primary_object(act)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise

    def _sync_primary_object(self, act: Act) -> None:
        objects = self.repo.get_objects(act.id)
        current = (act.object_id, act.object_type)
        if any((o.object_id, o.object_type) == current for o in objects):
            return  # the main object is still in the list
        first = objects[0] if objects else None
        act.object_id = first.object_id if first else None
        act.object_type = first.object_type if first else None

    def get_objects(self, act_id: int) -> list[dict]:
        if not self.repo.get_by_id(act_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        return [self._serialize_object(o) for o in self.repo.get_objects(act_id)]

    def add_objects(self, act_id: int, payload: ActObjectsAdd, user_id: str) -> list[dict]:
        act = self.repo.get_by_id(act_id)
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        objects = [o.model_dump() for o in payload.objects]
        missing = [o["object_id"] for o in objects if self.reference_repo and not self._resolve_object_name_by(o["object_id"], o["object_type"])]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Объекты не найдены: {', '.join(missing)}")
        self._attach_objects(act, objects, user_id)
        return [self._serialize_object(o) for o in self.repo.get_objects(act_id)]

    def delete_object(self, act_id: int, obj_id: int, user_id: str) -> list[dict]:
        act = self.repo.get_by_id(act_id)
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        row = self.repo.get_object_by_id(act_id, obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act object not found")
        try:
            self.repo.delete_object(row)
            self.repo.flush()
            self._sync_primary_object(act)  # the next object becomes the main one
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return [self._serialize_object(o) for o in self.repo.get_objects(act_id)]

    def _serialize_object(self, row: ActObject) -> dict:
        return {
            "id": row.id,
            "act_id": row.act_id,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": self._resolve_object_name_by(row.object_id, row.object_type),
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def delete(self, act_id: int) -> None:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        self.repo.delete(row)

    # --- User roles ---

    def get_user_roles(self, act_id: int) -> list[dict]:
        rows = self.repo.get_user_roles(act_id)
        user_ids = [r.user_id for r in rows]
        users_by_id = self._get_users_map(user_ids)
        return [self._serialize_user_role(r, users_by_id) for r in rows]

    def create_user_role(self, act_id: int, payload: ActUserRoleCreate, created_by: str) -> dict:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        row = self.repo.create_user_role(act_id, payload.user_id, payload.role, created_by)
        users_by_id = self._get_users_map([row.user_id])
        return self._serialize_user_role(row, users_by_id)

    def update_user_role(self, role_id: str, payload: ActUserRoleUpdate) -> dict:
        row = self.repo.get_user_role(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            users_by_id = self._get_users_map([row.user_id])
            return self._serialize_user_role(row, users_by_id)
        updated = self.repo.update_user_role(row, updates)
        users_by_id = self._get_users_map([updated.user_id])
        return self._serialize_user_role(updated, users_by_id)

    def delete_user_role(self, role_id: str) -> None:
        row = self.repo.get_user_role(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        self.repo.delete_user_role(row)

    # --- Statuses ---

    def create_status(self, act_id: int, payload: ActStatusCreate, created_by: str) -> dict:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        created = self.repo.create_status(act_id, payload.status_id, created_by)
        status_name = self.repo.get_status_name(payload.status_id)
        return {
            "id": created.id,
            "act_id": created.act_id,
            "status_id": created.status_id,
            "status_name": status_name,
            "created_by": created.created_by,
            "created_at": created.created_at,
        }

    def get_statuses(self, act_id: int) -> list[dict]:
        rows = self.repo.get_statuses(act_id)
        status_ids = [r.status_id for r in rows]
        status_names = self.repo.get_status_names(status_ids)
        user_ids = [r.created_by for r in rows]
        users_by_id = self._get_users_map(user_ids)
        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "act_id": r.act_id,
                "status_id": r.status_id,
                "status_name": status_names.get(r.status_id),
                "created_by": r.created_by,
                "created_by_user": self._map_user(users_by_id.get(r.created_by)),
                "created_at": r.created_at,
            })
        return result

    # --- Folders ---

    def get_folders(self, act_id: int) -> list[dict]:
        rows = self.repo.get_folders(act_id)
        user_ids = [r.created_by for r in rows if r.created_by]
        users_by_id = self._get_users_map(user_ids)
        return [self._serialize_folder(r, users_by_id) for r in rows]

    def create_folder(self, payload: ActFolderCreate, created_by: str) -> dict:
        row = self.repo.get_by_id(payload.act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        created = self.repo.create_folder(payload.act_id, payload.name, created_by, payload.parent_id)
        users_by_id = self._get_users_map([created.created_by])
        return self._serialize_folder(created, users_by_id)

    def update_folder(self, folder_id: str, payload: ActFolderUpdate, user_id: str) -> dict:
        row = self.repo.get_folder(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            users_by_id = self._get_users_map([row.created_by])
            return self._serialize_folder(row, users_by_id)
        row.updated_by = user_id
        updated = self.repo.update_folder(row, updates)
        users_by_id = self._get_users_map([updated.created_by])
        return self._serialize_folder(updated, users_by_id)

    def delete_folder(self, folder_id: str) -> None:
        row = self.repo.get_folder(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        self.repo.delete_folder(row)

    def get_folder_tree(self, act_id: int) -> list[dict]:
        folders = self.repo.get_folders(act_id)
        files = self.repo.get_files(act_id)
        user_ids = {f.created_by for f in folders}
        for f in folders:
            if f.updated_by:
                user_ids.add(f.updated_by)
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
            file_data = self._serialize_file(f, users_by_id)
            parent_id = f.act_folder_id
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

    def get_files_history(self, act_id: int) -> list[dict]:
        rows = self.repo.get_files(act_id)
        user_ids = [r.uploaded_by for r in rows]
        users_by_id = self._get_users_map(user_ids)
        return [self._serialize_file(r, users_by_id) for r in rows]

    # --- Files ---

    def upload_file(self, act_id: int, file: UploadFile, user_id: str, act_folder_id: str | None = None, file_type: str | None = None) -> dict:
        row = self.repo.get_by_id(act_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")

        Path(ACTS_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{ACTS_FILES_DIR}/{storage_name}"

        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        record = self.repo.create_file({
            "id": str(uuid.uuid4()),
            "act_id": act_id,
            "original_name": file.filename or storage_name,
            "storage_name": storage_name,
            "extension": ext.lstrip("."),
            "file_path": file_path,
            "type": file_type or "original",
            "uploaded_by": user_id,
            "act_folder_id": act_folder_id,
        })
        return self._serialize_file(record)

    def get_files(self, act_id: int) -> list[dict]:
        rows = self.repo.get_files(act_id)
        user_ids = [r.uploaded_by for r in rows]
        users_by_id = self._get_users_map(user_ids)
        return [self._serialize_file(r, users_by_id) for r in rows]

    def update_file(self, file_id: str, payload: ActFileUpdate, user_id: str) -> dict:
        row = self.repo.get_file(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            users_by_id = self._get_users_map([row.uploaded_by])
            return self._serialize_file(row, users_by_id)
        old_name = row.original_name
        row.updated_by = user_id
        updated = self.repo.update_file(row, updates)
        if "original_name" in updates and updates["original_name"] != old_name and self.documents_list_repo:
            self.documents_list_repo.rename_by_linked_file_id(updated.id, updates["original_name"])
        users_by_id = self._get_users_map([updated.uploaded_by])
        return self._serialize_file(updated, users_by_id)

    def get_file(self, file_id: str) -> dict:
        row = self.repo.get_file(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        users_by_id = self._get_users_map([row.uploaded_by])
        return self._serialize_file(row, users_by_id)

    def get_download(self, file_id: str) -> tuple[str, str]:
        row = self.repo.get_file(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def get_preview(self, file_id: str) -> str:
        row = self.repo.get_file(file_id)
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

        import subprocess
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), row.file_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(row.file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Preview generation failed")
        return str(cached)

    def delete_file(self, file_id: str) -> None:
        row = self.repo.get_file(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        self.repo.delete_file(row)
        if self.documents_list_repo:
            self.documents_list_repo.unlink_by_linked_file_id(file_id)

    def get_file_path(self, filename: str) -> str:
        return f"{ACTS_FILES_DIR}/{filename}"

    # --- Serialization ---

    def _serialize(self, row: Act, detail: bool = False, objects: list | None = None) -> dict:
        act_type = self.repo.get_act_type(row.act_type_id)
        type_name = act_type.name if act_type else ""
        fullname = f"{type_name} №{row.num}"

        current_status = self.repo.get_current_status(row.id)
        status_name = None
        if current_status:
            status_name = self.repo.get_status_name(current_status.status_id)

        counterparty_ids = {row.customer_id, row.contractor_id}
        counterparty_names = self._get_counterparty_names(list(counterparty_ids))

        object_name = self._resolve_object_name(row)

        user_ids = [row.created_by]
        users_by_id = self._get_users_map(user_ids)

        result = {
            "id": row.id,
            "act_type_id": row.act_type_id,
            "act_type_name": type_name,
            "num": row.num,
            "fullname": fullname,
            "date": row.date,
            "sum": row.sum,
            "comment": row.comment,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": object_name,
            "objects": [self._serialize_object(o) for o in (objects if objects is not None else self.repo.get_objects(row.id))],
            "customer_id": row.customer_id,
            "customer_name": counterparty_names.get(row.customer_id),
            "contractor_id": row.contractor_id,
            "contractor_name": counterparty_names.get(row.contractor_id),
            "status_id": current_status.status_id if current_status else None,
            "status_name": status_name,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
        }

        if detail:
            result["user_roles"] = self.get_user_roles(row.id)
            result["files"] = self.get_files(row.id)
            result["folders"] = self.get_folders(row.id)
            result["statuses"] = self.get_statuses(row.id)

        return result

    def _serialize_user_role(self, row, users_by_id: dict | None = None) -> dict:
        return {
            "id": row.id,
            "act_id": row.act_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)) if users_by_id else None,
            "role": row.role,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def _serialize_folder(self, row, users_by_id: dict | None = None) -> dict:
        return {
            "id": row.id,
            "act_id": row.act_id,
            "name": row.name,
            "parent_id": row.parent_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def _serialize_file(self, row, users_by_id: dict | None = None) -> dict:
        return {
            "id": row.id,
            "act_id": row.act_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "type": row.type,
            "act_folder_id": row.act_folder_id,
            "uploaded_by": row.uploaded_by,
            "uploaded_by_user": self._map_user(users_by_id.get(row.uploaded_by)) if users_by_id else None,
            "uploaded_at": row.uploaded_at,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def _map_user(self, user) -> dict | None:
        if not user:
            return None
        surname = getattr(user, "surname", "") or ""
        name = getattr(user, "name", "") or ""
        patronymic = getattr(user, "patronymic", "") or ""
        short_fio = f"{surname} {name[0]}.{patronymic[0]}." if surname and name and patronymic else (surname or name or "")
        return {"id": user.id, "surname": surname, "name": name, "patronymic": patronymic, "short_fio": short_fio}

    def _get_users_map(self, user_ids: list[str]) -> dict:
        if not self.auth_user_repo or not user_ids:
            return {}
        users = self.auth_user_repo.get_by_ids(user_ids)
        return {u.id: u for u in users}

    def _get_counterparty_names(self, counterparty_ids: list[str]) -> dict[str, str]:
        if not self.reference_repo or not counterparty_ids:
            return {}
        return self.reference_repo.get_counterparty_names(counterparty_ids)

    def _resolve_object_name(self, row: Act) -> str | None:
        return self._resolve_object_name_by(row.object_id, row.object_type)

    def _resolve_object_name_by(self, object_id: str | None, object_type: str | None) -> str | None:
        if not self.reference_repo or not object_id:
            return None
        if object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            if objs:
                return objs[0].short_name or objs[0].full_name
            return None
        elif object_type == "object_levels_id":
            return self.reference_repo.resolve_object_name(object_id)
        return None

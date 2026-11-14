import os
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.models.documents_list import DocumentsListCreate, DocumentsListUpdate
from app.repositories.act_repository import ActRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.letter_repository import LetterRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.act_service import ACTS_FILES_DIR
from app.services.contract_service import BASE_CONTRACT_FILES_DIR
from app.services.letter_service import BASE_LETTER_FILES_DIR

DOCUMENTS_FILES_DIR = "/home/webserver/models/supply/documents"

PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}


class DocumentsListService:
    def __init__(
        self,
        repo: DocumentsListRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        contract_repo: ContractRepository | None = None,
        act_repo: ActRepository | None = None,
        letter_repo: LetterRepository | None = None,
        department_repo=None,
        doc_access_service=None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.contract_repo = contract_repo
        self.act_repo = act_repo
        self.letter_repo = letter_repo
        self.department_repo = department_repo
        self.doc_access_service = doc_access_service

    # --- CRUD ---

    def get_all(self, unattached_only: bool = False) -> list[dict]:
        rows = self.repo.get_all(unattached_only)
        return self._serialize_rows(rows)

    def get_my(self, user_id: str, unattached_only: bool = False) -> list[dict]:
        ids = self.repo.get_document_ids_by_user(user_id)

        # Добавляем ID на основе document_access_settings
        if self.doc_access_service and self.department_repo:
            dept_ids = self.department_repo.get_department_ids_for_user(user_id)
            extra_ids = self.doc_access_service.get_additional_visible_ids(
                "document", user_id, dept_ids,
                self.repo.get_all_document_ids,
                self.repo.get_document_ids_by_counterparty,
            )
            ids = list(set(ids + extra_ids))

        if not ids:
            return []
        rows = [r for r in self.repo.get_all(unattached_only) if r.id in ids]
        return self._serialize_rows(rows)

    def get_by_id(self, document_id: int) -> dict:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return self._serialize_row(row)

    def _serialize_rows(self, rows) -> list[dict]:
        user_ids = set()
        for r in rows:
            user_ids.add(r.uploaded_by)
            if r.updated_by:
                user_ids.add(r.updated_by)
            if r.from_whom_id:
                user_ids.add(r.from_whom_id)
        users_by_id = self._get_users_map(list(user_ids))
        document_names = self._build_document_names(rows)
        party_ids = {pid for r in rows for pid in (r.customer_id, r.contractor_id) if pid}
        counterparty_names = self.reference_repo.get_counterparty_names(list(party_ids)) if self.reference_repo and party_ids else {}
        return [
            self._serialize_row(r, users_by_id, document_names=document_names, counterparty_names=counterparty_names)
            for r in rows
        ]

    def _serialize_row(self, row, users_by_id: dict | None = None, object_names: dict | None = None, document_names: dict | None = None, counterparty_names: dict | None = None) -> dict:
        if users_by_id is None:
            user_ids = {row.uploaded_by}
            if row.updated_by:
                user_ids.add(row.updated_by)
            if row.from_whom_id:
                user_ids.add(row.from_whom_id)
            users_by_id = self._get_users_map(list(user_ids))

        if counterparty_names is None:
            party_ids = [pid for pid in (row.customer_id, row.contractor_id) if pid]
            counterparty_names = self.reference_repo.get_counterparty_names(party_ids) if self.reference_repo and party_ids else {}

        document_name = None
        if row.document_id and row.document_type:
            if document_names is not None:
                document_name = document_names.get((row.document_type, row.document_id))
            else:
                document_name = self._resolve_document_name(row)

        return {
            "id": row.id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_by_user": self._map_user(users_by_id.get(row.uploaded_by)) if users_by_id else None,
            "uploaded_at": row.uploaded_at,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "type": row.type,
            "document_id": row.document_id,
            "document_type": row.document_type,
            "document_name": document_name,
            "from_whom_id": row.from_whom_id,
            "from_whom_user": self._map_user(users_by_id.get(row.from_whom_id)) if users_by_id and row.from_whom_id else None,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": self._resolve_object_name(row) if row.object_id else None,
            "customer_id": row.customer_id,
            "customer_name": counterparty_names.get(row.customer_id) if row.customer_id else None,
            "contractor_id": row.contractor_id,
            "contractor_name": counterparty_names.get(row.contractor_id) if row.contractor_id else None,
            "linked_file_id": row.linked_file_id,
        }

    def _build_document_names(self, rows) -> dict:
        contract_ids = {r.document_id for r in rows if r.document_type == "contract" and r.document_id}
        act_ids = {r.document_id for r in rows if r.document_type == "act" and r.document_id}
        letter_ids = {r.document_id for r in rows if r.document_type == "letter" and r.document_id}

        result = {}
        if contract_ids and self.contract_repo:
            contracts = self.contract_repo.get_contracts_by_ids([int(i) for i in contract_ids])
            doc_types = {dt.id: dt.name for dt in self.contract_repo.get_document_types()}
            for c in contracts:
                doc_type_name = doc_types.get(c.document_type_id)
                full_name = " ".join(part for part in [doc_type_name, c.name, "№", c.num] if part).strip()
                result[("contract", str(c.id))] = full_name
        if act_ids and self.act_repo:
            acts = self.act_repo.get_acts_by_ids([int(i) for i in act_ids])
            act_types = {at.id: at.name for at in self.act_repo.get_act_types()}
            for a in acts:
                type_name = act_types.get(a.act_type_id, "")
                result[("act", str(a.id))] = f"{type_name} №{a.num}"
        if letter_ids and self.letter_repo:
            letters = self.letter_repo.get_letters_by_ids([int(i) for i in letter_ids])
            for l in letters:
                full_name = " ".join(part for part in [l.name or "", "№", l.num or ""] if part).strip()
                result[("letter", str(l.id))] = full_name
        return result

    def _resolve_document_name(self, row) -> str | None:
        try:
            entity_id = int(row.document_id)
        except (TypeError, ValueError):
            return None
        if row.document_type == "contract" and self.contract_repo:
            contract = self.contract_repo.get_contract_by_id(entity_id)
            if not contract:
                return None
            doc_type = self.contract_repo.get_document_type_by_id(contract.document_type_id)
            doc_type_name = doc_type.name if doc_type else None
            return " ".join(part for part in [doc_type_name, contract.name, "№", contract.num] if part).strip()
        if row.document_type == "act" and self.act_repo:
            act = self.act_repo.get_by_id(entity_id)
            if not act:
                return None
            act_type = self.act_repo.get_act_type(act.act_type_id)
            type_name = act_type.name if act_type else ""
            return f"{type_name} №{act.num}"
        if row.document_type == "letter" and self.letter_repo:
            letter = self.letter_repo.get_letter_by_id(entity_id)
            if not letter:
                return None
            return " ".join(part for part in [letter.name or "", "№", letter.num or ""] if part).strip()
        return None

    def _resolve_object_name(self, row) -> str | None:
        if not self.reference_repo or not row.object_id:
            return None
        if row.object_type == "object_levels_id":
            return self.reference_repo.resolve_object_name(row.object_id)
        objs = self.reference_repo.get_objects_by_ids([row.object_id])
        if objs:
            return objs[0].short_name or objs[0].full_name
        return None

    def _check_parties(self, data: dict) -> dict:
        """Empty strings mean "not set"; given counterparties must exist."""
        data = dict(data)
        for key in ("customer_id", "contractor_id"):
            if key in data and data[key] == "":
                data[key] = None
        ids = [data[k] for k in ("customer_id", "contractor_id") if data.get(k)]
        if ids and self.reference_repo:
            found = self.reference_repo.get_counterparty_names(ids)
            missing = [i for i in dict.fromkeys(ids) if i not in found]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Контрагенты не найдены: {', '.join(missing)}"
                )
        return data

    def upload_file(self, file: UploadFile, user_id: str, payload: DocumentsListCreate | None = None) -> dict:
        Path(DOCUMENTS_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{DOCUMENTS_FILES_DIR}/{storage_name}"

        extra = self._check_parties(payload.model_dump(exclude_unset=True)) if payload is not None else None

        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        data = {
            "original_name": file.filename or storage_name,
            "storage_name": storage_name,
            "extension": ext.lstrip("."),
            "file_path": file_path,
            "uploaded_by": user_id,
        }
        if extra is not None:
            data.update(extra)
        else:
            data["document_type"] = Path(file.filename or "").suffix.lstrip(".") or None

        record = self.repo.create(data)
        return self._serialize_row(record)

    def update(self, document_id: int, payload: DocumentsListUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        updates = self._check_parties(payload.model_dump(exclude_unset=True))
        if updates:
            for key, value in updates.items():
                setattr(row, key, value)
        self.repo.touch(row, user_id)
        return self._serialize_row(row)

    def delete(self, document_id: int) -> None:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.repo.delete(row)

    # --- Attach ---

    def _copy_to_entity_dir(self, row, target_dir: str) -> str:
        ext = Path(row.file_path).suffix
        storage_name = f"{uuid.uuid4().hex}{ext}"
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)
        shutil.copy2(row.file_path, file_path)
        return file_path

    def attach_to_contract(
        self,
        document_id: int,
        contract_id: int,
        user_id: str,
        contract_folder_id: str | None = None,
        file_type: str | None = None,
    ) -> dict:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not self.contract_repo or not self.contract_repo.get_contract_by_id(contract_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        target_dir = os.path.join(BASE_CONTRACT_FILES_DIR, str(contract_id))
        file_path = self._copy_to_entity_dir(row, target_dir)
        extension = Path(row.file_path).suffix.lstrip(".")
        effective_type = file_type if extension in {"pdf", "doc", "docx", "xls", "xlsx"} else None

        created = self.contract_repo.create_file({
            "contract_id": contract_id,
            "contract_folder_id": contract_folder_id,
            "original_name": row.original_name,
            "storage_name": os.path.basename(file_path),
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": user_id,
            "type": effective_type,
        })
        self.contract_repo.create_log(str(contract_id), "contract", f"привязал файл {row.original_name}", user_id)

        self._mark_attached(row, str(contract_id), "contract", created.id, user_id)
        return self._serialize_file(created)

    def attach_to_act(
        self,
        document_id: int,
        act_id: int,
        user_id: str,
        act_folder_id: str | None = None,
        file_type: str | None = None,
    ) -> dict:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not self.act_repo or not self.act_repo.get_by_id(act_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        file_path = self._copy_to_entity_dir(row, ACTS_FILES_DIR)
        ext = Path(row.file_path).suffix
        created = self.act_repo.create_file({
            "id": str(uuid.uuid4()),
            "act_id": act_id,
            "act_folder_id": act_folder_id,
            "original_name": row.original_name,
            "storage_name": os.path.basename(file_path),
            "extension": ext.lstrip("."),
            "file_path": file_path,
            "uploaded_by": user_id,
            "type": file_type or "original",
        })

        self._mark_attached(row, str(act_id), "act", created.id, user_id)
        return self._serialize_file(created)

    def attach_to_letter(
        self,
        document_id: int,
        letter_id: int,
        user_id: str,
        letter_folder_id: str | None = None,
        file_type: str | None = None,
    ) -> dict:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not self.letter_repo or not self.letter_repo.get_letter_by_id(letter_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        target_dir = os.path.join(BASE_LETTER_FILES_DIR, str(letter_id))
        file_path = self._copy_to_entity_dir(row, target_dir)
        extension = Path(row.file_path).suffix.lstrip(".")
        effective_type = file_type if extension in {"pdf", "doc", "docx", "xls", "xlsx"} else None

        created = self.letter_repo.create_file({
            "letter_id": letter_id,
            "letter_folder_id": letter_folder_id,
            "original_name": row.original_name,
            "storage_name": os.path.basename(file_path),
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": user_id,
            "type": effective_type,
        })
        self.letter_repo.create_log(str(letter_id), f"привязал файл {row.original_name}", user_id)

        self._mark_attached(row, str(letter_id), "letter", created.id, user_id)
        return self._serialize_file(created)

    def _mark_attached(self, row, document_id: str, document_type: str, linked_file_id: str, user_id: str) -> None:
        row.document_id = document_id
        row.document_type = document_type
        row.linked_file_id = linked_file_id
        self.repo.touch(row, user_id)

    def unlink_by_linked_file_id(self, linked_file_id: str) -> None:
        row = self.repo.get_by_linked_file_id(linked_file_id)
        if not row:
            return
        row.document_id = None
        row.document_type = None
        row.linked_file_id = None
        self.repo.save(row)

    def rename_by_linked_file_id(self, linked_file_id: str, new_name: str) -> None:
        row = self.repo.get_by_linked_file_id(linked_file_id)
        if not row:
            return
        row.original_name = new_name
        self.repo.save(row)

    def _serialize_file(self, row) -> dict:
        return {
            "id": row.id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
            "type": getattr(row, "type", None),
        }

    # --- Files ---

    def get_download(self, document_id: int) -> tuple[str, str]:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    def get_preview(self, document_id: int) -> str:
        row = self.repo.get_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        ext = Path(row.file_path).suffix.lower()
        if ext == ".pdf":
            return row.file_path

        if ext not in PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")

        cached = Path(row.file_path).parent / f"{Path(row.file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

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

    def get_file_path(self, filename: str) -> str:
        return f"{DOCUMENTS_FILES_DIR}/{filename}"

    # --- Serialization ---

    def _get_users_map(self, user_ids: list[str]) -> dict:
        if not self.auth_user_repo or not user_ids:
            return {}
        users = self.auth_user_repo.get_by_ids(user_ids)
        return {u.id: u for u in users}

    @staticmethod
    def _map_user(user) -> dict | None:
        if not user:
            return None
        surname = getattr(user, "surname", "") or ""
        name = getattr(user, "name", "") or ""
        patronymic = getattr(user, "patronymic", "") or ""
        short_fio = f"{surname} {name[0]}.{patronymic[0]}." if surname and name and patronymic else (surname or name or "")
        return {"id": user.id, "surname": surname, "name": name, "patronymic": patronymic, "short_fio": short_fio}
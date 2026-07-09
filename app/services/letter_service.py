import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import date
from pathlib import Path

import requests

from fastapi import HTTPException, status

from app.models.letter import (
    Letter,
    LetterCreate,
    LetterFileUpdate,
    LetterFolderCreate,
    LetterFolderUpdate,
    LetterObjectCreate,
    LetterStatusCreate,
    LetterStatusUpdate,
    LetterUpdate,
    LetterUserRoleCreate,
    LetterUserRoleUpdate,
    msk_now,
)
from app.models.reference_object import CounterpartyRef
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.letter_repository import LetterRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

BASE_LETTER_FILES_DIR = "/home/webserver/models/documents/letters"
MAIL_TEMPLATE_PATH = "/home/webserver/models/supply/tamplates/mails/mail.docx"
CALLBACK_HOST = "https://supply.st29.ru/apisup"
JWT_SECRET = "lLst3oyFq7Ml8QPQK5bUkdUU7nrycRuH"

_editor_keys: dict[int, str] = {}


class LetterService:
    def __init__(
        self,
        repo: LetterRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        users = self.auth_user_repo.get_by_ids([uid for uid in user_ids if uid])
        return {user.id: user for user in users}

    def _get_counterparty_names(self, counterparty_ids: list[str]) -> dict[str, str]:
        if not self.reference_repo:
            return {}
        return self.reference_repo.get_counterparty_names(counterparty_ids)

    @staticmethod
    def _serialize_log(row, users_by_id: dict | None = None):
        return {
            "id": row.id,
            "log_object_id": row.log_object_id,
            "log_object_type": row.log_object_type,
            "message": row.message,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": LetterService._map_user((users_by_id or {}).get(row.created_by)),
        }

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


    def _serialize_folder(self, row) -> dict:
        return {
            "id": row.id,
            "letter_id": row.letter_id,
            "name": row.name,
            "parent_id": row.parent_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    @staticmethod
    def _serialize_file(row) -> dict:
        return {
            "id": row.id,
            "letter_id": row.letter_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
            "letter_folder_id": row.letter_folder_id,
            "type": row.type,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    @staticmethod
    def _serialize_status(row) -> dict:
        return {
            "id": row.id,
            "letter_id": row.letter_id,
            "type_movement": row.type_movement,
            "date": row.date,
            "type": row.type,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def _serialize_user_role(self, row, users_by_id: dict):
        return {
            "id": row.id,
            "letter_id": row.letter_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)) if users_by_id else None,
            "role": row.role,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
        }

    # --- Letter CRUD ---

    def get_logs(self, letter_id: int | None = None, created_by: str | None = None) -> list[dict]:
        rows = self.repo.get_logs(letter_id, created_by)
        user_ids = {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_log(r, users_by_id) for r in rows]

    def get_letters(self, letter_type: str | None = None) -> list[dict]:
        rows = self.repo.get_letters(letter_type)
        return [self._build_letter_response(r) for r in rows]

    def get_my_letters(self, user_id: str, letter_type: str | None = None) -> list[dict]:
        ids = self.repo.get_letter_ids_by_user(user_id)
        if not ids:
            return []
        all_letters = self.repo.get_letters(letter_type)
        rows = [r for r in all_letters if r.id in ids]
        return [self._build_letter_response(r) for r in rows]

    def get_letter(self, letter_id: int) -> dict:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        return self._build_letter_response(row)

    def _build_letter_response(self, row: Letter) -> dict:
        user_ids = {row.created_by}
        counterparty_ids = {row.from_to, row.where_to}

        user_roles = self.repo.get_user_roles(letter_id=row.id)
        for ur in user_roles:
            user_ids.add(ur.user_id)
            user_ids.add(ur.created_by)

        users_by_id = self._get_users_map(list(user_ids))
        counterparty_names = self._get_counterparty_names(list(counterparty_ids))

        result = {
            "id": row.id,
            "internal_num": row.internal_num,
            "num": row.num,
            "name": row.name,
            "from_to": row.from_to,
            "from_to_name": counterparty_names.get(row.from_to),
            "where_to": row.where_to,
            "where_to_name": counterparty_names.get(row.where_to),
            "type": row.type,
            "comment": row.comment,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "objects": [self._serialize_object(o) for o in self.repo.get_objects(letter_id=row.id)],
            "statuses": [self._serialize_status(s) for s in self.repo.get_statuses(letter_id=row.id)],
            "user_roles": [self._serialize_user_role(ur, users_by_id) for ur in user_roles],
        }

        return result

    def create_letter(self, payload: LetterCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by

        from_to_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("from_to", ""))
        where_to_internal = self.reference_repo and self.reference_repo.is_counterparty_internal(data.get("where_to", ""))

        if data["type"] == "outgoing" and from_to_internal:
            data["internal_num"] = str(self.repo.count_letters(data["from_to"], "from_to", "outgoing") + 1)
        elif data["type"] == "incoming" and where_to_internal:
            data["internal_num"] = str(self.repo.count_letters(data["where_to"], "where_to", "incoming") + 1)
        else:
            data["internal_num"] = str(self.repo.count_letters() + 1)

        created = self.repo.create_letter(data)
        full_name = " ".join(part for part in [data.get("name", ""), "№", data.get("num", "")] if part).strip()
        self.repo.create_log(created.id, f"создал письмо {full_name}", created_by)
        return self._build_letter_response(created)

    def update_letter(self, letter_id: int, payload: LetterUpdate, user_id: str) -> dict:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        old = {
            "num": row.num,
            "internal_num": row.internal_num,
            "name": row.name,
            "from_to": row.from_to,
            "where_to": row.where_to,
            "type": row.type,
            "comment": row.comment,
        }

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return self._build_letter_response(row)

        for key, value in data.items():
            setattr(row, key, value)
        self.repo.save_letter(row)

        logs = []
        if "from_to" in data and data["from_to"] != old["from_to"]:
            names = self._get_counterparty_names([old["from_to"], data["from_to"]])
            logs.append(f"изменил отправителя с {names.get(old['from_to'], old['from_to'])} на {names.get(data['from_to'], data['from_to'])}")
        if "where_to" in data and data["where_to"] != old["where_to"]:
            names = self._get_counterparty_names([old["where_to"], data["where_to"]])
            logs.append(f"изменил получателя с {names.get(old['where_to'], old['where_to'])} на {names.get(data['where_to'], data['where_to'])}")
        if "num" in data and data["num"] != old["num"]:
            if data["num"] is None and old["num"] is not None:
                logs.append(f"удалил номер письма {old['num']}")
            else:
                logs.append(f"изменил номер письма с {old['num'] or '—'} на {data['num']}")
        if "internal_num" in data and data["internal_num"] != old["internal_num"]:
            logs.append(f"изменил внутренний номер письма с {old['internal_num'] or '—'} на {data['internal_num']}")
        if "name" in data and data["name"] != old["name"]:
            if data["name"] is None and old["name"] is not None:
                logs.append(f"удалил наименование письма {old['name']}")
            else:
                logs.append(f"изменил наименование письма с {old['name'] or '—'} на {data['name']}")
        if "type" in data and data["type"] != old["type"]:
            logs.append(f"изменил тип письма с {old['type']} на {data['type']}")
        if "comment" in data and data["comment"] != old["comment"]:
            if old["comment"] is None:
                logs.append(f"добавил примечание: {data['comment']}")
            else:
                logs.append(f"изменил примечание с {old['comment']} на {data['comment']}")

        for msg in logs:
            self.repo.create_log(letter_id, msg, user_id)

        return self._build_letter_response(row)

    def delete_letter(self, letter_id: int, user_id: str) -> None:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        full_name = " ".join(part for part in [row.name or "", "№", row.num or ""] if part).strip()
        self.repo.delete_logs_by_letter(letter_id)
        self.repo.delete_letter(row)
        self.repo.create_log(letter_id, f"удалил письмо {full_name}", user_id)

    # --- Editor ---

    def _fill_docx_template(self, template_path: str, output_path: str, replacements: dict[str, str]):
        shutil.copy(template_path, output_path)
        temp_dir = output_path + ".tmp"
        os.makedirs(temp_dir, exist_ok=True)
        with zipfile.ZipFile(output_path, "r") as zin:
            zin.extractall(temp_dir)
        document_xml_path = os.path.join(temp_dir, "word", "document.xml")
        if not os.path.exists(document_xml_path):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid docx template")
        with open(document_xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()

        def _merge_para(m):
            para = m.group(0)
            texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
            merged = "".join(texts)
            changed = False
            for key, val in replacements.items():
                new_merged = merged.replace(f"${key}", val)
                if new_merged != merged:
                    changed = True
                    merged = new_merged
            if not changed:
                return para
            first = [True]
            def _replace_t(m2):
                if first[0]:
                    first[0] = False
                    return f"<w:t>{merged}</w:t>"
                return "<w:t></w:t>"
            return re.sub(r'<w:t[^>]*>[^<]*</w:t>', _replace_t, para)

        xml_content = re.sub(r'<w:p[ >].*?</w:p>', _merge_para, xml_content, flags=re.DOTALL)

        with open(document_xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, _dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zout.write(file_path, arcname)
        shutil.rmtree(temp_dir)

    def _get_person_fio(self, person) -> str:
        if not person:
            return ""
        parts = [p for p in [person.last_naem, person.name, person.middle_name] if p]
        return " ".join(parts)

    @staticmethod
    def _encode_jwt(payload: dict, secret: str) -> str:
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        signature = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        return f"{header}.{body}.{signature}"

    def _resolve_counterparty_data(self, counterparty_id: str) -> dict:
        data = {
            "full_name": "",
            "type": "",
            "inn": "",
            "kpp": "",
            "ogrn": "",
            "legal_address": "",
            "phone": "",
            "email": "",
            "fio_director": "",
            "position": "",
            "bank_name": "",
            "bik": "",
            "ks": "",
            "rs": "",
        }
        cp = self.reference_repo.db.query(CounterpartyRef).filter(CounterpartyRef.id == counterparty_id).first()
        if not cp:
            return data

        data["full_name"] = cp.full_name or ""
        cp_type = self.reference_repo.get_counterparty_type(counterparty_id)
        data["type"] = cp_type or ""

        person_id = None
        if cp_type == "LLC":
            details = self.reference_repo.get_details_llc(counterparty_id)
            if details:
                data["inn"] = details.inn or ""
                data["kpp"] = details.kpp or ""
                data["ogrn"] = details.ogrn or ""
                data["legal_address"] = details.legal_address or ""
                person_id = details.director_person_id
        elif cp_type == "IP":
            details = self.reference_repo.get_details_ip(counterparty_id)
            if details:
                data["inn"] = details.inn or ""
                data["ogrn"] = details.ogrnip or ""
                person_id = details.person_id

        if person_id:
            person = self.reference_repo.get_person(person_id)
            if person:
                data["phone"] = person.phone_personal or ""
                data["email"] = person.email_personal or ""
                data["fio_director"] = self._get_person_fio(person)
            emp = self.reference_repo.get_employee(person_id, counterparty_id)
            if emp:
                data["position"] = emp.position or ""

        banks = self.reference_repo.get_bank_accounts(counterparty_id)
        if banks:
            b = banks[0]
            data["bank_name"] = b.bank_name or ""
            data["bik"] = b.bik or ""
            data["ks"] = b.correspondent_account or ""
            data["rs"] = b.account_number or ""

        return data

    def get_template_data(self, letter_id: int) -> dict:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        if not self.reference_repo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reference service not available")

        mail_num = row.num or ""
        mail_date = row.created_at or date.today()
        mail_date_str = mail_date.strftime("%d.%m.%Y") if hasattr(mail_date, "strftime") else str(mail_date)

        from_data = self._resolve_counterparty_data(row.from_to) if row.from_to else {}
        where_data = self._resolve_counterparty_data(row.where_to) if row.where_to else {}

        return {
            "mailNum": mail_num,
            "mailDate": mail_date_str,
            "from": from_data,
            "where": where_data,
        }

    def get_editor_config(self, letter_id: int, file_id: str | None = None) -> dict:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        callback_url = f"{CALLBACK_HOST}/supply/letters/{letter_id}/editor-callback"
        mail_num = row.num or ""
        title = f"Исходящее письмо № {mail_num}"

        if file_id:
            file = self.repo.get_file_by_id(file_id)
            if not file:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
            key = f"letter-{letter_id}-ver-{file_id}"
            _editor_keys[letter_id] = key
            return {
                "fileUrl": f"{CALLBACK_HOST}/supply/letter-editor-files/{letter_id}/{file.storage_name}",
                "callbackUrl": callback_url,
                "key": key,
                "title": file.original_name or title,
            }

        if not self.reference_repo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reference service not available")

        from_data = self._resolve_counterparty_data(row.from_to) if row.from_to else {}
        where_data = self._resolve_counterparty_data(row.where_to) if row.where_to else {}

        mail_date = row.created_at or date.today()
        mail_date_str = mail_date.strftime("%d.%m.%Y") if hasattr(mail_date, "strftime") else str(mail_date)

        folders = self.repo.get_folders(letter_id)
        version_folder = None
        for fld in folders:
            if fld.name == "Версия письма" and fld.parent_id is None:
                version_folder = fld
                break

        last_version = None
        if version_folder:
            files = self.repo.get_files(letter_id, version_folder.id)
            if files:
                last_version = files[0]

        callback_url = f"{CALLBACK_HOST}/supply/letters/{letter_id}/editor-callback"
        title = f"Исходящее письмо № {mail_num}"

        if last_version:
            file_url = f"{CALLBACK_HOST}/supply/letter-editor-files/{letter_id}/{last_version.storage_name}"
            key = f"letter-{letter_id}-{last_version.id}"
            _editor_keys[letter_id] = key
            return {
                "fileUrl": file_url,
                "callbackUrl": callback_url,
                "key": key,
                "title": title,
            }

        key = uuid.uuid4().hex
        row.editor_key = key
        self.repo.save_letter(row)
        output_filename = f"mail_filled_{key}.docx"
        output_dir = os.path.join(BASE_LETTER_FILES_DIR, str(letter_id))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        if not os.path.exists(MAIL_TEMPLATE_PATH):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Mail template not found")

        replacements = {
            "fullName": from_data.get("full_name", ""),
            "inn": from_data.get("inn", ""),
            "kpp": from_data.get("kpp", ""),
            "ogrn": from_data.get("ogrn", ""),
            "fullAdress": from_data.get("legal_address", ""),
            "rs": from_data.get("rs", ""),
            "bankName": from_data.get("bank_name", ""),
            "ks": from_data.get("ks", ""),
            "bik": from_data.get("bik", ""),
            "phone": from_data.get("phone", ""),
            "email": from_data.get("email", ""),
            "mailNum": mail_num,
            "mailDate": mail_date_str,
            "post": from_data.get("position", ""),
            "fioDirector": from_data.get("fio_director", ""),
            "whereFullName": where_data.get("full_name", ""),
            "whereFullAddress": where_data.get("legal_address", ""),
            "wherePhone": where_data.get("phone", ""),
            "whereEmail": where_data.get("email", ""),
        }
        self._fill_docx_template(MAIL_TEMPLATE_PATH, output_path, replacements)

        file_url = f"{CALLBACK_HOST}/supply/letter-editor-files/{letter_id}/{output_filename}"
        return {
            "fileUrl": file_url,
            "callbackUrl": callback_url,
            "key": key,
            "title": title,
        }

    def force_save(self, letter_id: int) -> dict:
        key = _editor_keys.get(letter_id)
        if not key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active editor session")

        import requests
        resp = requests.post(
            "https://doc.st29.ru/coauthoring/CommandService.ashx",
            json={"c": "forcesave", "key": key},
            timeout=30,
        )
        result = resp.json()
        if result.get("error", 0) != 0:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OnlyOffice error: {result}")
        return {"ok": True}

    def handle_editor_callback(self, letter_id: int, status: int, url: str, user_id: str, token: str = "") -> dict:
        row = self.repo.get_letter_by_id(letter_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if status != 2 or not url:
            return {"error": 0, "status": status, "saved": False}

        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = requests.get(url, headers=headers, timeout=120)
            if resp.status_code != 200:
                return {"error": 0, "status": status, "saved": False, "reason": f"download failed {resp.status_code}"}
        except Exception:
            return {"error": 0, "status": status, "saved": False, "reason": "download exception"}

        mail_num = row.num or ""
        original_name = f"Письмо исходящее № {mail_num}.docx"
        content_disposition = resp.headers.get("content-disposition", "")
        if "filename=" in content_disposition:
            original_name = content_disposition.split("filename=")[-1].strip('" ')

        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_LETTER_FILES_DIR, str(letter_id))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)
        with open(file_path, "wb") as f:
            f.write(resp.content)

        folders = self.repo.get_folders(letter_id)
        version_folder = None
        for fld in folders:
            if fld.name == "Версия письма" and fld.parent_id is None:
                version_folder = fld
                break
        if not version_folder:
            version_folder = self.repo.create_folder({
                "letter_id": letter_id,
                "name": "Версия письма",
                "parent_id": None,
                "created_by": row.created_by or user_id,
                "created_at": msk_now(),
            })

        created = self.repo.create_file({
            "letter_id": letter_id,
            "letter_folder_id": version_folder.id,
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": row.created_by or user_id,
            "type": "version",
        })
        self.repo.create_log(letter_id, f"загрузил файл {original_name} (версия письма)", row.created_by or user_id)
        return self._serialize_file(created)

    # --- LetterFolder ---

    def get_folders(self, letter_id: int | None = None) -> list[dict]:
        rows = self.repo.get_folders(letter_id)
        return [self._serialize_folder(r) for r in rows]

    def get_folder(self, folder_id: str) -> dict:
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        return self._serialize_folder(row)

    def create_folder(self, payload: LetterFolderCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_folder(data)
        self.repo.create_log(created.letter_id, f"добавил папку {created.name}", created_by)
        return self._serialize_folder(created)

    def update_folder(self, folder_id: str, payload: LetterFolderUpdate, user_id: str) -> dict:
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        old_name = row.name
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_folder(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.save_folder(row)
        if "name" in updates and updates["name"] != old_name:
            self.repo.create_log(row.letter_id, f"изменил папку {old_name} на {updates['name']}", user_id)
        return self._serialize_folder(row)

    def delete_folder(self, folder_id: str, user_id: str) -> None:
        row = self.repo.get_folder_by_id(folder_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        letter_id = row.letter_id
        name = row.name
        self.repo.delete_folder(row)
        self.repo.create_log(letter_id, f"удалил папку {name}", user_id)

    def get_folder_tree(self, letter_id: int) -> list[dict]:
        folders = self.repo.get_folders(letter_id)
        files = self.repo.get_files(letter_id=letter_id)

        folders_map = {}
        for f in folders:
            folders_map[f.id] = {**self._serialize_folder(f), "children": [], "files": []}

        root_files = []
        for f in files:
            file_data = self._serialize_file(f)
            parent_id = f.letter_folder_id
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

    # --- LetterFile ---

    def get_files(self, letter_id: int | None = None, folder_id: str | None = None) -> list[dict]:
        rows = self.repo.get_files(letter_id, folder_id)
        return [self._serialize_file(r) for r in rows]

    def get_my_files(self, user_id: str) -> list[dict]:
        letter_ids = self.repo.get_letter_ids_by_user(user_id)
        if not letter_ids:
            return []
        letters = self.repo.get_letters_by_ids(letter_ids)
        files = self.repo.get_files_by_letter_ids(letter_ids)
        files_by_letter: dict[int, list[dict]] = {}
        for f in files:
            files_by_letter.setdefault(f.letter_id, []).append(self._serialize_file(f))
        result = []
        for l in letters:
            entry = {
                "id": l.id,
                "internal_num": l.internal_num,
                "num": l.num,
                "name": l.name,
                "type": l.type,
                "files": files_by_letter.get(l.id, []),
            }
            result.append(entry)
        return result

    def get_files_history(self, letter_id: int) -> list[dict]:
        rows = self.repo.get_files_history(letter_id)
        return [self._serialize_file(r) for r in rows]

    def get_file(self, file_id: str) -> dict:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return self._serialize_file(row)

    def upload(
        self,
        letter_id: int,
        original_name: str,
        file_bytes: bytes,
        uploaded_by: str,
        letter_folder_id: str | None = None,
        file_type: str | None = None,
    ):
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_LETTER_FILES_DIR, str(letter_id))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        effective_type = file_type if extension in {"pdf", "doc", "docx", "xls", "xlsx"} else None
        created = self.repo.create_file({
            "letter_id": letter_id,
            "letter_folder_id": letter_folder_id,
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or None,
            "file_path": file_path,
            "uploaded_by": uploaded_by,
            "type": effective_type,
        })
        self.repo.create_log(letter_id, f"загрузил файл {original_name}", uploaded_by)
        return self._serialize_file(created)

    def update_file(self, file_id: str, payload: LetterFileUpdate, user_id: str) -> dict:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        old_name = row.original_name
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_file(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.save_file(row)
        if "original_name" in updates and updates["original_name"] != old_name:
            self.repo.create_log(row.letter_id, f"переименовал файл {old_name} в {updates['original_name']}", user_id)
        return self._serialize_file(row)

    def delete_file(self, file_id: str, user_id: str) -> None:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        letter_id = row.letter_id
        original_name = row.original_name
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)
        self.repo.create_log(letter_id, f"удалил файл {original_name}", user_id)

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

    # --- LetterObject ---

    def get_objects(self, letter_id: int | None = None) -> list[dict]:
        rows = self.repo.get_objects(letter_id)
        return [self._serialize_object(r) for r in rows]

    def _resolve_object_name(self, row) -> str | None:
        if not self.reference_repo:
            return None
        if row.object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([row.object_id])
            return objs[0].short_name if objs else None
        elif row.object_type == "object_levels_id":
            return self.reference_repo.resolve_object_name(row.object_id)
        return None

    def _serialize_object(self, row) -> dict:
        return {
            "id": row.id,
            "letter_id": row.letter_id,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": self._resolve_object_name(row),
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def create_object(self, payload: LetterObjectCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_object(data)
        object_name = self._resolve_object_name(created)
        name_part = f" ({object_name})" if object_name else ""
        self.repo.create_log(created.letter_id, f"добавил объект{name_part}", created_by)
        return self._serialize_object(created)

    def delete_object(self, obj_id: int, user_id: str) -> None:
        row = self.repo.get_object_by_id(obj_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
        letter_id = row.letter_id
        object_name = self._resolve_object_name(row)
        name_part = f" ({object_name})" if object_name else ""
        self.repo.delete_object(row)
        self.repo.create_log(letter_id, f"удалил объект{name_part}", user_id)

    # --- LetterStatus ---

    def get_statuses(self, letter_id: int | None = None) -> list[dict]:
        rows = self.repo.get_statuses(letter_id)
        return [self._serialize_status(r) for r in rows]

    def create_status(self, payload: LetterStatusCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_status(data)
        label = f"{created.type_movement} {created.type}"
        self.repo.create_log(created.letter_id, f"присвоил статус {label}", created_by)
        return self._serialize_status(created)

    def update_status(self, status_id: int, payload: LetterStatusUpdate, user_id: str) -> dict:
        row = self.repo.get_status_by_id(status_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_status(row)
        old_label = f"{row.type_movement} {row.type}"
        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save_status(row)
        new_label = f"{row.type_movement} {row.type}"
        if new_label != old_label:
            self.repo.create_log(row.letter_id, f"изменил статус с {old_label} на {new_label}", user_id)
        return self._serialize_status(row)

    def delete_status(self, status_id: int, user_id: str) -> None:
        row = self.repo.get_status_by_id(status_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status not found")
        letter_id = row.letter_id
        label = f"{row.type_movement} {row.type}"
        self.repo.delete_status(row)
        self.repo.create_log(letter_id, f"удалил статус {label}", user_id)

    # --- LetterUserRole ---

    def get_user_roles(self, letter_id: int | None = None) -> list[dict]:
        rows = self.repo.get_user_roles(letter_id)
        user_ids = {row.user_id for row in rows} | {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_user_role(r, users_by_id) for r in rows]

    def get_user_role(self, role_id: str) -> dict:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return self._serialize_user_role(row, users_by_id)

    def create_user_role(self, payload: LetterUserRoleCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_user_role(data)
        users_by_id = self._get_users_map([created.user_id, created.created_by])
        user_info = self._map_user(users_by_id.get(created.user_id))
        user_name = user_info["short_fio"] if user_info else created.user_id
        self.repo.create_log(created.letter_id, f"добавил роль {created.role} для {user_name}", created_by)
        return self._serialize_user_role(created, users_by_id)

    def update_user_role(self, role_id: str, payload: LetterUserRoleUpdate, user_id: str) -> dict:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        old_role = row.role
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_user_role(row)
        if "role" in data and data["role"] != old_role:
            self.repo.create_log(updated.letter_id, f"изменил роль с {old_role} на {data['role']}", user_id)
        users_by_id = self._get_users_map([updated.user_id, updated.created_by])
        return self._serialize_user_role(updated, users_by_id)

    def delete_user_role(self, role_id: str, user_id: str) -> None:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        letter_id = row.letter_id
        role = row.role
        self.repo.delete_user_role(row)
        self.repo.create_log(letter_id, f"удалил роль {role}", user_id)

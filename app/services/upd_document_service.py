import hashlib
import json
import os
import re
import time
import uuid
from datetime import date as dt_date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status
import httpx

from app.models.request_file import FileAudit, FileDB
from app.models.upd_document import UpdDocumentItemCreate, UpdDocumentItemUpdate, UpdDocumentUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.upd_document_repository import UpdDocumentRepository

DEFAULT_UPD_STATUS_ID = "f5533f42-3972-11f1-b5d7-bc241127d0bd"
UPD_FILE_TYPE_ID = "4594a94b-140f-11f1-aa8c-bc241127d0bd"
BASE_UPD_FILES_DIR = os.getenv(
    "SUPPLY_UPD_FILES_DIR",
    "/home/webserver/models/supply/upd",
)
DECIMAL_17_8_MAX = Decimal("999999999.99999999")
DECIMAL_17_8_MIN = Decimal("-999999999.99999999")


class UpdDocumentService:
    def __init__(
        self,
        repo: UpdDocumentRepository,
        file_repo: RequestFileRepository | None = None,
        counterparty_repo: CounterpartyRepository | None = None,
        auth_user_repo: AuthUserRepository | None = None,
    ) -> None:
        self.repo = repo
        self.file_repo = file_repo
        self.counterparty_repo = counterparty_repo
        self.auth_user_repo = auth_user_repo

    def get_all(self, warehouse_id: str | None = None):
        rows = self.repo.get_documents(warehouse_id)
        warehouse_names = self.repo.get_warehouse_names([row.warehouse_id for row in rows if row.warehouse_id])
        return [self._serialize_document(row, warehouse_names=warehouse_names) for row in rows]

    def get_document(self, document_id: str):
        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")
        warehouse_names = self.repo.get_warehouse_names([row.warehouse_id] if row.warehouse_id else [])
        return self._serialize_document(row, warehouse_names=warehouse_names)

    def update_document(self, document_id: str, payload: UpdDocumentUpdate):
        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        self.repo.save_document(row)
        return self.get_document(document_id)

    def get_file_download_payload(self, document_id: str, user_id: str):
        if not self.file_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File repository is not configured",
            )

        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")
        if not row.file_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD file not found")

        file_row = self.file_repo.get_file_by_id(row.file_id)
        if not file_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD file not found")
        if not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        self.file_repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="download",
                user_id=user_id,
            )
        )

        return {
            "path": file_row.file_path,
            "filename": file_row.original_name,
            "media_type": file_row.mime_type,
        }

    def reparse_document_items(self, document_id: str):
        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")
        if not row.file_id or not self.file_repo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD file not found")

        file_row = self.file_repo.get_file_by_id(row.file_id)
        if not file_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD file not found")
        if not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        with open(file_row.file_path, "rb") as file_stream:
            file_bytes = file_stream.read()

        parsed_result = self.parse_file_only(file_row.original_name, file_bytes)
        normalized_header = parsed_result["header"]
        normalized_items = parsed_result["items"]

        row.num = normalized_header["num"]
        row.date = normalized_header["date"]
        self.repo.save_document(row)

        self.repo.delete_document_items_by_document_id(document_id)
        try:
            for item in normalized_items:
                self._validate_item_numeric_ranges(item)
                self.repo.create_document_item(document_id, self._to_db_item_payload(item))
        except Exception:
            self.repo.rollback()
            raise

        return {
            "status": "success",
            "upd_document_id": document_id,
            "num": row.num,
            "date": row.date,
            "items_count": len(normalized_items),
        }

    def create_document_with_file(
        self,
        user_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        warehouse_id: str | None = None,
        provider_id: str | None = None,
        payer_id: str | None = None,
    ):
        extension, file_type = self._validate_upload(original_name, file_bytes)

        document_id = str(uuid.uuid4())
        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        upd_dir = os.path.join(BASE_UPD_FILES_DIR, document_id)
        self._ensure_directory(upd_dir)

        file_path = os.path.join(upd_dir, storage_name)
        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        md5_hash = hashlib.md5(file_bytes).hexdigest()
        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=file_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=md5_hash,
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )

        try:
            created_file = self.file_repo.create_file(file_row)
            self.file_repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=created_file.id,
                    action="upload",
                    user_id=user_id,
                )
            )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        try:
            parsed_result = self.parse_file_only(
                original_name=original_name,
                file_bytes=file_bytes,
            )
            normalized_header = parsed_result["header"]
            normalized_items = parsed_result["items"]

            data = {
                "id": document_id,
                "warehouse_id": warehouse_id,
                "provider_id": provider_id,
                "payer_id": payer_id,
                "file_id": created_file.id,
                "created_by": user_id,
                "status": DEFAULT_UPD_STATUS_ID,
                "num": normalized_header["num"],
                "date": normalized_header["date"],
            }

            created = self.repo.create_document(data)
            for item in normalized_items:
                self._validate_item_numeric_ranges(item)
                self.repo.create_document_item(created.id, self._to_db_item_payload(item))
        except Exception:
            self.repo.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            if self.file_repo:
                stored_file = self.file_repo.get_file_by_id(file_id)
                if stored_file:
                    self.file_repo.mark_file_deleted(stored_file)
            raise

        return {
            "status": "success",
            "upd_document_id": created.id,
            "warehouse_id": created.warehouse_id,
            "warehouse_name": self.repo.get_warehouse_names([created.warehouse_id]).get(created.warehouse_id)
            if created.warehouse_id else None,
            "file_id": created_file.id,
            "num": created.num,
            "date": created.date,
            "items_count": len(normalized_items),
        }

    def create_document_item(self, document_id: str, payload: UpdDocumentItemCreate):
        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")
        data = payload.model_dump(exclude_unset=True)
        self._validate_item_numeric_ranges(data)
        item = self.repo.create_document_item(document_id, data)
        return self._item_to_dict(item)

    def update_document_item(self, document_id: str, item_id: str, payload: UpdDocumentItemUpdate):
        item = self.repo.get_document_item_by_id(document_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document item not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        self._validate_item_numeric_ranges(
            {
                "quantity": item.quantity,
                "price": item.price,
                "sum": item.sum,
            }
        )
        updated = self.repo.save_document_item(item)
        return self._item_to_dict(updated)

    def delete_document_item(self, document_id: str, item_id: str):
        item = self.repo.get_document_item_by_id(document_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document item not found")
        self.repo.delete_document_item(item)
        return None

    def delete_all_document_items(self, document_id: str):
        row = self.repo.get_document_by_id(document_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")
        self.repo.delete_document_items_by_document_id(document_id)
        return {"status": "success", "upd_document_id": document_id}

    def parse_file_only(
        self,
        original_name: str,
        file_bytes: bytes,
    ):
        self._validate_upload(original_name, file_bytes)
        parsed_payload = self._parse_upd_content(
            file_name=original_name,
            file_bytes=file_bytes,
        )
        return {
            "status": "success",
            "header": self._normalize_header_payload(parsed_payload.get("header")),
            "items": self._normalize_items_payload(parsed_payload.get("items")),
            "items_count": len(parsed_payload.get("items") or []),
        }

    def _parse_upd_content(self, file_name: str, file_bytes: bytes) -> dict:
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MISTRAL_API_KEY is not set",
            )

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        client = Mistral(
            api_key=mistral_api_key,
            client=httpx.Client(
                trust_env=False,
                timeout=httpx.Timeout(120.0, connect=30.0),
            ),
            timeout_ms=120000,
        )
        try:
            uploaded_file = client.files.upload(
                file={
                    "file_name": os.path.basename(file_name),
                    "content": file_bytes,
                },
                purpose="ocr",
            )
            signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                },
            )
            document_text = "\n\n".join(page.markdown for page in ocr_response.pages)
        except httpx.RemoteProtocolError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Mistral connection was interrupted while uploading or OCR processing the file. "
                    "Check outbound network access, reverse proxy settings, and HTTP_PROXY/HTTPS_PROXY variables."
                ),
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Mistral HTTP error: {exc}",
            ) from exc

        parse_prompt = (
            "Извлеки номер, дату и все товарные позиции из текста накладной/счёта-фактуры "
            "и верни ТОЛЬКО JSON без пояснений.\n\n"
            "Формат:\n"
            "{\n"
            '  "num": string|null,\n'
            '  "date": "YYYY-MM-DD"|null,\n'
            '  "items": [\n'
            "    {\n"
            '      "position_number": number|null,\n'
            '      "name": string|null,\n'
            '      "unit": string|null,\n'
            '      "quantity": number|null,\n'
            '      "vat_rate": number|null,\n'
            '      "price_per_unit": number|null\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Поля:\n"
            "- num — номер документа\n"
            "- date — дата документа в формате YYYY-MM-DD\n"
            "- position_number — номер позиции\n"
            "- name — наименование товара (работы, услуги)\n"
            "- unit — единица измерения, условное обозначение национальное (шт, кг, л, м и т.д.)\n"
            "- quantity — количество (объём)\n"
            "- vat_rate — ставка НДС в процентах (0, 10, 20 и т.д.)\n"
            "- total_with_tax — сумма по позиции с налогом из документа\n"
            "- price_per_unit — цена за товар (total_with_tax / quantity), округли до 2 знаков\n\n"
            "Правила:\n"
            "- Если поле не найдено — null.\n"
            "- Числа без пробелов и символов валют, только цифры и точка.\n"
            "- Если в документе указано 'без НДС', vat_rate = 0.\n"
            "- price_per_unit вычисли сам.\n\n"
            "Текст документа:\n"
            f"{document_text[:25000]}"
        )

        try:
            parse_response = self._chat_complete_with_retry(client, parse_prompt)
        except httpx.RemoteProtocolError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Mistral connection was interrupted while parsing the OCR text.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Mistral HTTP error: {exc}",
            ) from exc

        payload = self._extract_json_payload(
            self._message_content_to_text(parse_response.choices[0].message.content)
        )
        return {
            "header": {
                "num": payload.get("num"),
                "date": payload.get("date"),
            },
            "items": payload.get("items") if isinstance(payload.get("items"), list) else [],
        }

    @staticmethod
    def _chat_complete_with_retry(client, prompt: str, attempts: int = 3, base_delay: float = 2.0):
        last_exc = None
        for attempt in range(attempts):
            try:
                return client.chat.complete(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as exc:
                last_exc = exc
                message = str(exc).lower()
                status_code = getattr(exc, "status_code", None)
                is_rate_limited = status_code == 429 or "429" in message or "rate limit" in message
                if not is_rate_limited:
                    raise
                if attempt == attempts - 1:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Mistral rate limit exceeded. Try again a bit later.",
                    ) from exc
                time.sleep(base_delay * (attempt + 1))

        raise last_exc

    def _validate_upload(self, original_name: str, file_bytes: bytes):
        if not self.file_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File repository is not configured",
            )

        file_type = self.file_repo.get_file_type_by_id(UPD_FILE_TYPE_ID)
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active UPD file type not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = file_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = file_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        return extension, file_type

    def _serialize_document(self, row, warehouse_names: dict[str, str] | None = None):
        warehouse_names = warehouse_names or {}
        items = self.repo.get_document_items(row.id)
        users_by_id = self._get_users_map([row.created_by] if row.created_by else [])
        return {
            "id": row.id,
            "warehouse_id": row.warehouse_id,
            "warehouse_name": warehouse_names.get(row.warehouse_id) if row.warehouse_id else None,
            "provider_id": row.provider_id,
            "provider": self._build_counterparty_payload(row.provider_id),
            "provider_name": self._build_counterparty_name(row.provider_id),
            "payer_id": row.payer_id,
            "payer": self._build_counterparty_payload(row.payer_id),
            "payer_name": self._build_counterparty_name(row.payer_id),
            "file_id": row.file_id,
            "file": self._build_file_payload(row.file_id),
            "num": row.num,
            "date": row.date,
            "status": row.status,
            "status_name": self.repo.get_status_name(row.status),
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "items": [self._item_to_dict(item) for item in items],
        }

    def _build_counterparty_payload(self, counterparty_id: str | None) -> dict | None:
        if not self.counterparty_repo:
            return None
        return self.counterparty_repo.get_counterparty_brief(counterparty_id)

    def _build_counterparty_name(self, counterparty_id: str | None) -> str | None:
        payload = self._build_counterparty_payload(counterparty_id)
        return payload.get("short_name") if payload else None

    def _build_file_payload(self, file_id: str | None) -> dict | None:
        if not file_id or not self.file_repo:
            return None

        file_row = self.file_repo.get_file_by_id(file_id)
        if not file_row:
            return None

        return {
            "id": file_row.id,
            "original_name": file_row.original_name,
            "file_path": file_row.file_path,
            "mime_type": file_row.mime_type,
            "extension": file_row.extension,
            "file_size": file_row.file_size,
        }

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        users = self.auth_user_repo.get_by_ids([user_id for user_id in user_ids if user_id])
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

    @staticmethod
    def _item_to_dict(item):
        return {
            "id": item.id,
            "upd_documents_id": item.upd_documents_id,
            "position": item.position,
            "name": item.name,
            "unit_name": item.unit_name,
            "quantity": item.quantity,
            "vat_rate": item.vat_rate,
            "price": item.price,
            "sum": item.sum,
        }

    @staticmethod
    def _message_content_to_text(content) -> str:
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content or "")

    @staticmethod
    def _extract_json_payload(content: str) -> dict:
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mistral returned empty response",
            )

        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            payload = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot parse JSON from Mistral response",
                )
            try:
                payload = json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot parse JSON from Mistral response",
                ) from exc

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unexpected JSON format from Mistral",
            )
        return payload

    @staticmethod
    def _extract_json_array_payload(content: str) -> list[dict]:
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mistral returned empty response",
            )

        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            payload = json.loads(cleaned)
        except Exception:
            match = re.search(r"\[.*\]", cleaned, flags=re.S)
            if not match:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot parse JSON array from Mistral response",
                )
            try:
                payload = json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot parse JSON array from Mistral response",
                ) from exc

        if not isinstance(payload, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unexpected JSON format from Mistral",
            )
        return [item for item in payload if isinstance(item, dict)]

    def _normalize_header_payload(self, payload: dict | None) -> dict:
        payload = payload or {}
        return {
            "num": self._as_str(payload.get("num")),
            "date": self._as_date(payload.get("date")),
        }

    def _normalize_items_payload(self, payload: list[dict] | None) -> list[dict]:
        items = payload or []
        normalized = []
        for item in items:
            quantity = self._as_money(item.get("quantity"))
            price = self._as_money(item.get("price_per_unit"))
            vat_rate = self._as_vat_rate(item.get("vat_rate"))
            normalized.append(
                {
                    "position": self._as_int(item.get("position_number")),
                    "name": self._as_str(item.get("name")),
                    "unit_name": self._as_str(item.get("unit")),
                    "quantity": quantity,
                    "vat_rate": self._as_int(vat_rate),
                    "price": price,
                    "sum": self._as_money(item.get("total_with_tax")),
                }
            )
        return normalized

    @staticmethod
    def _to_db_item_payload(item: dict) -> dict:
        return {
            "position": item.get("position"),
            "name": item.get("name"),
            "unit_name": item.get("unit_name"),
            "quantity": item.get("quantity"),
            "vat_rate": item.get("vat_rate"),
            "price": item.get("price"),
            "sum": item.get("sum"),
        }

    @staticmethod
    def _as_str(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_date(value) -> dt_date | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        try:
            return dt_date.fromisoformat(text)
        except Exception:
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
            if m:
                day, month, year = m.groups()
                try:
                    return dt_date(int(year), int(month), int(day))
                except Exception:
                    return None
            m = re.search(r"(\d{4})/(\d{2})/(\d{2})", text)
            if m:
                year, month, day = m.groups()
                try:
                    return dt_date(int(year), int(month), int(day))
                except Exception:
                    return None
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
            if m:
                year, month, day = m.groups()
                try:
                    return dt_date(int(year), int(month), int(day))
                except Exception:
                    return None
        return None

    @staticmethod
    def _as_int(value) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        match = re.search(r"-?\d+", text)
        if not match:
            return None
        try:
            return int(match.group(0))
        except Exception:
            return None

    @staticmethod
    def _as_money(value) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            candidate = str(value)
        else:
            candidate = str(value).strip()
            candidate = candidate.replace(" ", "")
            candidate = candidate.replace(",", ".")
            candidate = re.sub(r"[^0-9.\-]", "", candidate)
        if candidate in ("", "-", ".", "-."):
            return None
        try:
            amount = Decimal(candidate).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            return float(amount)
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _as_vat_rate(value) -> float | None:
        if value in (None, ""):
            return None
        text = str(value).strip().lower()
        if "без" in text and "ндс" in text:
            return 0.0
        return UpdDocumentService._as_money(value)

    def _validate_item_numeric_ranges(self, item: dict) -> None:
        for field_name in ("quantity", "price", "sum"):
            value = item.get(field_name)
            if not self._fits_decimal_17_8(value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Field '{field_name}' value {value} exceeds database range for DECIMAL(17,8). "
                        "Maximum allowed absolute value is 999999999.99999999."
                    ),
                )

    @staticmethod
    def _fits_decimal_17_8(value) -> bool:
        if value in (None, ""):
            return True
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return False
        return DECIMAL_17_8_MIN <= amount <= DECIMAL_17_8_MAX

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Cannot create directory '{path}'. "
                    "Set SUPPLY_UPD_FILES_DIR to a writable path."
                ),
            ) from exc

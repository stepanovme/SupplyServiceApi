import hashlib
import json
import os
import re
import uuid
from datetime import date as dt_date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB
from app.models.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoiceUpdate,
)
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.request_file_repository import RequestFileRepository

DEFAULT_NEW_STATUS_ID = "1ff34436-1312-11f1-aa8c-bc241127d0bd"
INVOICE_FILE_TYPE_ID = "4594a94b-140f-11f1-aa8c-bc241127d0bd"
BASE_INVOICE_FILES_DIR = os.getenv(
    "SUPPLY_INVOICE_FILES_DIR",
    "/home/webserver/models/supply/invoices",
)


class InvoiceService:
    def __init__(
        self,
        repo: InvoiceRepository,
        file_repo: RequestFileRepository | None = None,
        counterparty_repo: CounterpartyRepository | None = None,
    ) -> None:
        self.repo = repo
        self.file_repo = file_repo
        self.counterparty_repo = counterparty_repo

    def parse_invoice_file_and_update(self, invoice_id: int, file_path: str, user_id: str):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        if not os.path.isabs(file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_path must be absolute",
            )
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found by file_path",
            )

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

        try:
            with open(file_path, "rb") as file_stream:
                file_bytes = file_stream.read()
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot read file: {file_path}",
            ) from exc

        client = Mistral(api_key=mistral_api_key)
        uploaded_file = client.files.upload(
            file={
                "file_name": os.path.basename(file_path),
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
        prompt = (
            "Extract invoice data from the document.\n"
            "Return ONLY valid JSON object with keys:\n"
            "{\n"
            '  "invoice_num": string|null,\n'
            '  "invoice_date": "YYYY-MM-DD"|null,\n'
            '  "vat_rate": int|null,\n'
            '  "vat_amount": number|null,\n'
            '  "total_amount": number|null,\n'
            '  "items": [\n'
            "    {\n"
            '      "name": string|null,\n'
            '      "unit_name": string|null,\n'
            '      "quantity": number|null,\n'
            '      "price": number|null,\n'
            '      "sum": number|null\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "If field is missing in document, set null.\n"
            "Document:\n"
            f"{document_text[:15000]}"
        )

        chat_response = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_content = chat_response.choices[0].message.content
        if isinstance(raw_content, list):
            raw_content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        parsed_payload = self._extract_json_payload(raw_content)

        normalized = self._normalize_invoice_payload(parsed_payload)
        invoice.num = normalized["invoice_num"]
        invoice.date = normalized["invoice_date"]
        invoice.total_amount = normalized["total_amount"] if normalized["total_amount"] is not None else 0
        invoice.vat_rate = normalized["vat_rate"] if normalized["vat_rate"] is not None else 0
        invoice.vat_amount = normalized["vat_amount"] if normalized["vat_amount"] is not None else 0
        self.repo.save_invoice(invoice)

        self.repo.delete_invoice_items_by_invoice_id(invoice_id)
        created_items = []
        for item in normalized["items"]:
            created = self.repo.create_invoice_item(invoice_id, item)
            created_items.append(created)

        if invoice.file_id and self.file_repo:
            self.file_repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=invoice.file_id,
                    action="view",
                    user_id=user_id,
                )
            )

        return {
            "status": "success",
            "invoice_id": invoice_id,
            "updated_invoice": {
                "invoice_num": normalized["invoice_num"],
                "invoice_date": normalized["invoice_date"],
                "vat_rate": normalized["vat_rate"],
                "vat_amount": normalized["vat_amount"],
                "total_amount": normalized["total_amount"],
            },
            "items_count": len(created_items),
        }

    def create_invoice(self, payload: InvoiceCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("is_delivery_included", False)
        data.setdefault("prepayment_percent", 0)
        data.setdefault("due_days", 0)
        data.setdefault("valid_until", 0)
        data.setdefault("is_urgent", False)
        data.setdefault("total_amount", 0)
        data.setdefault("vat_rate", 0)
        data.setdefault("vat_amount", 0)
        data.setdefault("status", DEFAULT_NEW_STATUS_ID)
        data["created_by"] = user_id

        created = self.repo.create_invoice(data)
        return self.get_invoice(created.id)

    def create_invoice_with_file(
        self,
        payload: InvoiceCreate,
        user_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
    ):
        if not self.file_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File repository is not configured",
            )

        file_type = self.file_repo.get_file_type_by_id(INVOICE_FILE_TYPE_ID)
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active invoice file type not found",
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

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        directory_suffix = str(payload.request_id) if payload.request_id is not None else user_id
        invoice_dir = os.path.join(BASE_INVOICE_FILES_DIR, directory_suffix)
        self._ensure_directory(invoice_dir)

        file_path = os.path.join(invoice_dir, storage_name)
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

        data = payload.model_dump(exclude_unset=True)
        data["file_id"] = created_file.id
        data.setdefault("is_delivery_included", False)
        data.setdefault("prepayment_percent", 0)
        data.setdefault("due_days", 0)
        data.setdefault("valid_until", 0)
        data.setdefault("is_urgent", False)
        data.setdefault("total_amount", 0)
        data.setdefault("vat_rate", 0)
        data.setdefault("vat_amount", 0)
        data.setdefault("status", DEFAULT_NEW_STATUS_ID)
        data["created_by"] = user_id

        created = self.repo.create_invoice(data)
        return self.get_invoice(created.id)

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Cannot create directory '{path}'. "
                    "Set SUPPLY_INVOICE_FILES_DIR to a writable path."
                ),
            ) from exc

    def update_invoice(self, invoice_id: int, payload: InvoiceUpdate):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(invoice, key, value)

        updated = self.repo.save_invoice(invoice)
        return self.get_invoice(updated.id)

    def delete_invoice(self, invoice_id: int):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        self.repo.delete_invoice(invoice)
        return None

    def get_invoice_file_download_payload(self, invoice_id: int, user_id: str):
        if not self.file_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File repository is not configured",
            )

        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if not invoice.file_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice file not found",
            )

        file_row = self.file_repo.get_file_by_id(invoice.file_id)
        if not file_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice file not found",
            )
        if not os.path.exists(file_row.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk",
            )

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

    def create_invoice_item(self, invoice_id: int, payload: InvoiceItemCreate):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        item = self.repo.create_invoice_item(invoice_id, data)
        unit_names = self.repo.get_unit_names([item.unit_id] if item.unit_id else [])
        return self._item_to_dict(item, unit_names)

    def update_invoice_item(self, invoice_id: int, item_id: str, payload: InvoiceItemUpdate):
        item = self.repo.get_invoice_item_by_id(invoice_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_invoice_item(item)
        unit_names = self.repo.get_unit_names([updated.unit_id] if updated.unit_id else [])
        return self._item_to_dict(updated, unit_names)

    def delete_invoice_item(self, invoice_id: int, item_id: str):
        item = self.repo.get_invoice_item_by_id(invoice_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

        self.repo.delete_invoice_item(item)
        return None

    def get_invoice(self, invoice_id: int):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        items = self.repo.get_invoice_items(invoice_id)
        unit_ids = [item.unit_id for item in items if item.unit_id]
        unit_names = self.repo.get_unit_names(unit_ids)
        return {
            "id": invoice.id,
            "num": invoice.num,
            "date": invoice.date,
            "request_id": invoice.request_id,
            "file_id": invoice.file_id,
            "file": self._build_file_payload(invoice.file_id),
            "provider_id": invoice.provider_id,
            "provider": self._build_counterparty_payload(invoice.provider_id),
            "payer_id": invoice.payer_id,
            "payer": self._build_counterparty_payload(invoice.payer_id),
            "is_delivery_included": invoice.is_delivery_included,
            "prepayment_percent": invoice.prepayment_percent,
            "due_days": invoice.due_days,
            "valid_until": invoice.valid_until,
            "is_urgent": invoice.is_urgent,
            "total_amount": invoice.total_amount,
            "vat_rate": invoice.vat_rate,
            "vat_amount": invoice.vat_amount,
            "status": invoice.status,
            "status_name": self.repo.get_status_name(invoice.status),
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
            "created_by": invoice.created_by,
            "items": [self._item_to_dict(item, unit_names) for item in items],
        }

    @staticmethod
    def _item_to_dict(item, unit_names: dict[str, str] | None = None):
        unit_names = unit_names or {}
        return {
            "id": item.id,
            "invoice_id": item.invoice_id,
            "name": item.name,
            "unit_name": item.unit_name,
            "quantity": item.quantity,
            "price": item.price,
            "sum": item.sum,
            "nds": item.nds,
            "value_nds": item.value_nds,
            "unit_id": item.unit_id,
            "unit_converted_name": unit_names.get(item.unit_id) if item.unit_id else None,
            "converted_quantity": item.converted_quantity,
        }

    def _build_counterparty_payload(self, counterparty_id: str | None) -> dict | None:
        if not self.counterparty_repo:
            return None
        return self.counterparty_repo.get_counterparty_brief(counterparty_id)

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

    def _normalize_invoice_payload(self, payload: dict) -> dict:
        items = payload.get("items")
        if not isinstance(items, list):
            items = []

        return {
            "invoice_num": self._as_str(payload.get("invoice_num")),
            "invoice_date": self._as_date(payload.get("invoice_date")),
            "vat_rate": self._as_int(payload.get("vat_rate")),
            "vat_amount": self._as_money(payload.get("vat_amount")),
            "total_amount": self._as_money(payload.get("total_amount")),
            "items": [self._normalize_item(item) for item in items if isinstance(item, dict)],
        }

    def _normalize_item(self, item: dict) -> dict:
        return {
            "name": self._as_str(item.get("name")),
            "unit_name": self._as_str(item.get("unit_name")),
            "quantity": self._as_money(item.get("quantity")),
            "price": self._as_money(item.get("price")),
            "sum": self._as_money(item.get("sum")),
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
            amount = Decimal(candidate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(amount)
        except (InvalidOperation, ValueError):
            return None

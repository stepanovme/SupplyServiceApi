import hashlib
import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB
from app.models.project_user_role import ProjectUserRoleType
from app.models.invoice import (
    InvoiceCreate,
    InvoiceLogCreate,
    InvoiceLogUpdate,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoicePaymentCreate,
    InvoicePaymentUpdate,
    InvoiceUpdate,
)
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.invoice_user_repository import InvoiceUserRepository
from app.repositories.object_setting_repository import ObjectSettingRepository
from app.services.project_name_builder import build_project_name, load_project_reference_maps
from app.services.invoice_requisites import REQUISITE_FIELDS, clean_requisite, fix_account_roles, normalize_requisites
from app.services.invoice_vat import normalize_vat_rate
from app.services.mistral_retry import mistral_retry as _mistral_retry
from app.services.mistral_retry import recognize_document_text as _shared_recognize_document_text

DEFAULT_NEW_STATUS_ID = "1ff34436-1312-11f1-aa8c-bc241127d0bd"
APPROVED_STATUS_ID = "c532989f-17ba-11f1-aa8c-bc241127d0bd"
REJECTED_STATUS_ID = "1ff33ee2-1312-11f1-aa8c-bc241127d0bd"
INVOICE_FILE_TYPE_ID = "4594a94b-140f-11f1-aa8c-bc241127d0bd"
BASE_INVOICE_FILES_DIR = os.getenv(
    "SUPPLY_INVOICE_FILES_DIR",
    "/home/webserver/models/supply/invoices",
)


from app.services.mistral_retry import mistral_retry as _mistral_retry


# Appended to the extraction prompts: the payee's payment details block ("Получатель", "Банк получателя").
RECIPIENT_PROMPT_KEYS = (
    '  "recipient_inn": string|null,\n'
    '  "recipient_kpp": string|null,\n'
    '  "recipient_bank_name": string|null,\n'
    '  "recipient_account": string|null,\n'
    '  "recipient_corr_account": string|null,\n'
    '  "recipient_bik": string|null,\n'
    '  "payment_purpose": string|null,\n'
    '  // recipient_* = payment details of the PAYEE (the seller who gets the money), taken from the block with '
    'bank details ("Получатель", "Банк получателя", "Образец заполнения платёжного поручения"). '
    'recipient_inn / recipient_kpp belong to the payee ORGANIZATION, not to the bank. '
    'recipient_account is its settlement account (Р/С, 20 digits), recipient_corr_account is the bank\'s '
    'correspondent account (К/С, 20 digits), recipient_bik is 9 digits. payment_purpose only if the document states '
    'the wording of the payment purpose. Digits only, no spaces. Never take the buyer\'s details. '
    'Both accounts are often just labelled "Сч. №": the correspondent account (К/С) is the one that starts with 301, '
    'the payee\'s settlement account (Р/С) usually starts with 40 (e.g. 40702...).\n'
)


class InvoiceService:
    def __init__(
        self,
        repo: InvoiceRepository,
        file_repo: RequestFileRepository | None = None,
        counterparty_repo: CounterpartyRepository | None = None,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        project_user_role_repo: ProjectUserRoleRepository | None = None,
        invoice_user_repo: InvoiceUserRepository | None = None,
        object_setting_repo: ObjectSettingRepository | None = None,
    ) -> None:
        self.repo = repo
        self.file_repo = file_repo
        self.counterparty_repo = counterparty_repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.project_user_role_repo = project_user_role_repo
        self.invoice_user_repo = invoice_user_repo
        self.object_setting_repo = object_setting_repo

    def get_all(self, user_id: str | None = None):
        invoices = self.repo.get_invoices()
        if user_id:
            invoices = self._filter_visible(invoices, user_id)
        return self._serialize_invoice_list(invoices)

    def get_by_object(self, object_id: str):
        invoices = self.repo.get_invoices()

        level_ids = self.reference_repo.get_level_ids_by_object_ids([object_id]) if self.reference_repo else set()

        request_ids = [invoice.request_id for invoice in invoices if invoice.request_id is not None]
        request_meta = self.repo.get_requests_meta_by_ids(request_ids)

        matched = []
        for invoice in invoices:
            object_levels_id = invoice.object_levels_id
            if not object_levels_id and invoice.request_id is not None:
                object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
            if not object_levels_id:
                continue
            if invoice.object_type == "object" and object_levels_id == object_id:
                matched.append(invoice)
            elif object_levels_id in level_ids:
                matched.append(invoice)

        return self._serialize_invoice_list(matched)

    def get_available_for_user(self, user_id: str):
        logs = self.repo.get_invoice_logs_by_user(user_id)
        invoice_ids = {log.invoice_id for log in logs}

        all_invoices = self.repo.get_invoices()
        managed_level_ids = self._get_supply_manager_level_ids(user_id)
        request_meta = self.repo.get_requests_meta_by_ids(
            [invoice.request_id for invoice in all_invoices if invoice.request_id is not None]
        )
        for invoice in all_invoices:
            if invoice.created_by == user_id:
                invoice_ids.add(invoice.id)
                continue
            if managed_level_ids:
                object_levels_id = invoice.object_levels_id
                if not object_levels_id and invoice.request_id is not None:
                    object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
                if object_levels_id in managed_level_ids and invoice.status != DEFAULT_NEW_STATUS_ID:
                    invoice_ids.add(invoice.id)

        if self.invoice_user_repo:
            observer_ids = self.invoice_user_repo.get_invoice_ids_by_user_id_and_role(
                user_id, "observer",
            )
            invoice_ids.update(observer_ids)

        # For public object‑type invoices, also grant access via object_settings
        accessible_object_ids: set[str] = set()
        if self.object_setting_repo:
            accessible_object_ids = self.object_setting_repo.get_accessible_object_ids_for_user(user_id)
            if accessible_object_ids:
                for inv in all_invoices:
                    if getattr(inv, "privacy", "public") == "public" and inv.object_type == "object" and inv.object_levels_id and inv.object_levels_id in accessible_object_ids and inv.status != DEFAULT_NEW_STATUS_ID:
                        invoice_ids.add(inv.id)

        invoices = self.repo.get_invoices_by_ids(list(invoice_ids))

        # Filter out private invoices — only participants can see them
        log_invoice_ids = {log.invoice_id for log in logs}
        obs_ids: set[int] = set()
        if self.invoice_user_repo:
            obs_ids = set(self.invoice_user_repo.get_invoice_ids_by_user_id_and_role(user_id, "observer"))
        result = []
        for inv in invoices:
            privacy = getattr(inv, "privacy", "public")
            if privacy == "private":
                if self._is_invoice_participant(inv, user_id, log_invoice_ids, obs_ids):
                    result.append(inv)
            else:
                result.append(inv)

        return self._serialize_invoice_list(result)

    def _is_invoice_participant(
        self, inv, user_id: str,
        log_invoice_ids: set[int] | None = None,
        observer_ids: set[int] | None = None,
    ) -> bool:
        if inv.created_by == user_id:
            return True
        if inv.from_by == user_id:
            return True
        if log_invoice_ids and inv.id in log_invoice_ids:
            return True
        if observer_ids and inv.id in observer_ids:
            return True
        return False

    def _has_legacy_access(
        self, inv, user_id: str,
        managed_level_ids: set[str],
        request_meta: dict,
        log_invoice_ids: set[int] | None = None,
        observer_ids: set[int] | None = None,
    ) -> bool:
        if log_invoice_ids and inv.id in log_invoice_ids:
            return True
        if inv.created_by == user_id:
            return True
        if inv.id in (observer_ids or set()):
            return True
        if managed_level_ids:
            object_levels_id = inv.object_levels_id
            if not object_levels_id and inv.request_id is not None:
                object_levels_id = request_meta.get(inv.request_id, {}).get("object_levels_id")
            if object_levels_id in managed_level_ids:
                return True
        return False

    def _filter_visible(self, invoices: list, user_id: str) -> list:
        log_invoice_ids = {log.invoice_id for log in self.repo.get_invoice_logs_by_user(user_id)}
        obs_ids: set[int] = set()
        if self.invoice_user_repo:
            obs_ids = set(self.invoice_user_repo.get_invoice_ids_by_user_id_and_role(user_id, "observer"))
        result = []
        for inv in invoices:
            privacy = getattr(inv, "privacy", "public")
            if privacy == "private":
                if self._is_invoice_participant(inv, user_id, log_invoice_ids, obs_ids):
                    result.append(inv)
            else:
                result.append(inv)
        return result

    def get_badge_counts(self, user_id: str):
        return self.repo.get_badge_counts(user_id)

    def get_my_invoice_payments(self, user_id: str, paid: bool | None = None, limit: int = 100, offset: int = 0):
        logs = self.repo.get_invoice_logs_by_user(user_id)
        invoice_ids = {log.invoice_id for log in logs}

        all_invoices = self.repo.get_invoices()
        managed_level_ids = self._get_supply_manager_level_ids(user_id)
        request_meta = self.repo.get_requests_meta_by_ids(
            [invoice.request_id for invoice in all_invoices if invoice.request_id is not None]
        )
        for invoice in all_invoices:
            if invoice.created_by == user_id:
                invoice_ids.add(invoice.id)
                continue
            if managed_level_ids:
                object_levels_id = invoice.object_levels_id
                if not object_levels_id and invoice.request_id is not None:
                    object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
                if object_levels_id in managed_level_ids and invoice.status != DEFAULT_NEW_STATUS_ID:
                    invoice_ids.add(invoice.id)

        if not invoice_ids:
            return []

        invoices_map = {inv.id: inv for inv in self.repo.get_invoices_by_ids(list(invoice_ids))}

        payments = self.repo.get_invoice_payments_by_invoice_ids(list(invoice_ids))
        extract_links = self.repo.get_extract_links_by_payment_ids([p.id for p in payments])

        # collect user ids and counterparty ids
        user_ids: set[str] = set()
        counterparty_ids: set[str] = set()
        for payment in payments:
            if payment.created_by:
                user_ids.add(payment.created_by)
            if payment.paid_by:
                user_ids.add(payment.paid_by)
            invoice = invoices_map.get(payment.invoice_id)
            if invoice:
                if invoice.created_by:
                    user_ids.add(invoice.created_by)
                if invoice.from_by:
                    user_ids.add(invoice.from_by)
                if invoice.provider_id:
                    counterparty_ids.add(invoice.provider_id)
                if invoice.payer_id:
                    counterparty_ids.add(invoice.payer_id)

        users_by_id = self._get_users_map(list(user_ids))
        counterparty_names = self.reference_repo.get_counterparty_names(list(counterparty_ids)) if self.reference_repo else {}
        counterparty_logos = self.reference_repo.get_counterparty_logos(list(counterparty_ids)) if self.reference_repo else {}

        # The object of an invoice, resolved exactly as in the invoice list: the invoice's own
        # object_levels_id, or the one of its request.
        payment_invoices = [invoices_map[p.invoice_id] for p in payments if p.invoice_id in invoices_map]
        levels_by_invoice: dict[int, str | None] = {}
        for inv in payment_invoices:
            level_id = inv.object_levels_id
            if not level_id and inv.request_id is not None:
                level_id = request_meta.get(inv.request_id, {}).get("object_levels_id")
            levels_by_invoice[inv.id] = level_id

        levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(
            self.reference_repo, [lvl for lvl in levels_by_invoice.values() if lvl]
        ) if self.reference_repo else ({}, {}, {}, {})
        direct_object_ids = {
            inv.object_levels_id for inv in payment_invoices if inv.object_type == "object" and inv.object_levels_id
        }
        object_names = {}
        if direct_object_ids and self.reference_repo:
            for obj in self.reference_repo.get_objects_by_ids(list(direct_object_ids)):
                object_names[obj.id] = obj.short_name or obj.full_name

        result = []
        for payment in payments:
            invoice = invoices_map.get(payment.invoice_id)
            if not invoice:
                continue
            is_paid = payment.paid_at is not None
            if paid is not None and paid != is_paid:
                continue
            object_levels_id = levels_by_invoice.get(invoice.id)
            if invoice.object_type == "object":
                project_name = object_names.get(object_levels_id)
            else:
                project_name = build_project_name(
                    object_levels_id, levels_by_id, objects_by_id, contracts_by_id, work_types_by_id
                ) if self.reference_repo else None
            result.append({
                "payment": self._map_payment(payment, users_by_id, extract_links),
                "invoice": {
                    "id": invoice.id,
                    "num": invoice.num,
                    "date": invoice.date,
                    "total_amount": invoice.total_amount,
                    "provider_id": invoice.provider_id,
                    "provider_name": counterparty_names.get(invoice.provider_id),
                    "provider_logo_url": counterparty_logos.get(invoice.provider_id),
                    "payer_id": invoice.payer_id,
                    "payer_name": counterparty_names.get(invoice.payer_id),
                    "payer_logo_url": counterparty_logos.get(invoice.payer_id),
                    "object_levels_id": object_levels_id,
                    "object_type": invoice.object_type,
                    "project_name": project_name,
                    **self._requisites_block(invoice),
                    "from_by": invoice.from_by,
                    "from_by_user": self._map_user(users_by_id.get(invoice.from_by)),
                },
            })

        sort_key = "updated_at" if paid is not None else "created_at"
        result.sort(key=lambda row: (row["payment"][sort_key] or datetime.min), reverse=True)
        return result

    def _push_badge_for_invoice_users(self, invoice_id: int) -> None:
        from app.services.ws_manager import ws_manager
        logs = self.repo.get_invoice_logs(invoice_id)
        seen = set()
        for log in logs:
            if log.user_id and log.user_id not in seen:
                seen.add(log.user_id)
                counts = self.repo.get_badge_counts(log.user_id)
                ws_manager.send_badge_counts(log.user_id, counts)

    def parse_invoice_file_and_update(self, invoice_id: int, file_path: str, user_id: str, provider: str = "mistral"):
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

        if provider == "groq":
            if not self.file_repo:
                raise HTTPException(status_code=500, detail="File repository is not configured")
            ids = {row.file_id for row in self.repo.get_invoice_files(invoice_id)}
            if invoice.file_id:
                ids.add(invoice.file_id)
            paths = [self.file_repo.get_file_by_id(file_id) for file_id in ids]
            if not any(row and os.path.realpath(row.file_path) == os.path.realpath(file_path) for row in paths):
                raise HTTPException(status_code=403, detail="File is not attached to this invoice")

        try:
            with open(file_path, "rb") as file_stream:
                file_bytes = file_stream.read(15 * 1024 * 1024 + 1) if provider == "groq" else file_stream.read()
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot read file: {file_path}",
            ) from exc


        if provider == "groq":
            from app.services.groq_invoice_recognition import recognize_invoice_text
            document_text = recognize_invoice_text(file_path, file_bytes)
            if len(document_text) > 150000:
                raise HTTPException(status_code=413, detail="Распознанный текст счёта слишком большой")
        elif provider == "mistral":
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


            client = Mistral(api_key=mistral_api_key)
            try:
                uploaded_file = _mistral_retry(
                    client.files.upload,
                    file={"file_name": os.path.basename(file_path), "content": file_bytes},
                    purpose="ocr",
                )
                signed_url = _mistral_retry(client.files.get_signed_url, file_id=uploaded_file.id)
                document_text = self._recognize_document_text(client, signed_url.url)
            except Exception as exc:
                if self._is_mistral_rate_limit(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Сервис распознавания документов временно перегружен (лимит запросов). Попробуйте ещё раз через минуту.",
                    ) from exc
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось распознать документ",
                ) from exc

        else:
            raise HTTPException(status_code=400, detail="Unknown recognition provider")

        prompt = (
            "Extract invoice data from the document.\n"
            "Return ONLY valid JSON object with keys:\n"
            "{\n"
            '  "invoice_num": string|null,\n'
            '  "invoice_date": "YYYY-MM-DD"|null,\n'
            '  "vat_rate": 0|5|7|10|22|null,\n'
            '  "vat_amount": number|null,\n'
            '  "total_amount": number|null,\n'
            + RECIPIENT_PROMPT_KEYS +
            '  "items": [\n'
            "    {\n"
            '      "name": string|null,\n'
            '      "unit_name": string|null,\n'
            '      "quantity": number|null,\n'
            '      "price": number|null,\n'
            '      "sum": number|null,\n'
            '      "num": int|null,\n'
            '      "type": "product"|"service"|"delivery"|"tax"|"equipment"|null\n'
            "    }\n"
            "  ]\n"
            "}\n"
            '"num" is the sequential position number (1, 2, 3...) of the item in the invoice.\n'
            '"type" categorizes the item. Rules:\n'
            '- "equipment" for tools, machinery, devices, appliances and instrumenty — anything physical/mechanical/electronic that performs a function: angle grinder/шлифовальная машинка, огнетушитель, молоток, отвертка, телефон, видеокарта, станок, насос, компрессор, сварочный аппарат, компьютер, монитор, принтер, камера, электродрель, лопата, перфоратор, газовый баллон and similar tools/instruments/equipment.\n'
            '- "product" for consumable goods/расходные материалы и товары (e.g. краска, крепеж, кабель, кирпич, расходники) that are not tools or devices.\n'
            '- "service" for услуги (e.g. монтаж, ремонт, доставка есть отдельно, обслуживание).\n'
            '- "delivery" for доставка/транспортные услуги.\n'
            '- "tax" for налоги/сборы.\n'
            'When in doubt, prefer "equipment" for tools/instruments/devices over "product".\n'
            "If field is missing in document, set null.\n"
            '"vat_rate" is the VAT percent of the invoice in 2026: ONLY 0, 5, 7, 10 or 22 (the 20% rate no longer exists; '
            'never answer 20 or 18). "Без НДС" / "НДС не облагается" means 0. Take it from the document text, and it must be consistent '
            'with "vat_amount" (VAT amount = total * rate / (100 + rate) when VAT is included in the total).\n'
            "Document:\n"
            f"{document_text[:150000] if provider == 'groq' else document_text[:15000]}"
        )

        if provider == "groq":
            from app.services.groq_invoice_recognition import extract_invoice_json
            raw_content = extract_invoice_json(prompt)
        else:
            try:
                chat_response = _mistral_retry(
                    client.chat.complete,
                    model="ministral-8b-2512",
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as exc:
                if self._is_mistral_rate_limit(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Сервис распознавания документов временно перегружен (лимит запросов). Попробуйте ещё раз через минуту.",
                    ) from exc
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось распознать документ",
                ) from exc
            raw_content = chat_response.choices[0].message.content
            if isinstance(raw_content, list):
                raw_content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in raw_content
                )

        parsed_payload = self._extract_json_payload(raw_content, provider="Groq" if provider == "groq" else "Mistral")

        normalized = self._normalize_invoice_payload(parsed_payload)
        invoice.num = normalized["invoice_num"]
        invoice.date = normalized["invoice_date"]
        invoice.total_amount = normalized["total_amount"] if normalized["total_amount"] is not None else 0
        invoice.vat_rate = normalized["vat_rate"] if normalized["vat_rate"] is not None else 0
        invoice.vat_amount = normalized["vat_amount"] if normalized["vat_amount"] is not None else 0
        # Recipient requisites: only what was actually recognised (and looks valid) is written, so an
        # unrecognised field never erases a value somebody typed in.
        recognised = {k: v for k, v in self._recognised_requisites(parsed_payload).items() if v is not None}
        for field, value in recognised.items():
            setattr(invoice, field, value)
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
                **{field: getattr(invoice, field, None) for field in REQUISITE_FIELDS},
            },
            "recognized_requisites": sorted(recognised),
            "items_count": len(created_items),
        }

    def upload_invoice_file(self, invoice_id: int, file_bytes: bytes, original_name: str, mime_type: str, user_id: str):
        if not self.file_repo:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File repository is not configured")

        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        file_type = self.file_repo.get_file_type_by_id(INVOICE_FILE_TYPE_ID)
        if not file_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active invoice file type not found")

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")

        allowed_extensions = file_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File extension .{extension} is not allowed")

        max_size_mb = file_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File size exceeds {max_size_mb} MB")

        old_file_id = invoice.file_id

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        directory_suffix = str(invoice.request_id) if invoice.request_id is not None else str(invoice_id)
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

        if old_file_id:
            old_file = self.file_repo.get_file_by_id(old_file_id)
            if old_file:
                self.file_repo.mark_file_deleted(old_file)
                self.file_repo.add_audit(
                    FileAudit(
                        id=str(uuid.uuid4()),
                        file_id=old_file_id,
                        action="delete",
                        user_id=user_id,
                    )
                )
                if os.path.exists(old_file.file_path):
                    try:
                        os.remove(old_file.file_path)
                    except OSError:
                        pass

        invoice.file_id = created_file.id
        self.repo.save_invoice(invoice)

        return self.get_invoice(invoice_id)

    def check_duplicate(self, num: str | None, date, provider_id: str | None, payer_id: str | None) -> dict:
        duplicate = self.repo.find_duplicate_invoice(
            provider_id=provider_id,
            payer_id=payer_id,
            num=num,
            date=date,
        )
        return {"is_duplicate": duplicate is not None, "invoice": duplicate}

    def parse_counterparty_from_file(self, file_bytes: bytes, file_name: str):
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MISTRAL_API_KEY is not set")

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        client = Mistral(api_key=mistral_api_key)
        try:
            uploaded_file = _mistral_retry(
                client.files.upload,
                file={"file_name": file_name, "content": file_bytes},
                purpose="ocr",
            )
            signed_url = _mistral_retry(client.files.get_signed_url, file_id=uploaded_file.id)
            document_text = self._recognize_document_text(client, signed_url.url)
        except Exception as exc:
            if self._is_mistral_rate_limit(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Сервис распознавания документов временно перегружен (лимит запросов). Попробуйте ещё раз через минуту.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось распознать документ",
            ) from exc

        prompt = (
            "Extract invoice data from the document.\n"
            "Return ONLY valid JSON object with keys:\n"
            "{\n"
            '  "seller_inn": string|null,\n'
            '  "buyer_inn": string|null,\n'
            '  "invoice_num": string|null,\n'
            + RECIPIENT_PROMPT_KEYS +
            '  "invoice_date": "YYYY-MM-DD"|null\n'
            "}\n"
            "INN is a 10 or 12 digit number.\n"
            "If field is missing in document, set null.\n"
            "Document:\n"
            f"{document_text[:15000]}"
        )

        try:
            chat_response = _mistral_retry(
                client.chat.complete,
                model="ministral-8b-2512",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            if self._is_mistral_rate_limit(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Сервис распознавания документов временно перегружен (лимит запросов). Попробуйте ещё раз через минуту.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось распознать документ",
            ) from exc
        raw_content = chat_response.choices[0].message.content
        if isinstance(raw_content, list):
            raw_content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_content
            )
        parsed = self._extract_json_payload(raw_content)

        seller_inn = parsed.get("seller_inn")
        buyer_inn = parsed.get("buyer_inn")
        invoice_num = self._as_str(parsed.get("invoice_num"))
        invoice_date = self._as_date(parsed.get("invoice_date"))

        seller = self.counterparty_repo.find_by_inn(str(seller_inn)) if seller_inn and self.counterparty_repo else None
        buyer = self.counterparty_repo.find_by_inn(str(buyer_inn)) if buyer_inn and self.counterparty_repo else None

        duplicate = None
        if seller and buyer and invoice_num and invoice_date:
            duplicate = self.repo.find_duplicate_invoice(
                provider_id=seller.get("id"),
                payer_id=buyer.get("id"),
                num=invoice_num,
                date=invoice_date,
            )

        return {
            "seller_inn": seller_inn,
            "buyer_inn": buyer_inn,
            "invoice_num": invoice_num,
            "invoice_date": invoice_date,
            "seller": seller,
            "buyer": buyer,
            "duplicate": duplicate,
            "recipient": self._recognised_requisites(parsed),
        }

    def create_invoice(self, payload: InvoiceCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data = self._apply_request_object_levels_fallback(data)
        data.setdefault("is_delivery_included", False)
        data.setdefault("prepayment_percent", 0)
        data.setdefault("due_days", 0)
        data.setdefault("valid_until", 0)
        data.setdefault("is_urgent", False)
        data.setdefault("total_amount", 0)
        data.setdefault("vat_rate", 0)
        data.setdefault("vat_amount", 0)
        data.setdefault("status", DEFAULT_NEW_STATUS_ID)
        data.setdefault("type", "incoming")
        data.setdefault("privacy", "public")
        data.update(normalize_requisites(data))  # recipient requisites: validated, optional
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
        data = self._apply_request_object_levels_fallback(data)
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
        data.setdefault("privacy", "public")
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
        data = self._apply_request_object_levels_fallback(data, current_invoice=invoice)
        data.update(normalize_requisites(data))  # recipient requisites: validated, optional
        for key, value in data.items():
            setattr(invoice, key, value)

        updated = self.repo.save_invoice(invoice)
        return self.get_invoice(updated.id)

    def set_closing_docs_mark(self, invoice_id: int, not_required: bool, user_id: str):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        invoice.closing_docs_not_required = not_required
        invoice.closing_docs_not_required_at = datetime.now() if not_required else None
        invoice.closing_docs_not_required_by = user_id if not_required else None
        self.repo.save_invoice(invoice)
        return self.get_invoice(invoice_id)

    def set_delivery_mark(self, invoice_id: int, not_required: bool, user_id: str):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        invoice.delivery_not_required = not_required
        invoice.delivery_not_required_at = datetime.now() if not_required else None
        invoice.delivery_not_required_by = user_id if not_required else None
        self.repo.save_invoice(invoice)
        return self.get_invoice(invoice_id)

    def delete_invoice(self, invoice_id: int):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        from app.repositories.documents_link_repository import DocumentsLinkRepository
        DocumentsLinkRepository(self.repo.db).delete_for_document("invoice", str(invoice_id))
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

    def get_invoice_file_preview_path(self, invoice_id: int) -> str:
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
        if not file_row.file_path or not os.path.exists(file_row.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk",
            )

        file_path = file_row.file_path
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return file_path

        IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
        if ext in IMAGE_EXTENSIONS:
            from app.services.pdf_converter import convert_image_to_pdf
            cached = Path(file_path).parent / f"{Path(file_path).name}.preview.pdf"
            if cached.exists():
                return str(cached)
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            pdf_bytes = convert_image_to_pdf(file_bytes, file_row.original_name)
            with open(cached, "wb") as f:
                f.write(pdf_bytes)
            return str(cached)

        PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}
        if ext not in PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Preview not supported for this file type")

        cached = Path(file_path).parent / f"{Path(file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

        import subprocess
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=500, detail="Conversion produced no output")

        return str(cached)

    # --- Additional invoice files (invoice_files table) ---

    def get_invoice_additional_files(self, invoice_id: int) -> list[dict]:
        rows = self.repo.get_invoice_files(invoice_id)
        result = []
        for row in rows:
            file_row = self.file_repo.get_file_by_id(row.file_id) if self.file_repo else None
            if file_row:
                result.append({
                    "id": row.id,
                    "invoice_id": row.invoice_id,
                    "file_id": row.file_id,
                    "original_name": file_row.original_name,
                    "extension": file_row.extension,
                    "mime_type": file_row.mime_type,
                    "file_size": file_row.file_size,
                    "uploaded_by": file_row.uploaded_by,
                    "uploaded_at": file_row.uploaded_at,
                })
        return result

    def upload_invoice_additional_file(
        self, invoice_id: int, file_bytes: bytes, original_name: str, mime_type: str, user_id: str,
    ) -> dict:
        if not self.file_repo:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File repository is not configured")

        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        directory_suffix = str(invoice.request_id) if invoice.request_id is not None else str(invoice_id)
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
            file_type_id=INVOICE_FILE_TYPE_ID,
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

        invoice_file_row = self.repo.create_invoice_file({
            "invoice_id": invoice_id,
            "file_id": created_file.id,
        })

        return {
            "id": invoice_file_row.id,
            "invoice_id": invoice_id,
            "file_id": created_file.id,
            "original_name": original_name,
            "extension": extension,
            "mime_type": mime_type,
            "file_size": len(file_bytes),
        }

    def get_invoice_additional_file_download_payload(
        self, invoice_id: int, invoice_file_id: str, user_id: str,
    ) -> dict:
        if not self.file_repo:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File repository is not configured")

        invoice_file_row = self.repo.get_invoice_file_by_id(invoice_file_id)
        if not invoice_file_row or invoice_file_row.invoice_id != invoice_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        file_row = self.file_repo.get_file_by_id(invoice_file_row.file_id)
        if not file_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
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

    def delete_invoice_additional_file(
        self, invoice_id: int, invoice_file_id: str, user_id: str,
    ) -> None:
        if not self.file_repo:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File repository is not configured")

        invoice_file_row = self.repo.get_invoice_file_by_id(invoice_file_id)
        if not invoice_file_row or invoice_file_row.invoice_id != invoice_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        file_row = self.file_repo.get_file_by_id(invoice_file_row.file_id)
        if file_row:
            self.file_repo.mark_file_deleted(file_row)
            self.file_repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=file_row.id,
                    action="delete",
                    user_id=user_id,
                )
            )
            if os.path.exists(file_row.file_path):
                try:
                    os.remove(file_row.file_path)
                except OSError:
                    pass

        self.repo.delete_invoice_file(invoice_file_row)

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

    # Fixed payment planner / payer, added to every invoice that goes to approval. Override with .env.
    @staticmethod
    def _default_planner_id() -> str:
        return os.getenv("INVOICE_DEFAULT_PLANNER_ID", "8f1d6ffd-6652-4719-a426-5b21412d7c56")

    @staticmethod
    def _default_payer_id() -> str:
        return os.getenv("INVOICE_DEFAULT_PAYER_ID", "06968a8b-e24c-4099-998d-3d4c16ebc63a")

    def ensure_planning_and_payment_users(self, invoice_id: int) -> list:
        """Adds the planner (type planing) and the payer (type payment) if the invoice has at least one approver.
        Never duplicates: a user already present with that type is skipped. Returns the logs it created."""
        logs = self.repo.get_invoice_logs(invoice_id)
        if not any(l.type == "approval" for l in logs):
            return []
        existing = {(l.type, l.user_id) for l in logs}
        created = []
        for log_type, user_id in (("planing", self._default_planner_id()), ("payment", self._default_payer_id())):
            if not user_id or (log_type, user_id) in existing:
                continue
            created.append(self.repo.create_invoice_log(invoice_id, {"user_id": user_id, "type": log_type}))
        if created:
            from app.services.ws_manager import ws_manager
            for user_id in {l.user_id for l in created}:
                ws_manager.send_badge_counts(user_id, self.repo.get_badge_counts(user_id))
        return created

    def create_invoice_log(self, invoice_id: int, payload: InvoiceLogCreate):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        duplicate = None
        if data.get("type") in ("planing", "payment"):
            duplicate = next(
                (l for l in self.repo.get_invoice_logs(invoice_id) if l.type == data["type"] and l.user_id == data.get("user_id")),
                None,
            )
        created = duplicate or self.repo.create_invoice_log(invoice_id, data)
        users_by_id = self._get_users_map([created.user_id])
        result = {
            "id": created.id,
            "invoice_id": created.invoice_id,
            "user_id": created.user_id,
            "user": self._map_user(users_by_id.get(created.user_id)),
            "type": created.type,
            "status_name": created.status_name,
            "date_response": created.date_response,
        }
        if duplicate:
            return result
        if created.user_id:
            from app.services.ws_manager import ws_manager
            counts = self.repo.get_badge_counts(created.user_id)
            ws_manager.send_badge_counts(created.user_id, counts)

        if created.type == "approval":
            self.ensure_planning_and_payment_users(invoice_id)

        if created.type == "approval" and created.status_name in ("approved", "rejected") and created.user_id:
            self._notify_approval(invoice, created.user_id)

        return result

    def update_invoice_log(self, invoice_id: int, log_id: str, payload: InvoiceLogUpdate):
        row = self.repo.get_invoice_log_by_id(invoice_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice log not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_invoice_log(row)
        users_by_id = self._get_users_map([updated.user_id])
        result = {
            "id": updated.id,
            "invoice_id": updated.invoice_id,
            "user_id": updated.user_id,
            "user": self._map_user(users_by_id.get(updated.user_id)),
            "type": updated.type,
            "status_name": updated.status_name,
            "date_response": updated.date_response,
        }
        if updated.user_id:
            from app.services.ws_manager import ws_manager
            counts = self.repo.get_badge_counts(updated.user_id)
            ws_manager.send_badge_counts(updated.user_id, counts)

        if updated.type == "approval" and updated.status_name in ("approved", "rejected") and updated.user_id:
            invoice = self.repo.get_invoice_by_id(invoice_id)
            if invoice:
                self._notify_approval(invoice, updated.user_id)

        return result

    def delete_invoice_log(self, invoice_id: int, log_id: str):
        row = self.repo.get_invoice_log_by_id(invoice_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice log not found")
        target_user_id = row.user_id
        self.repo.delete_invoice_log(row)
        if target_user_id:
            from app.services.ws_manager import ws_manager
            counts = self.repo.get_badge_counts(target_user_id)
            ws_manager.send_badge_counts(target_user_id, counts)
        return None

    def create_invoice_payment(self, invoice_id: int, payload: InvoicePaymentCreate, created_by: str):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by

        created = self.repo.create_invoice_payment(invoice_id, data)
        users_by_id = self._get_users_map(
            [user_id for user_id in [created.created_by, created.paid_by] if user_id]
        )
        result = self._map_payment(created, users_by_id)
        self._push_badge_for_invoice_users(invoice_id)

        is_planned = created.paid is None or created.paid == 0
        payment_amount = created.value if is_planned else (created.paid or 0)
        self._notify_payment(invoice, created_by, is_planned=is_planned, payment_amount=payment_amount)

        return result

    def notify_payment_made(self, invoice, actor_user_id: str, amount: float) -> None:
        """Same side effects a manually entered payment gets (see create_invoice_payment /
        update_invoice_payment): refresh badges, then notify the invoice participants. Used when a
        bank-statement match pays a planned payment or creates one."""
        self._push_badge_for_invoice_users(invoice.id)
        self._notify_payment(invoice, actor_user_id, is_planned=False, payment_amount=amount)

    def _collect_invoice_participant_ids(self, invoice) -> set[str]:
        ids: set[str] = set()
        if invoice.created_by:
            ids.add(invoice.created_by)
        if invoice.from_by:
            ids.add(invoice.from_by)
        logs = self.repo.get_invoice_logs(invoice.id)
        for log in logs:
            if log.user_id:
                ids.add(log.user_id)
        if self.invoice_user_repo:
            observers = self.invoice_user_repo.get_by_invoice_id(invoice.id)
            for obs in observers:
                if obs.user_id:
                    ids.add(obs.user_id)
        return ids

    def _format_invoice_desc(self, invoice) -> str:
        invoice_num = invoice.num or f"№{invoice.id}"
        desc = f"№{invoice_num}"
        if invoice.date:
            desc += f" от {invoice.date.strftime('%d.%m.%Y')}"
        return desc

    def _get_request_name(self, invoice) -> str | None:
        if not invoice.request_id:
            return None
        meta = self.repo.get_requests_meta_by_ids([invoice.request_id])
        return meta.get(invoice.request_id, {}).get("name")

    def _notify_payment(self, invoice, exclude_user_id: str, is_planned: bool = False, payment_amount: float = 0) -> None:
        participant_ids = self._collect_invoice_participant_ids(invoice)
        participant_ids.discard(exclude_user_id)
        if not participant_ids:
            return

        payments = self.repo.get_invoice_payments(invoice.id)
        total_planned = sum(pmt.value or 0 for pmt in payments if pmt.paid is None or pmt.paid == 0)
        total_paid = sum(pmt.paid or 0 for pmt in payments)
        total_amount = invoice.total_amount or 0

        desc = self._format_invoice_desc(invoice)
        request_name = self._get_request_name(invoice)

        combined_total = (total_planned + total_paid) if is_planned else total_paid
        is_full = combined_total >= total_amount and total_amount > 0

        if is_planned:
            prefix = "Запланировали полную оплату" if is_full else "Запланировали частичную оплату"
            title = "Планирование оплаты"
            message = f"{prefix} счёта {desc}"
            notif_type = "invoice_payment_planned_full" if is_full else "invoice_payment_planned_partial"
        else:
            prefix = "Полностью оплачен" if is_full else "Частично оплачен"
            title = "Оплата счёта"
            message = f"{prefix} счёт {desc}"
            notif_type = "invoice_paid_full" if is_full else "invoice_paid_partial"

        if payment_amount:
            message += f" на сумму {payment_amount:.2f}"
        if request_name:
            message += f" по заявке \"{request_name}\""

        from app.services.notification_feed_service import push_notification

        for uid in participant_ids:
            self._send_vk_notification(uid, message)
            self._send_push_notification(uid, title, message)
            push_notification(self.repo.db, uid, notif_type,
                              title=title,
                              body=message,
                              object_type="invoice", object_id=str(invoice.id),
                              related_user_id=exclude_user_id)

    def _notify_approval(self, invoice, actor_user_id: str) -> None:
        participant_ids = self._collect_invoice_participant_ids(invoice)
        participant_ids.discard(actor_user_id)
        if not participant_ids:
            return

        actor_fio = self._get_user_fio(actor_user_id)
        desc = self._format_invoice_desc(invoice)
        request_name = self._get_request_name(invoice)

        status_name = None
        logs = self.repo.get_invoice_logs(invoice.id)
        for log in logs:
            if log.user_id == actor_user_id and log.type == "approval":
                status_name = log.status_name
                break

        if status_name == "approved":
            message = f"{actor_fio} согласовал счёт {desc}"
            title = "Счёт согласован"
            notif_type = "invoice_approved"
        elif status_name == "rejected":
            message = f"{actor_fio} отклонил счёт {desc}"
            title = "Счёт отклонён"
            notif_type = "invoice_rejected"
        else:
            return

        if request_name:
            message += f" по заявке \"{request_name}\""

        from app.services.notification_feed_service import push_notification

        for uid in participant_ids:
            self._send_vk_notification(uid, message)
            self._send_push_notification(uid, title, message)
            push_notification(self.repo.db, uid, notif_type,
                              title=title,
                              body=message,
                              object_type="invoice", object_id=str(invoice.id),
                              related_user_id=actor_user_id)

    def _get_user_fio(self, user_id: str) -> str:
        if not self.auth_user_repo or not user_id:
            return user_id
        users = self._get_users_map([user_id])
        user = self._map_user(users.get(user_id))
        return user["short_fio"] if user else user_id

    def _send_vk_notification(self, user_id: str, message: str) -> None:
        print(f"[INVOICE][VK] _send_vk_notification user_id={user_id} message='{message[:60]}...'")
        try:
            from app.repositories.vk_repository import VkRepository
            from app.services.vk_service import VkService
            vk_repo = VkRepository(self.repo.db)
            service = VkService(vk_repo)
            vk_id = service.get_vk_id(user_id)
            print(f"[INVOICE][VK] vk_id for user {user_id} = {vk_id}")
            if vk_id:
                service.send_notification(vk_id, message)
        except Exception as e:
            print(f"[INVOICE][VK] exception: {e}")

    def _send_push_notification(self, user_id: str, title: str, body: str) -> None:
        print(f"[INVOICE][PUSH] _send_push_notification user_id={user_id} title='{title}' body='{body}'")
        try:
            from app.repositories.push_subscription_repository import PushSubscriptionRepository
            from app.services.push_service import PushService
            repo = PushSubscriptionRepository(self.repo.db)
            service = PushService(repo)
            sent = service.send_notification(user_id, title, body)
            print(f"[INVOICE][PUSH] result: sent={sent}")
        except Exception as e:
            print(f"[INVOICE][PUSH] exception: {e}")

    def update_invoice_payment(self, invoice_id: int, payment_id: str, payload: InvoicePaymentUpdate, user_id: str | None = None):
        row = self.repo.get_invoice_payment_by_id(invoice_id, payment_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice payment not found")

        was_planned = row.paid is None or row.paid == 0
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_invoice_payment(row)
        users_by_id = self._get_users_map(
            [user_id for user_id in [updated.created_by, updated.paid_by] if user_id]
        )
        result = self._map_payment(updated, users_by_id)
        self._push_badge_for_invoice_users(invoice_id)

        if was_planned and updated.paid is not None and updated.paid != 0 and updated.created_by:
            invoice = self.repo.get_invoice_by_id(invoice_id)
            if invoice:
                self._notify_payment(invoice, user_id or updated.created_by, is_planned=False, payment_amount=updated.paid)

        return result

    def delete_invoice_payment(self, invoice_id: int, payment_id: str):
        row = self.repo.get_invoice_payment_by_id(invoice_id, payment_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice payment not found")
        self.repo.delete_invoice_payment(row)
        self._push_badge_for_invoice_users(invoice_id)
        return None

    def get_invoice(self, invoice_id: int, user_id: str | None = None):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        if user_id:
            filtered = self._filter_visible([invoice], user_id)
            if not filtered:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        items = self.repo.get_invoice_items(invoice_id)
        item_mappings = self.repo.get_item_mappings_by_invoice_id(invoice_id)
        request_item_id_by_invoice_item_id: dict[str, str | None] = {}
        for mapping in item_mappings:
            invoice_item_id = str(mapping.invoice_item_id) if mapping.invoice_item_id else None
            if not invoice_item_id:
                continue
            if invoice_item_id not in request_item_id_by_invoice_item_id:
                request_item_id_by_invoice_item_id[invoice_item_id] = (
                    str(mapping.request_item_id) if mapping.request_item_id else None
                )
        unit_ids = [item.unit_id for item in items if item.unit_id]
        unit_names = self.repo.get_unit_names(unit_ids)
        request_meta = self.repo.get_requests_meta_by_ids(
            [invoice.request_id] if invoice.request_id is not None else []
        )
        object_levels_id = invoice.object_levels_id
        if not object_levels_id and invoice.request_id is not None:
            object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
        object_type = invoice.object_type
        project_name, project = self._build_project_block(object_levels_id)
        if object_type == "object" and object_levels_id and self.reference_repo:
            objects = self.reference_repo.get_objects_by_ids([object_levels_id])
            if objects:
                obj = objects[0]
                project_name = obj.short_name or obj.full_name
                project = obj

        logs = self.repo.get_invoice_logs(invoice.id)
        payments = self.repo.get_invoice_payments(invoice.id)
        extract_links = self.repo.get_extract_links_by_payment_ids([p.id for p in payments])
        log_user_ids = [log.user_id for log in logs if log.user_id]
        payment_user_ids = []
        for payment in payments:
            if payment.created_by:
                payment_user_ids.append(payment.created_by)
            if payment.paid_by:
                payment_user_ids.append(payment.paid_by)
        users_by_id = self._get_users_map(
            log_user_ids + payment_user_ids + ([invoice.created_by] if invoice.created_by else []) + ([invoice.from_by] if invoice.from_by else [])
        )

        grouped_logs = self._group_invoice_logs(logs, users_by_id)

        chat_id = self.repo.get_chat_id_by_invoice(invoice.id)

        invoice_observers = self._get_observers_by_invoice_ids([invoice.id])

        return {
            "id": invoice.id,
            "chat_id": chat_id,
            "object_levels_id": object_levels_id,
            "project_id": project.id if project else None,
            "project_name": project_name,
            "num": invoice.num,
            "date": invoice.date,
            "request_id": invoice.request_id,
            "request_name": request_meta.get(invoice.request_id, {}).get("name"),
            "file_id": invoice.file_id,
            "file": self._build_file_payload(invoice.file_id),
            "files": self.get_invoice_additional_files(invoice_id),
            "provider_id": invoice.provider_id,
            "provider": self._build_counterparty_payload(invoice.provider_id),
            "provider_name": self._build_counterparty_name(invoice.provider_id),
            "payer_id": invoice.payer_id,
            "payer": self._build_counterparty_payload(invoice.payer_id),
            "payer_name": self._build_counterparty_name(invoice.payer_id),
            **self._links_summary([invoice.id])[str(invoice.id)],
            **self._deliveries_summary([invoice.id])[str(invoice.id)],
            **self._closing_docs_mark(invoice),
            "is_delivery_included": invoice.is_delivery_included,
            "prepayment_percent": invoice.prepayment_percent,
            "due_days": invoice.due_days,
            "valid_until": invoice.valid_until,
            "is_urgent": invoice.is_urgent,
            "total_amount": invoice.total_amount,
            "vat_rate": invoice.vat_rate,
            "vat_amount": invoice.vat_amount,
            "comment": invoice.comment,
            "privacy": invoice.privacy,
            **self._requisites_block(invoice),
            "object_type": invoice.object_type,
            "from_by": invoice.from_by,
            "from_by_user": self._map_user(users_by_id.get(invoice.from_by)),
            "status": invoice.status,
            "status_name": self.repo.get_status_name(invoice.status),
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
            "created_by": invoice.created_by,
            "created_by_user": self._map_user(users_by_id.get(invoice.created_by)),
            "approvals": grouped_logs["approval"],
            "planning": grouped_logs["planning"],
            "payment": grouped_logs["payment"],
            "payments": [self._map_payment(payment, users_by_id, extract_links) for payment in payments],
            "observer": invoice_observers.get(invoice.id, []),
            "items": [
                self._item_to_dict(
                    item,
                    unit_names,
                    request_item_id=request_item_id_by_invoice_item_id.get(str(item.id)),
                )
                for item in items
            ],
        }

    @staticmethod
    def _item_to_dict(
        item,
        unit_names: dict[str, str] | None = None,
        request_item_id: str | None = None,
    ):
        unit_names = unit_names or {}
        return {
            "id": item.id,
            "invoice_item_id": item.id,
            "request_item_id": request_item_id,
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
            "type": item.type,
            "num": item.num,
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

    # warehouse_service.deliveries statuses that still count as a planned (not yet finished) delivery
    _PLANNED_DELIVERY_STATUSES = ("planned", "partially_received")

    def _deliveries_summary(self, invoice_ids: list) -> dict[str, dict]:
        """Deliveries of invoices from the warehouse service DB (deliveries.supply_invoice_id = invoice.id)."""
        from sqlalchemy import bindparam, text
        result = {str(i): [] for i in invoice_ids}
        if invoice_ids:
            from app.database import tenant_engine
            schema = tenant_engine("warehouse")
            if not schema:
                raise ValueError("WAREHOUSE_DB_NAME must be configured")
            query = text(
                "select id, number, status, supply_invoice_id, pickup_planned_date, delivery_planned_date, "
                f"warehouse_id, carrier_counterparty_id from `{schema}`.deliveries "
                "where supply_invoice_id in :ids order by created_at, id"
            ).bindparams(bindparam("ids", expanding=True))
            for r in self.repo.db.execute(query, {"ids": [int(i) for i in invoice_ids]}).mappings():
                result[str(r["supply_invoice_id"])].append({
                    "id": r["id"], "number": r["number"], "status": r["status"],
                    "is_planned": r["status"] in self._PLANNED_DELIVERY_STATUSES,
                    "pickup_planned_date": r["pickup_planned_date"], "delivery_planned_date": r["delivery_planned_date"],
                    "warehouse_id": r["warehouse_id"], "carrier_counterparty_id": r["carrier_counterparty_id"],
                })
        return {
            k: {
                "has_delivery": bool(v), "deliveries_count": len(v),
                "has_planned_delivery": any(x["is_planned"] for x in v), "deliveries": v,
            }
            for k, v in result.items()
        }

    @staticmethod
    def _closing_docs_mark(invoice) -> dict:
        return {
            "closing_docs_not_required": bool(invoice.closing_docs_not_required),
            "closing_docs_not_required_at": invoice.closing_docs_not_required_at,
            "closing_docs_not_required_by": invoice.closing_docs_not_required_by,
            "delivery_not_required": bool(invoice.delivery_not_required),
            "delivery_not_required_at": invoice.delivery_not_required_at,
            "delivery_not_required_by": invoice.delivery_not_required_by,
        }

    def _links_summary(self, invoice_ids: list) -> dict[str, dict]:
        """has_act/has_upd/counts plus the linked acts and УПД themselves (only invoices that have links are resolved)."""
        from app.repositories.documents_link_repository import DocumentsLinkRepository
        from app.services.documents_link_service import DocumentsLinkService
        repo = DocumentsLinkRepository(self.repo.db)
        counts = repo.counts_for_documents("invoice", invoice_ids, ["act", "upd"])
        service = DocumentsLinkService(repo)
        result = {}
        for i in invoice_ids:
            c = counts.get(str(i), {})
            acts, upds = [], []
            if c:
                for item in service.get_for_document("invoice", str(i))["items"]:
                    if item["document_type"] not in ("act", "upd"):
                        continue
                    entry = {"link_id": item["link_id"], "document_id": item["document_id"], "display_name": item["display_name"], "document": item["document"]}
                    (acts if item["document_type"] == "act" else upds).append(entry)
            result[str(i)] = {
                "has_act": c.get("act", 0) > 0, "has_upd": c.get("upd", 0) > 0,
                "acts_count": c.get("act", 0), "upd_count": c.get("upd", 0),
                "linked_acts": acts, "linked_upds": upds,
            }
        return result

    def _serialize_invoice_list(self, invoices):
        if not invoices:
            return []

        request_ids = [invoice.request_id for invoice in invoices if invoice.request_id is not None]
        request_meta = self.repo.get_requests_meta_by_ids(request_ids)

        counterparty_ids = set()
        user_ids = set()
        object_level_ids = []
        invoice_ids = []
        for invoice in invoices:
            invoice_ids.append(invoice.id)
            if invoice.provider_id:
                counterparty_ids.add(invoice.provider_id)
            if invoice.payer_id:
                counterparty_ids.add(invoice.payer_id)
            if invoice.created_by:
                user_ids.add(invoice.created_by)
            if invoice.from_by:
                user_ids.add(invoice.from_by)
            object_levels_id = invoice.object_levels_id
            if not object_levels_id and invoice.request_id is not None:
                object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
            if object_levels_id:
                object_level_ids.append(object_levels_id)

        links_summary = self._links_summary(invoice_ids)
        deliveries_summary = self._deliveries_summary(invoice_ids)
        logs = self.repo.get_invoice_logs_by_invoice_ids(invoice_ids)
        logs_by_invoice_id = defaultdict(list)
        for log in logs:
            logs_by_invoice_id[log.invoice_id].append(log)
            if log.user_id:
                user_ids.add(log.user_id)

        payments = self.repo.get_invoice_payments_by_invoice_ids(invoice_ids)
        extract_links = self.repo.get_extract_links_by_payment_ids([p.id for p in payments])
        payments_by_invoice_id = defaultdict(list)
        for payment in payments:
            payments_by_invoice_id[payment.invoice_id].append(payment)
            if payment.created_by:
                user_ids.add(payment.created_by)
            if payment.paid_by:
                user_ids.add(payment.paid_by)

        items_by_invoice_id = self.repo.get_invoice_items_by_invoice_ids(invoice_ids)
        unit_ids = set()
        for items in items_by_invoice_id.values():
            for item in items:
                if item.unit_id:
                    unit_ids.add(item.unit_id)
        unit_names = self.repo.get_unit_names(list(unit_ids))

        counterparty_names = self.reference_repo.get_counterparty_names(list(counterparty_ids)) if self.reference_repo else {}
        counterparty_logos = self.reference_repo.get_counterparty_logos(list(counterparty_ids)) if self.reference_repo else {}
        users_by_id = self._get_users_map(list(user_ids))

        levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(
            self.reference_repo,
            object_level_ids,
        ) if self.reference_repo else ({}, {}, {}, {})

        chat_ids_map = self.repo.get_chat_ids_by_invoice(invoice_ids)

        observers_by_invoice_id = self._get_observers_by_invoice_ids(invoice_ids)

        # Fetch additional files for all invoices
        all_invoice_files = self.repo.get_invoice_files_by_invoice_ids(invoice_ids) if self.repo else []
        files_by_invoice_id: dict[int, list] = defaultdict(list)
        file_ids = set()
        for f in all_invoice_files:
            files_by_invoice_id[f.invoice_id].append(f)
            file_ids.add(f.file_id)

        # Pre-fetch file metadata
        file_meta_by_id: dict[str, object] = {}
        if self.file_repo and file_ids:
            for file_row in self.file_repo.get_files_by_ids(list(file_ids)):
                file_meta_by_id[file_row.id] = file_row
                if file_row.uploaded_by:
                    user_ids.add(file_row.uploaded_by)

        object_type_ids = {
            invoice.object_levels_id for invoice in invoices
            if invoice.object_type == "object" and invoice.object_levels_id
        }
        object_names = {}
        if object_type_ids and self.reference_repo:
            for obj in self.reference_repo.get_objects_by_ids(list(object_type_ids)):
                object_names[obj.id] = obj.short_name or obj.full_name

        result = []
        for invoice in invoices:
            object_levels_id = invoice.object_levels_id
            if not object_levels_id and invoice.request_id is not None:
                object_levels_id = request_meta.get(invoice.request_id, {}).get("object_levels_id")
            if invoice.object_type == "object":
                project_name = object_names.get(object_levels_id)
            else:
                project_name = build_project_name(
                    object_levels_id,
                    levels_by_id,
                    objects_by_id,
                    contracts_by_id,
                    work_types_by_id,
                ) if self.reference_repo else None
            grouped_logs = self._group_invoice_logs(logs_by_invoice_id.get(invoice.id, []), users_by_id)
            result.append(
                {
                    "id": invoice.id,
                    "object_levels_id": object_levels_id,
                    "project_name": project_name,
                    "num": invoice.num,
                    "date": invoice.date,
                    "request_id": invoice.request_id,
                    "request_name": request_meta.get(invoice.request_id, {}).get("name"),
                    "provider_id": invoice.provider_id,
                    "provider_name": counterparty_names.get(invoice.provider_id),
                    "provider_logo_url": counterparty_logos.get(invoice.provider_id),
                    "payer_id": invoice.payer_id,
                    "payer_name": counterparty_names.get(invoice.payer_id),
                    "payer_logo_url": counterparty_logos.get(invoice.payer_id),
                    "chat_id": chat_ids_map.get(invoice.id),
                    **links_summary[str(invoice.id)],
                    **deliveries_summary[str(invoice.id)],
                    **self._closing_docs_mark(invoice),
                    "object_type": invoice.object_type,
                    "from_by": invoice.from_by,
                    "from_by_user": self._map_user(users_by_id.get(invoice.from_by)),
                    "status": invoice.status,
                    "status_name": self.repo.get_status_name(invoice.status),
                    "is_delivery_included": invoice.is_delivery_included,
                    "prepayment_percent": invoice.prepayment_percent,
                    "due_days": invoice.due_days,
                    "valid_until": invoice.valid_until,
                    "is_urgent": invoice.is_urgent,
                    "total_amount": invoice.total_amount,
                    "vat_rate": invoice.vat_rate,
                    "vat_amount": invoice.vat_amount,
                    "comment": invoice.comment,
                    "privacy": invoice.privacy,
                    **self._requisites_block(invoice),
                    "created_at": invoice.created_at,
                    "created_by": invoice.created_by,
                    "created_by_user": self._map_user(users_by_id.get(invoice.created_by)),
                    "approvals": grouped_logs["approval"],
                    "planning": grouped_logs["planning"],
                    "payment": grouped_logs["payment"],
                    "payments": [
                        self._map_payment(payment, users_by_id, extract_links)
                        for payment in payments_by_invoice_id.get(invoice.id, [])
                    ],
                    "items_count": len(items_by_invoice_id.get(invoice.id, [])),
                    "observer": observers_by_invoice_id.get(invoice.id, []),
                    "items": [
                        self._item_to_dict(item, unit_names)
                        for item in items_by_invoice_id.get(invoice.id, [])
                    ],
                    "files": [
                        {
                            "id": f.id,
                            "invoice_id": f.invoice_id,
                            "file_id": f.file_id,
                            "original_name": (file_meta_by_id[f.file_id].original_name if f.file_id in file_meta_by_id else None),
                            "extension": (file_meta_by_id[f.file_id].extension if f.file_id in file_meta_by_id else None),
                            "mime_type": (file_meta_by_id[f.file_id].mime_type if f.file_id in file_meta_by_id else None),
                            "file_size": (file_meta_by_id[f.file_id].file_size if f.file_id in file_meta_by_id else None),
                            "uploaded_by": (file_meta_by_id[f.file_id].uploaded_by if f.file_id in file_meta_by_id else None),
                            "uploaded_at": (file_meta_by_id[f.file_id].uploaded_at if f.file_id in file_meta_by_id else None),
                        }
                        for f in files_by_invoice_id.get(invoice.id, [])
                    ],
                }
            )
        return result

    def _build_project_block(self, object_levels_id: str | None):
        if not self.reference_repo or not object_levels_id:
            return None, None

        levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(
            self.reference_repo,
            [object_levels_id],
        )
        project_name = build_project_name(
            object_levels_id,
            levels_by_id,
            objects_by_id,
            contracts_by_id,
            work_types_by_id,
        )
        level = levels_by_id.get(object_levels_id)
        project = objects_by_id.get(level.object_id) if level else None
        return project_name, project

    @staticmethod
    def _recognised_requisites(parsed: dict) -> dict:
        """Recipient requisites from the model's JSON; anything that doesn't look valid becomes null."""
        found = {field: clean_requisite(field, parsed.get(field), strict=False) for field in REQUISITE_FIELDS}
        # the model often swaps Р/С and К/С (both are just "Сч. №" on a payment order): put them right
        found["recipient_account"], found["recipient_corr_account"] = fix_account_roles(
            found["recipient_account"], found["recipient_corr_account"], found["recipient_bik"]
        )
        return found

    @staticmethod
    def _requisites_block(invoice) -> dict:
        """Recipient requisites as they appear in every invoice response."""
        return {field: getattr(invoice, field, None) for field in REQUISITE_FIELDS}

    def _group_invoice_logs(self, logs, users_by_id: dict[str, object]):
        grouped = defaultdict(list)
        for log in logs:
            log_type = (log.type or "").lower()
            if log_type == "planing":
                log_type = "planning"
            if log_type not in {"approval", "planning", "payment"}:
                continue
            grouped[log_type].append(
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "user": self._map_user(users_by_id.get(log.user_id)),
                    "status_name": log.status_name,
                    "date_response": log.date_response,
                    "answer": log.status_name,
                }
            )
        return {
            "approval": grouped["approval"],
            "planning": grouped["planning"],
            "payment": grouped["payment"],
        }

    def _build_counterparty_name(self, counterparty_id: str | None) -> str | None:
        if not counterparty_id or not self.reference_repo:
            return None
        mapping = self.reference_repo.get_counterparty_names([counterparty_id])
        return mapping.get(counterparty_id)

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        users = self.auth_user_repo.get_by_ids([user_id for user_id in user_ids if user_id])
        return {user.id: user for user in users}

    def _get_observers_by_invoice_ids(self, invoice_ids: list[int]) -> dict[int, list[dict]]:
        if not self.invoice_user_repo or not self.auth_user_repo:
            return {}
        rows = self.invoice_user_repo.get_by_invoice_ids(invoice_ids)
        user_ids = list({row.user_id for row in rows if row.user_id})
        users_by_id = self._get_users_map(user_ids)
        result: dict[int, list[dict]] = {}
        for row in rows:
            result.setdefault(row.invoice_id, []).append({
                "id": row.id,
                "user_id": row.user_id,
                "user": self._map_user(users_by_id.get(row.user_id)),
                "role": row.role,
                "created_at": row.created_at,
                "created_by": row.created_by,
            })
        return result

    def _apply_request_object_levels_fallback(self, data: dict, current_invoice=None) -> dict:
        request_id = data.get("request_id")
        if request_id is None and current_invoice is not None:
            request_id = current_invoice.request_id

        object_levels_id = data.get("object_levels_id")
        if object_levels_id is None and current_invoice is not None:
            object_levels_id = current_invoice.object_levels_id

        if object_levels_id or request_id is None:
            return data

        meta = self.repo.get_requests_meta_by_ids([request_id]).get(request_id)
        if meta and meta.get("object_levels_id"):
            data["object_levels_id"] = meta["object_levels_id"]
        return data

    def _get_supply_manager_level_ids(self, user_id: str) -> set[str]:
        if not self.project_user_role_repo:
            return set()
        # Backward compatibility for possible typo in historical data.
        role_values = [ProjectUserRoleType.SUPPLY_MANAGER.value, "Supply maneger"]
        level_ids: set[str] = set()
        for role in role_values:
            for level_id in self.project_user_role_repo.get_object_level_ids_by_user_and_role(user_id, role):
                if level_id:
                    level_ids.add(level_id)
        return level_ids

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

    def _map_payment(self, payment, users_by_id: dict[str, object], extract_links: dict[str, list[dict]] | None = None):
        # Lists pass a pre-built batch map; single-payment callers (create/update) get a lookup here
        # so `has_extract` is always truthful, never a silent default.
        if extract_links is None:
            extract_links = self.repo.get_extract_links_by_payment_ids([payment.id])
        extracts = extract_links.get(payment.id, [])
        return {
            "id": payment.id,
            "invoice_id": payment.invoice_id,
            "value": payment.value,
            "date_plan": payment.date_plan,
            "created_by": payment.created_by,
            "created_by_user": self._map_user(users_by_id.get(payment.created_by)),
            "created_at": payment.created_at,
            "updated_at": payment.updated_at,
            "paid": payment.paid,
            "paid_type": payment.paid_type,
            "paid_by": payment.paid_by,
            "paid_by_user": self._map_user(users_by_id.get(payment.paid_by)),
            "paid_at": payment.paid_at,
            "file_id": payment.file_id,
            "priority": payment.priority,
            "has_extract": bool(extracts),
            "extracts": extracts,
        }

    @staticmethod
    def _recognize_document_text(client, document_url: str) -> str:
        return _shared_recognize_document_text(client, document_url)

    @staticmethod
    def _is_mistral_rate_limit(exc: Exception) -> bool:
        status_code = getattr(exc, "raw_response", None)
        if status_code is not None:
            status_code = getattr(status_code, "status_code", None)
        return (
            status_code == 429
            or "429" in str(exc)
            or "rate_limited" in str(exc)
            or "Rate limit" in str(exc)
        )

    @staticmethod
    def _extract_json_payload(content: str, provider: str = "Mistral") -> dict:
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{provider} returned empty response",
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
                    detail=f"Cannot parse JSON from {provider} response",
                )
            try:
                payload = json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot parse JSON from {provider} response",
                ) from exc

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unexpected JSON format from {provider}",
            )
        return payload

    def _normalize_invoice_payload(self, payload: dict) -> dict:
        items = payload.get("items")
        if not isinstance(items, list):
            items = []

        return {
            "invoice_num": self._as_str(payload.get("invoice_num")),
            "invoice_date": self._as_date(payload.get("invoice_date")),
            "vat_rate": normalize_vat_rate(
                self._as_int(payload.get("vat_rate")),
                self._as_money(payload.get("vat_amount")),
                self._as_money(payload.get("total_amount")),
            ),
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
            "num": self._as_int(item.get("num")),
            "type": self._normalize_item_type(item.get("type")),
        }

    @staticmethod
    def _normalize_item_type(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in ("product", "service", "delivery", "tax", "equipment"):
            return text
        return None

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

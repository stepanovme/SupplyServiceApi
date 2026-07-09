from __future__ import annotations
from app.database import msk_now

import html
import os
import smtplib
import uuid
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from ssl import create_default_context

from fastapi import HTTPException, status

from app.models.request_supplier import (
    RequestSupplierCreate,
    RequestSupplierLinkCreate,
    RequestSupplierLinkResponse,
    RequestSupplierLinkUpdate,
    RequestSupplierEmailSenderCreate,
    RequestSupplierEmailSenderUpdate,
    RequestSupplierFileCreate,
    RequestSupplierFileUpdate,
    RequestSupplierItemCreate,
    RequestSupplierItemUpdate,
    RequestSupplierRecipientCreate,
    RequestSupplierRecipientUpdate,
    RequestSupplierSendResponse,
    RequestSupplierTestSmtpResponse,
    RequestSupplierUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_supplier_repository import RequestSupplierRepository
from app.repositories.smtp_repository import SmtpRepository
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.project_name_builder import build_project_name, load_project_reference_maps
from app.models.smtp import decrypt_password

DEFAULT_REQUEST_SUPPLIER_STATUS_ID = "ff28c5a3-1968-11f1-aa8c-bc241127d0bd"
BASE_REQUEST_SUPPLIER_FILES_DIR = os.getenv(
    "SUPPLY_REQUEST_SUPPLIER_FILES_DIR",
    "/home/webserver/models/supply/request_supplier",
)
PUBLIC_REQUEST_SUPPLIER_LINK_BASE = os.getenv(
    "SUPPLY_PUBLIC_REQUEST_SUPPLIER_LINK_BASE",
    "https://supply.st29.ru/request-suppliers/link",
)


class RequestSupplierService:
    def __init__(
        self,
        repo: RequestSupplierRepository,
        auth_user_repo: AuthUserRepository,
        counterparty_repo: CounterpartyRepository,
        reference_repo: ReferenceObjectRepository,
        warehouse_repo: WarehouseRepository,
        smtp_repo: SmtpRepository,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.counterparty_repo = counterparty_repo
        self.reference_repo = reference_repo
        self.warehouse_repo = warehouse_repo
        self.smtp_repo = smtp_repo

    def get_all(self):
        rows = self.repo.get_all()
        return self._serialize(rows)

    def get_by_id(self, request_supplier_id: str):
        row = self.repo.get_by_id(request_supplier_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")
        return self._serialize([row])[0]

    def create(self, payload: RequestSupplierCreate, user_id: str):
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        data["created_by"] = user_id
        data.setdefault("status_id", DEFAULT_REQUEST_SUPPLIER_STATUS_ID)
        data = self._normalize_delivery_to(data)
        created = self.repo.create(data)
        return self.get_by_id(created.id)

    def update(self, request_supplier_id: str, payload: RequestSupplierUpdate):
        row = self.repo.get_by_id(request_supplier_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        data = self._normalize_delivery_to(data, current=row)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self.get_by_id(updated.id)

    def delete(self, request_supplier_id: str):
        row = self.repo.get_by_id(request_supplier_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")
        self.repo.delete(row)
        return None

    def get_items(self, request_supplier_id: str):
        self._ensure_parent_exists(request_supplier_id)
        return [self._serialize_item(row) for row in self.repo.get_items(request_supplier_id)]

    def create_item(self, request_supplier_id: str, payload: RequestSupplierItemCreate):
        self._ensure_parent_exists(request_supplier_id)
        created = self.repo.create_item(request_supplier_id, payload.model_dump(exclude_unset=True))
        return self._serialize_item(created)

    def update_item(self, request_supplier_id: str, item_id: str, payload: RequestSupplierItemUpdate):
        row = self.repo.get_item_by_id(request_supplier_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier item not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_item(row)
        return self._serialize_item(updated)

    def delete_item(self, request_supplier_id: str, item_id: str):
        row = self.repo.get_item_by_id(request_supplier_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier item not found")
        self.repo.delete_item(row)
        return None

    def get_email_senders(self, request_supplier_id: str):
        self._ensure_parent_exists(request_supplier_id)
        return [self._serialize_email_sender(row) for row in self.repo.get_email_senders(request_supplier_id)]

    def create_email_sender(self, request_supplier_id: str, payload: RequestSupplierEmailSenderCreate):
        self._ensure_parent_exists(request_supplier_id)
        created = self.repo.create_email_sender(request_supplier_id, payload.model_dump(exclude_unset=True))
        return self._serialize_email_sender(created)

    def update_email_sender(self, request_supplier_id: str, row_id: str, payload: RequestSupplierEmailSenderUpdate):
        row = self.repo.get_email_sender_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier email sender not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_email_sender(row)
        return self._serialize_email_sender(updated)

    def delete_email_sender(self, request_supplier_id: str, row_id: str):
        row = self.repo.get_email_sender_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier email sender not found")
        self.repo.delete_email_sender(row)
        return None

    def get_files(self, request_supplier_id: str):
        self._ensure_parent_exists(request_supplier_id)
        return [self._serialize_file(row) for row in self.repo.get_files(request_supplier_id)]

    def upload_file(
        self,
        request_supplier_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        user_id: str,
    ):
        self._ensure_parent_exists(request_supplier_id)
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_REQUEST_SUPPLIER_FILES_DIR, request_supplier_id)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        created = self.repo.create_file(
            request_supplier_id,
            {
                "original_name": original_name,
                "storage_name": storage_name,
                "file_path": file_path,
                "uploaded_by": user_id,
            },
        )
        return self._serialize_file(created)

    def update_file(self, request_supplier_id: str, row_id: str, payload: RequestSupplierFileUpdate):
        row = self.repo.get_file_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier file not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_file(row)
        return self._serialize_file(updated)

    def delete_file(self, request_supplier_id: str, row_id: str):
        row = self.repo.get_file_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier file not found")
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)
        return None

    def get_recipients(self, request_supplier_id: str):
        self._ensure_parent_exists(request_supplier_id)
        return [self._serialize_recipient(row) for row in self.repo.get_recipients(request_supplier_id)]

    def create_recipient(self, request_supplier_id: str, payload: RequestSupplierRecipientCreate):
        self._ensure_parent_exists(request_supplier_id)
        created = self.repo.create_recipient(request_supplier_id, payload.model_dump(exclude_unset=True))
        return self._serialize_recipient(created)

    def update_recipient(self, request_supplier_id: str, row_id: str, payload: RequestSupplierRecipientUpdate):
        row = self.repo.get_recipient_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier recipient not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_recipient(row)
        return self._serialize_recipient(updated)

    def delete_recipient(self, request_supplier_id: str, row_id: str):
        row = self.repo.get_recipient_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier recipient not found")
        self.repo.delete_recipient(row)
        return None

    def get_links(self, request_supplier_id: str):
        self._ensure_parent_exists(request_supplier_id)
        return [self._serialize_link(row) for row in self.repo.get_links(request_supplier_id)]

    def create_link(self, request_supplier_id: str, payload: RequestSupplierLinkCreate):
        self._ensure_parent_exists(request_supplier_id)
        data = payload.model_dump(exclude_unset=True)
        if not data.get("code"):
            data["code"] = self._generate_link_code()
        created = self.repo.create_link(request_supplier_id, data)
        return self._serialize_link(created)

    def update_link(self, request_supplier_id: str, row_id: str, payload: RequestSupplierLinkUpdate):
        row = self.repo.get_link_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier link not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        updated = self.repo.save_link(row)
        return self._serialize_link(updated)

    def delete_link(self, request_supplier_id: str, row_id: str):
        row = self.repo.get_link_by_id(request_supplier_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier link not found")
        self.repo.delete_link(row)
        return None

    def send(self, request_supplier_id: str, user_id: str) -> RequestSupplierSendResponse:
        row = self.repo.get_by_id(request_supplier_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")

        items = self.repo.get_items(request_supplier_id)
        senders = self.repo.get_email_senders(request_supplier_id)
        recipients = self.repo.get_recipients(request_supplier_id)
        if not senders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request supplier email senders not found",
            )
        if not recipients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request supplier recipients not found",
            )

        sender_user = self._get_user_full_name(user_id)
        sender_phone = self._get_user_phone(user_id)
        request_data = self._serialize([row])[0]
        sent_count = 0
        skipped_count = 0
        recipient_emails = [recipient.email.strip() for recipient in recipients if recipient.email and recipient.email.strip()]
        if not recipient_emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request supplier recipients have no email addresses",
            )

        for sender in senders:
            smtp = self.smtp_repo.get_by_id(sender.smtp_id)
            if not smtp:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")
            smtp_password = decrypt_password(smtp.password_hash)
            from_email = (sender.email or smtp.email or "").strip()
            if not from_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SMTP sender email is empty",
                )
            for recipient in recipients:
                if not recipient.email or not recipient.email.strip():
                    skipped_count += 1
                    continue
                link = self._ensure_link_for_recipient(request_supplier_id, recipient.id)
                subject = f"Запрос коммерческого предложения №{row.request_id}"
                body_text = self._build_request_supplier_email_body(
                    request_data,
                    items,
                    recipient,
                    sender_user,
                    sender_phone,
                    link.code if link else None,
                )
                body_html = self._build_request_supplier_email_html(
                    request_data,
                    items,
                    recipient,
                    sender_user,
                    sender_phone,
                    link.code if link else None,
                )
                self._send_email(
                    smtp_server=smtp.smtp_server,
                    port=smtp.port,
                    security=smtp.security,
                    username=smtp.email or from_email,
                    password=smtp_password,
                    from_email=from_email,
                    to_email=recipient.email.strip(),
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                )
                sent_count += 1

        row.sent_at = msk_now()
        row.sent_by = user_id
        self.repo.save(row)

        return RequestSupplierSendResponse(
            request_supplier_id=request_supplier_id,
            sender_count=len(senders),
            recipient_count=len(recipient_emails),
            sent_count=sent_count,
            skipped_count=skipped_count,
        )

    def test_smtp(self, request_supplier_id: str) -> RequestSupplierTestSmtpResponse:
        row = self.repo.get_by_id(request_supplier_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")

        senders = self.repo.get_email_senders(request_supplier_id)
        if not senders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request supplier email senders not found",
            )

        results: list[dict] = []
        success_count = 0
        failed_count = 0
        for sender in senders:
            smtp = self.smtp_repo.get_by_id(sender.smtp_id)
            if not smtp:
                failed_count += 1
                results.append(
                    {
                        "smtp_id": sender.smtp_id,
                        "email": sender.email,
                        "status": "failed",
                        "detail": "SMTP settings not found",
                    }
                )
                continue
            from_email = (sender.email or smtp.email or "").strip()
            if not from_email:
                failed_count += 1
                results.append(
                    {
                        "smtp_id": sender.smtp_id,
                        "email": sender.email,
                        "status": "failed",
                        "detail": "SMTP sender email is empty",
                    }
                )
                continue

            try:
                self._test_smtp_connection(
                    smtp_server=smtp.smtp_server,
                    port=smtp.port,
                    security=smtp.security,
                    username=smtp.email or from_email,
                    password=decrypt_password(smtp.password_hash),
                )
                success_count += 1
                results.append(
                    {
                        "smtp_id": sender.smtp_id,
                        "email": sender.email,
                        "status": "ok",
                        "detail": "Connection and authentication successful",
                    }
                )
            except HTTPException as exc:
                failed_count += 1
                results.append(
                    {
                        "smtp_id": sender.smtp_id,
                        "email": sender.email,
                        "status": "failed",
                        "detail": exc.detail,
                    }
                )

        return RequestSupplierTestSmtpResponse(
            request_supplier_id=request_supplier_id,
            sender_count=len(senders),
            success_count=success_count,
            failed_count=failed_count,
            results=results,
        )

    def _serialize(self, rows):
        if not rows:
            return []

        user_ids = [row.created_by for row in rows if row.created_by]
        user_ids.extend([row.sent_by for row in rows if row.sent_by])
        users = self.auth_user_repo.get_by_ids(list(set(user_ids)))
        users_by_id = {user.id: user for user in users}

        counterparty_ids = []
        for row in rows:
            if row.payer_id:
                counterparty_ids.append(row.payer_id)
            if row.recipient_id:
                counterparty_ids.append(row.recipient_id)
        counterparty_names = self.counterparty_repo.get_counterparty_names(counterparty_ids)

        project_level_ids = [row.project_levels_id for row in rows if row.project_levels_id]
        levels_by_id = {}
        objects_by_id = {}
        contracts_by_id = {}
        work_types_by_id = {}
        if project_level_ids:
            (
                levels_by_id,
                objects_by_id,
                contracts_by_id,
                work_types_by_id,
            ) = load_project_reference_maps(self.reference_repo, project_level_ids)

        request_names = self.repo.get_requests_by_ids([row.request_id for row in rows if row.request_id is not None])
        status_names = self.repo.get_status_names([row.status_id for row in rows if row.status_id])

        return [
            {
                "id": row.id,
                "request_id": row.request_id,
                "request_name": request_names.get(row.request_id).name if request_names.get(row.request_id) else None,
                "payer_id": row.payer_id,
                "payer_name": counterparty_names.get(row.payer_id),
                "recipient_id": row.recipient_id,
                "recipient_name": counterparty_names.get(row.recipient_id),
                "delivery_required": row.delivery_required,
                "delivery_date": row.delivery_date,
                "days_delay": row.days_delay,
                "deadline": row.deadline,
                "project_levels_id": row.project_levels_id,
                "project_name": build_project_name(
                    row.project_levels_id,
                    levels_by_id,
                    objects_by_id,
                    contracts_by_id,
                    work_types_by_id,
                ),
                "delivery_to": row.delivery_to,
                "delivery_to_type": row.delivery_to_type,
                "comment_request": row.comment_request,
                "comment_supplier": row.comment_supplier,
                "created_at": row.created_at,
                "sent_at": row.sent_at,
                "created_by": row.created_by,
                "created_by_user": self._map_user(users_by_id.get(row.created_by)),
                "sent_by": row.sent_by,
                "sent_by_user": self._map_user(users_by_id.get(row.sent_by)),
                "status_id": row.status_id,
                "status_name": status_names.get(row.status_id),
                "items": [self._serialize_item(item) for item in self.repo.get_items(row.id)],
                "email_senders": [self._serialize_email_sender(item) for item in self.repo.get_email_senders(row.id)],
                "files": [self._serialize_file(item) for item in self.repo.get_files(row.id)],
                "recipients": [self._serialize_recipient(item) for item in self.repo.get_recipients(row.id)],
                "links": [self._serialize_link(item) for item in self.repo.get_links(row.id)],
            }
            for row in rows
        ]

    def _serialize_item(self, row):
        return {
            "id": row.id,
            "request_supplier_id": row.request_supplier_id,
            "name": row.name,
            "unit_name": row.unit_name,
            "quantity": row.quantity,
            "comment": row.comment,
        }

    @staticmethod
    def _serialize_email_sender(row):
        return {
            "id": row.id,
            "request_supplier_id": row.request_supplier_id,
            "smtp_id": row.smtp_id,
            "email": row.email,
        }

    @staticmethod
    def _serialize_file(row):
        return {
            "id": row.id,
            "request_supplier_id": row.request_supplier_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
        }

    @staticmethod
    def _serialize_recipient(row):
        return {
            "id": row.id,
            "request_supplier_id": row.request_supplier_id,
            "email": row.email,
            "fio": row.fio,
            "company_name": row.company_name,
        }

    @staticmethod
    def _serialize_link(row):
        return {
            "id": row.id,
            "request_supplier_id": row.request_supplier_id,
            "request_supplier_recipient_id": row.request_supplier_recipient_id,
            "code": row.code,
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _build_request_supplier_email_body(self, request_data, items, recipient, sender_user, sender_phone, code) -> str:
        company = recipient.company_name or request_data.get("payer_name") or request_data.get("request_name") or ""
        delivery_required = "да" if request_data.get("delivery_required") else "нет"
        delivery_date = self._format_date(request_data.get("delivery_date"))
        payment_delay = self._format_payment_delay(request_data.get("days_delay"))
        deadline = self._format_datetime(request_data.get("deadline"))
        project_name = request_data.get("project_name") or ""
        delivery_address = self._resolve_delivery_address(request_data)
        comment_request = request_data.get("comment_request") or ""
        comment_supplier = request_data.get("comment_supplier") or ""
        link_url = self._build_request_supplier_link_url(code)
        positions = "\n".join(
            f"{index}. {item.name} — {item.quantity:g} {item.unit_name}"
            for index, item in enumerate(items, start=1)
        ) or "Нет позиций"
        fio = sender_user or ""

        return (
            f"Компания: {company}\n"
            f"Требуется доставка: {delivery_required}\n"
            f"Требуемая дата доставки: {delivery_date}\n"
            f"Требуется отсрочка платежа: {payment_delay}\n"
            f"Срок подачи предложения до: {deadline}\n"
            f"Проект: {project_name}\n"
            f"Адрес доставки: {delivery_address}\n"
            f"Комментарий к заявке: {comment_request}\n"
            f"Комментарий к поставщику: {comment_supplier}\n"
            f"Для отправки предложения нажмите ЗДЕСЬ: {link_url}\n"
            f"Позиции заявки:\n{positions}\n\n"
            f"С уважением {fio}\n"
            f"Телефон для связи: {sender_phone or '—'}"
        )

    def _build_request_supplier_email_html(self, request_data, items, recipient, sender_user, sender_phone, code) -> str:
        company = self._escape_html(recipient.company_name or request_data.get("payer_name") or request_data.get("request_name") or "—")
        request_num = self._escape_html(f"Заявка №{request_data.get('request_id') or ''}")
        project_name = self._escape_html(request_data.get("project_name") or "—")
        delivery_required = self._escape_html("Да" if request_data.get("delivery_required") else "Нет")
        delivery_date = self._escape_html(self._format_date(request_data.get("delivery_date")) or "—")
        payment_delay = self._escape_html(self._format_payment_delay(request_data.get("days_delay")) or "—")
        deadline = self._escape_html(self._format_datetime(request_data.get("deadline")) or "—")
        delivery_address = self._escape_html(self._resolve_delivery_address(request_data) or "—")
        comment_request = self._escape_html(request_data.get("comment_request") or "—")
        comment_supplier = self._escape_html(request_data.get("comment_supplier") or "—")
        fio = self._escape_html(sender_user or "")
        phone = self._escape_html(sender_phone or "—")
        link_html = f'<a href="{self._escape_html(self._build_request_supplier_link_url(code))}" style="color:#2563eb;text-decoration:underline;font-weight:700;">ЗДЕСЬ</a>'
        request_date = self._escape_html(self._format_date(request_data.get("created_at")) or "—")
        payer_name = self._escape_html(request_data.get("payer_name") or "—")
        recipient_name = self._escape_html(request_data.get("recipient_name") or "—")
        positions_rows = []
        for index, item in enumerate(items, start=1):
            positions_rows.append(
                "<tr>"
                f"<td style=\"padding:12px 10px;border-top:1px solid #e3e8f4;\">{index}</td>"
                f"<td style=\"padding:12px 10px;border-top:1px solid #e3e8f4;font-weight:600;\">{self._escape_html(item.name or '—')}</td>"
                f"<td style=\"padding:12px 10px;border-top:1px solid #e3e8f4;text-align:center;\">{self._escape_html(self._format_quantity(item.quantity))}</td>"
                f"<td style=\"padding:12px 10px;border-top:1px solid #e3e8f4;text-align:center;\">{self._escape_html(item.unit_name or '—')}</td>"
                f"<td style=\"padding:12px 10px;border-top:1px solid #e3e8f4;\">{self._escape_html(item.comment or '—')}</td>"
                "</tr>"
            )
        positions_table = "".join(positions_rows) or (
            "<tr><td colspan=\"5\" style=\"padding:18px;text-align:center;color:#6b7280;border-top:1px solid #e3e8f4;\">Нет позиций</td></tr>"
        )

        return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f3f6fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f6fb;padding:18px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="width:680px;max-width:680px;background:#ffffff;border-radius:22px;overflow:hidden;box-shadow:0 10px 30px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#2563eb 0%,#1d4ed8 100%);padding:28px 32px 26px 32px;color:#ffffff;">
              <div style="font-size:12px;letter-spacing:1.2px;text-transform:uppercase;opacity:.9;font-weight:700;">Запрос поставщику</div>
              <div style="font-size:34px;line-height:1.1;font-weight:800;margin-top:8px;">{request_num}</div>
              <div style="font-size:15px;line-height:1.5;margin-top:10px;max-width:600px;opacity:.95;">{project_name}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px 8px 32px;font-size:16px;line-height:1.6;color:#334155;">
              Уважаемые поставщики, направляем вам запрос на предоставление предложения по заявке.
            </td>
          </tr>
          <tr>
            <td style="padding:18px 32px 8px 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td valign="top" style="width:50%;padding-right:8px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #dbe4f0;border-radius:18px;">
                      <tr>
                        <td style="padding:18px 18px 14px 18px;">
                          <div style="font-size:12px;letter-spacing:.8px;text-transform:uppercase;font-weight:800;color:#64748b;margin-bottom:10px;">Реквизиты заявки</div>
                          <div style="font-size:15px;line-height:1.7;">
                            <div><strong>Дата заявки:</strong> {request_date}</div>
                            <div><strong>Плательщик:</strong> {payer_name}</div>
                            <div><strong>Грузополучатель:</strong> {recipient_name}</div>
                            <div><strong>Компания:</strong> {company}</div>
                            <div><strong>Проект:</strong> {project_name}</div>
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td valign="top" style="width:50%;padding-left:8px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #dbe4f0;border-radius:18px;">
                      <tr>
                        <td style="padding:18px 18px 14px 18px;">
                          <div style="font-size:12px;letter-spacing:.8px;text-transform:uppercase;font-weight:800;color:#64748b;margin-bottom:10px;">Условия поставки</div>
                          <div style="font-size:15px;line-height:1.7;">
                            <div><strong>Доставка требуется:</strong> {delivery_required}</div>
                            <div><strong>Требуемая дата доставки:</strong> {delivery_date}</div>
                            <div><strong>Отсрочка платежа:</strong> {payment_delay}</div>
                            <div><strong>Срок подачи предложения до:</strong> {deadline}</div>
                            <div><strong>Адрес доставки:</strong> {delivery_address}</div>
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 32px 8px 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #dbe4f0;border-radius:18px;">
                <tr>
                  <td style="padding:18px 18px 14px 18px;">
                    <div style="font-size:12px;letter-spacing:.8px;text-transform:uppercase;font-weight:800;color:#64748b;margin-bottom:10px;">Комментарий к поставщику</div>
                    <div style="font-size:15px;line-height:1.7;color:#111827;">{comment_supplier}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 8px 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #dbe4f0;border-radius:18px;">
                <tr>
                  <td style="padding:18px 18px 14px 18px;">
                    <div style="font-size:12px;letter-spacing:.8px;text-transform:uppercase;font-weight:800;color:#64748b;margin-bottom:10px;">Комментарий к заявке</div>
                    <div style="font-size:15px;line-height:1.7;color:#111827;">{comment_request}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 8px 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:18px;">
                <tr>
                  <td style="padding:18px;">
                    <div style="font-size:14px;line-height:1.7;color:#0f172a;">
                      Для отправки предложения нажмите {link_html}.
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 32px 0 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #dbe4f0;border-radius:18px;overflow:hidden;">
                <tr>
                  <td style="padding:18px 18px 10px 18px;">
                    <div style="font-size:20px;font-weight:800;color:#0f172a;">Позиции заявки</div>
                    <div style="font-size:13px;color:#64748b;margin-top:4px;">Список позиций, отправленных поставщику</div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 0 8px 0;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
                      <thead>
                        <tr style="background:#f8fafc;color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:.8px;">
                          <th align="left" style="padding:12px 10px;border-top:1px solid #e3e8f4;">№</th>
                          <th align="left" style="padding:12px 10px;border-top:1px solid #e3e8f4;">Наименование</th>
                          <th align="center" style="padding:12px 10px;border-top:1px solid #e3e8f4;">Кол-во</th>
                          <th align="center" style="padding:12px 10px;border-top:1px solid #e3e8f4;">Ед. изм.</th>
                          <th align="left" style="padding:12px 10px;border-top:1px solid #e3e8f4;">Комментарий</th>
                        </tr>
                      </thead>
                      <tbody>
                        {positions_table}
                      </tbody>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px 30px 32px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding-top:10px;border-top:1px solid #e5e7eb;font-size:13px;line-height:1.7;color:#475569;">
                    С уважением {fio}
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:8px;font-size:12px;line-height:1.6;color:#64748b;">
                    Телефон для связи: {phone}
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:14px;font-size:12px;line-height:1.6;color:#94a3b8;">
                    Письмо сформировано автоматически системой Supply.
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    def _resolve_delivery_address(self, request_data) -> str:
        delivery_to = request_data.get("delivery_to")
        delivery_to_type = request_data.get("delivery_to_type")
        if not delivery_to:
            return ""
        if delivery_to_type == "project":
            project_level_id = request_data.get("project_levels_id") or str(delivery_to)
            if project_level_id:
                levels = self.reference_repo.get_levels_tree([project_level_id])
                level = levels.get(project_level_id)
                if level and level.object_id:
                    objects = self.reference_repo.get_objects_by_ids([level.object_id])
                    if objects:
                        address = objects[0].address or ""
                        if address:
                            return address
            return request_data.get("project_name") or str(delivery_to)
        if delivery_to_type == "warehouse":
            warehouse = self.warehouse_repo.get_by_id(str(delivery_to))
            return warehouse.name if warehouse else str(delivery_to)
        return str(delivery_to)

    @staticmethod
    def _format_date(value) -> str:
        if not value:
            return ""
        return value.strftime("%d.%m.%Y")

    @staticmethod
    def _format_datetime(value) -> str:
        if not value:
            return ""
        return value.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _format_payment_delay(days_delay) -> str:
        if days_delay in (None, "", 0):
            return "нет"
        return f"да ({days_delay} дн.)"

    def _build_html_email(self, body_text: str) -> str:
        lines = [html.escape(line) for line in body_text.split("\n")]
        return "<html><body style=\"font-family:Arial,sans-serif;white-space:pre-wrap;\">" + "<br>".join(lines) + "</body></html>"

    @staticmethod
    def _escape_html(value: str) -> str:
        return html.escape(value or "")

    @staticmethod
    def _format_quantity(value) -> str:
        if value is None:
            return "—"
        try:
            number = float(value)
        except Exception:
            return str(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:g}"

    def _send_email(
        self,
        smtp_server: str | None,
        port: int,
        security: str,
        username: str,
        password: str,
        from_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
    ) -> None:
        if not smtp_server:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP server is empty")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_email
        message["To"] = to_email
        message.set_content(body_text)
        message.add_alternative(body_html, subtype="html")

        context = create_default_context()
        try:
            if security == "ssl":
                with smtplib.SMTP_SSL(smtp_server, port, context=context, timeout=30) as client:
                    client.login(username, password)
                    client.send_message(message)
            else:
                with smtplib.SMTP(smtp_server, port, timeout=30) as client:
                    client.ehlo()
                    if security == "tls":
                        client.starttls(context=context)
                        client.ehlo()
                    client.login(username, password)
                    client.send_message(message)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send email to {to_email}: {exc}",
            ) from exc

    def _test_smtp_connection(
        self,
        smtp_server: str | None,
        port: int,
        security: str,
        username: str,
        password: str,
    ) -> None:
        if not smtp_server:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP server is empty")

        context = create_default_context()
        try:
            if security == "ssl":
                with smtplib.SMTP_SSL(smtp_server, port, context=context, timeout=30) as client:
                    client.login(username, password)
                    code, message = client.noop()
            else:
                with smtplib.SMTP(smtp_server, port, timeout=30) as client:
                    client.ehlo()
                    if security == "tls":
                        client.starttls(context=context)
                        client.ehlo()
                    client.login(username, password)
                    code, message = client.noop()
            if code and int(code) >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SMTP server returned error: {code} {message}",
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SMTP connection test failed: {exc}",
            ) from exc

    def _get_user_full_name(self, user_id: str) -> str:
        users = self.auth_user_repo.get_by_ids([user_id])
        if not users:
            return ""
        user = users[0]
        parts = [user.surname, user.name, user.patronymic]
        return " ".join(part for part in parts if part)

    def _get_user_phone(self, user_id: str) -> str:
        user = self.auth_user_repo.get_contact_by_id(user_id)
        if not user:
            return ""
        return getattr(user, "phone", "") or ""

    def _build_request_supplier_link_url(self, code: str | None) -> str:
        if not code:
            return PUBLIC_REQUEST_SUPPLIER_LINK_BASE.rstrip("/") + "/"
        return f"{PUBLIC_REQUEST_SUPPLIER_LINK_BASE.rstrip('/')}/{code}"

    def _ensure_link_for_recipient(self, request_supplier_id: str, request_supplier_recipient_id: str):
        link = self.repo.get_link_by_recipient_id(request_supplier_id, request_supplier_recipient_id, active_only=True)
        if link:
            return link
        return self.repo.create_link(
            request_supplier_id,
            {
                "request_supplier_recipient_id": request_supplier_recipient_id,
                "code": self._generate_link_code(),
                "status": "active",
            },
        )

    @staticmethod
    def _generate_link_code() -> str:
        return uuid.uuid4().hex[:10]

    def get_request_supplier_public_page_by_code(self, code: str) -> str:
        link = self.repo.get_link_by_code(code, active_only=True)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier link not found")

        request_supplier = self.repo.get_by_id(link.request_supplier_id)
        recipient = self.repo.get_recipient_by_id(link.request_supplier_id, link.request_supplier_recipient_id)
        if not request_supplier or not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier data not found")

        request_data = self._serialize([request_supplier])[0]
        items = self.repo.get_items(link.request_supplier_id)
        sender_user = self._get_user_full_name(request_supplier.sent_by or request_supplier.created_by)
        sender_phone = self._get_user_phone(request_supplier.sent_by or request_supplier.created_by)
        return self._build_request_supplier_email_html(
            request_data=request_data,
            items=items,
            recipient=recipient,
            sender_user=sender_user,
            sender_phone=sender_phone,
            code=link.code,
        )

    @staticmethod
    def _normalize_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in (
            "payer_id",
            "recipient_id",
            "project_levels_id",
            "delivery_to",
            "comment_request",
            "comment_supplier",
            "sent_by",
            "status_id",
        ):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized

    @staticmethod
    def _normalize_delivery_to(data: dict, current=None) -> dict:
        normalized = dict(data)
        delivery_to_type = normalized.get("delivery_to_type")
        delivery_to = normalized.get("delivery_to")
        project_levels_id = normalized.get("project_levels_id")

        if delivery_to_type == "project":
            if not delivery_to or (isinstance(delivery_to, str) and len(delivery_to) > 36):
                normalized["delivery_to"] = project_levels_id or (current.project_levels_id if current else None)
        elif delivery_to_type == "warehouse":
            if not delivery_to or (isinstance(delivery_to, str) and len(delivery_to) > 36):
                normalized["delivery_to"] = delivery_to[:36] if isinstance(delivery_to, str) else delivery_to

        return normalized

    def _ensure_parent_exists(self, request_supplier_id: str) -> None:
        if not self.repo.get_by_id(request_supplier_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request supplier not found")

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

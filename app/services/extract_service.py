import json
import logging
import os
import re
import uuid
from datetime import date as dt_date
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.extract import (
    Extract,
    ExtractCreate,
    ExtractFile,
    ExtractItem,
    ExtractItemCreate,
    ExtractItemPayment,
    ExtractItemPaymentCreate,
    ExtractItemPaymentUpdate,
    ExtractItemUpdate,
    ExtractUpdate,
)
from app.models.reference_object import CounterpartyRef, DetailsIP, DetailsLLC, Person
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.extract_repository import ExtractRepository
from app.services.mistral_retry import mistral_retry, recognize_document_text

logger = logging.getLogger(__name__)

_extract_log_dir = os.getenv("EXTRACT_LOG_DIR", "/home/webserver/models/supply/logs/extracts")
try:
    os.makedirs(_extract_log_dir, exist_ok=True)
    _fh = logging.FileHandler(os.path.join(_extract_log_dir, "extract_service.log"), encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%d.%m.%Y %H:%M:%S"))
    logger.addHandler(_fh)
except Exception:
    pass

EXTRACTS_FILES_DIR = os.getenv("SUPPLY_EXTRACT_FILES_DIR", "/home/webserver/models/supply/extracts")
CHECKO_API_KEY = os.getenv("CHECKO_API_KEY", "")


class ExtractService:
    def __init__(self, repo: ExtractRepository, reference_db: Session | None = None,
                 counterparty_repo: CounterpartyRepository | None = None) -> None:
        self.repo = repo
        self.ref_db = reference_db
        self.counterparty_repo = counterparty_repo

    # --- Extracts ---

    def get_extracts(self) -> list[dict]:
        return [self._serialize_extract(r) for r in self.repo.get_extracts()]

    def get_extract(self, extract_id: int) -> dict:
        row = self.repo.get_extract_by_id(extract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract not found")
        result = self._serialize_extract(row)
        result["items"] = [self._serialize_item(i) for i in self.repo.get_items_by_extract_id(extract_id)]
        result["files"] = [self._serialize_file(f) for f in self.repo.get_files_by_extract_id(extract_id)]
        return result

    def create_extract(self, payload: ExtractCreate, user_id: str) -> dict:
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        row = self.repo.create_extract(data)
        return self._serialize_extract(row)

    def update_extract(self, extract_id: int, payload: ExtractUpdate, user_id: str) -> dict:
        row = self.repo.get_extract_by_id(extract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_extract(row)
        return self._serialize_extract(updated)

    def delete_extract(self, extract_id: int) -> None:
        row = self.repo.get_extract_by_id(extract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract not found")
        self.repo.delete_extract(row)

    # --- Items ---

    def get_items(self, extract_id: int) -> list[dict]:
        return [self._serialize_item(r) for r in self.repo.get_items_by_extract_id(extract_id)]

    def get_item(self, item_id: str) -> dict:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return self._serialize_item(row)

    def create_item(self, extract_id: int, payload: ExtractItemCreate) -> dict:
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("id", str(uuid.uuid4()))
        data["extract_id"] = extract_id
        row = self.repo.create_item(data)
        return self._serialize_item(row)

    def update_item(self, item_id: str, payload: ExtractItemUpdate) -> dict:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_item(row)
        return self._serialize_item(updated)

    def delete_item(self, item_id: str) -> None:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        self.repo.delete_item(row)

    # --- Files ---

    def upload_file(self, extract_id: int, file: UploadFile, user_id: str) -> dict:
        row = self.repo.get_extract_by_id(extract_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract not found")

        Path(EXTRACTS_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{EXTRACTS_FILES_DIR}/{storage_name}"

        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        record = self.repo.create_file({
            "id": str(uuid.uuid4()),
            "extract_id": extract_id,
            "original_name": file.filename or storage_name,
            "storage_name": storage_name,
            "extension": ext.lstrip("."),
            "mime_type": file.content_type,
            "file_path": file_path,
            "uploaded_by": user_id,
        })
        return self._serialize_file(record)

    def get_files(self, extract_id: int) -> list[dict]:
        return [self._serialize_file(r) for r in self.repo.get_files_by_extract_id(extract_id)]

    def get_file(self, file_id: str) -> ExtractFile:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return row

    def delete_file(self, file_id: str) -> None:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)

    # --- Payments ---

    def get_payments(self, item_id: str) -> list[dict]:
        return [self._serialize_payment(r) for r in self.repo.get_payments_by_item_id(item_id)]

    def create_payment(self, payload: ExtractItemPaymentCreate, user_id: str) -> dict:
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.utcnow())
        data["created_by"] = user_id
        row = self.repo.create_payment(data)
        return self._serialize_payment(row)

    def update_payment(self, payment_id: str, payload: ExtractItemPaymentUpdate) -> dict:
        row = self.repo.get_payment_by_id(payment_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_payment(row)
        return self._serialize_payment(updated)

    def delete_payment(self, payment_id: str) -> None:
        row = self.repo.get_payment_by_id(payment_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        self.repo.delete_payment(row)

    # --- Parse & Create from file ---

    def parse_and_create(self, file: UploadFile, user_id: str) -> dict:
        file_name = file.filename or "extract.pdf"
        logger.info("Starting parse_and_create for file=%s user_id=%s", file_name, user_id)

        file_bytes = file.file.read()
        logger.info("File read: name=%s size=%d bytes", file_name, len(file_bytes))

        parsed = self._ocr_extract(file_bytes, file_name)
        logger.info("OCR completed: account_number=%s items_count=%d",
                     parsed.get("account_number"),
                     len(parsed.get("items") or []))

        extract_data = self._normalize_extract_payload(parsed)
        valid_items_count = len(extract_data.get("items", []))
        logger.info("Normalized payload: account_number=%s items_count=%d",
                     extract_data.get("account_number"), valid_items_count)

        items_data = extract_data.pop("items", [])
        resolved_items = self._resolve_item_counterparties(items_data)
        logger.info("Counterparties resolved: %d items processed", len(resolved_items))

        extract_payload = {k: v for k, v in extract_data.items() if v is not None}
        extract_payload["created_by"] = user_id
        extract_row = self.repo.create_extract(extract_payload)
        logger.info("Extract created: id=%d", extract_row.id)

        created_items = []
        for i, item in enumerate(resolved_items):
            item_payload = {k: v for k, v in item.items() if v is not None}
            item_payload.setdefault("id", str(uuid.uuid4()))
            item_payload["extract_id"] = extract_row.id
            try:
                created = self.repo.create_item(item_payload)
                created_items.append(created)
            except Exception as e:
                logger.error("Failed to create extract_item #%d: %s", i, e)
                raise

        file_record = self._save_file(file, file_bytes, extract_row.id, user_id)
        logger.info("File saved: file_id=%s original_name=%s", file_record.id, file_record.original_name)

        logger.info("Parse-and-create complete: extract_id=%d items_created=%d",
                     extract_row.id, len(created_items))

        result = self._serialize_extract(extract_row)
        result["items"] = [self._serialize_item(i) for i in created_items]
        result["files"] = [self._serialize_file(file_record)]
        return result

    def ai_parse_items(self, items: list[ExtractItem]) -> list[dict]:
        return self._enrich_parsed(items, self._ai_parse_items(items), lookup=False)

    def parse_items_with_lookup(self, items: list[ExtractItem], user_id: str,
                                 invoice_repo=None, outgoing_repo=None,
                                 contract_repo=None, doc_link_repo=None) -> list[dict]:
        parsed = self._ai_parse_items(items)
        return self._enrich_parsed(items, parsed, lookup=True, user_id=user_id,
                                    invoice_repo=invoice_repo, outgoing_repo=outgoing_repo,
                                    contract_repo=contract_repo, doc_link_repo=doc_link_repo)

    def _enrich_parsed(self, items: list[ExtractItem], parsed: list[dict],
                       lookup: bool = False, user_id: str | None = None,
                       invoice_repo=None, outgoing_repo=None,
                       contract_repo=None, doc_link_repo=None) -> list[dict]:
        result = []
        for item, p in zip(items, parsed):
            entry = {
                "extract_item_id": item.id,
                "date": item.date,
                "payment_purpose": item.payment_purpose,
                "debit": item.debit,
                "credit": item.credit,
                "debet_counterparties_id": item.debet_counterparties_id,
                "credit_counterparties_id": item.credit_counterparties_id,
                "debet_counterparty": self._get_counterparty_name(item.debet_counterparties_id),
                "credit_counterparty": self._get_counterparty_name(item.credit_counterparties_id),
                **p,
            }
            if lookup:
                entry["db_match"] = self._db_lookup(item, p, invoice_repo, outgoing_repo, user_id,
                                                     contract_repo=contract_repo, doc_link_repo=doc_link_repo)
            result.append(entry)
        return result

    def _db_lookup(self, item: ExtractItem, parsed: dict, invoice_repo, outgoing_repo,
                   user_id: str | None = None,
                   contract_repo=None, doc_link_repo=None) -> dict:
        ptype = parsed.get("payment_type")
        inv_num = parsed.get("invoice_num")
        inv_date = parsed.get("invoice_date")
        contract_num = parsed.get("contract_num")
        contract_date = parsed.get("contract_date")

        if ptype != "invoice":
            return {"found": False, "reason": "not an invoice payment"}

        if not inv_num:
            inv_num = self._extract_any_number(item.payment_purpose or "")

        if not inv_num:
            return {"found": False, "reason": "no invoice/order number found"}

        if item.debit and item.debit > 0:
            provider_id = item.credit_counterparties_id
            if not provider_id:
                return {"found": False, "reason": "missing credit_counterparties_id"}
            invoices = self._find_invoices_by_provider(invoice_repo, inv_num, provider_id, inv_date)
            if invoices:
                inv = invoices[0]
                amount = item.debit
                payments = invoice_repo.get_invoice_payments(inv.id)

                payment = next((p for p in payments if p.value is not None and abs(float(p.value) - float(amount)) < 0.01), None)
                created_payment = False
                if not payment:
                    logger.info("Creating invoice_payment for invoice %s amount=%s", inv.id, amount)
                    payment = invoice_repo.create_invoice_payment(inv.id, {
                        "value": amount,
                        "paid": amount,
                        "paid_by": user_id,
                        "paid_at": datetime.combine(item.date, datetime.min.time()) if item.date else datetime.utcnow(),
                        "date_plan": item.date,
                        "created_by": user_id or "",
                    })
                    created_payment = True
                else:
                    logger.info("Found existing payment %s for invoice %s", payment.id, inv.id)

                existing_link = self.repo.get_payment_by_item_and_source(item.id, str(payment.id), "payment")
                created_link = False
                if not existing_link:
                    self.repo.create_payment({
                        "id": str(uuid.uuid4()),
                        "extract_item_id": item.id,
                        "source_id": str(payment.id),
                        "type": "payment",
                        "created_at": datetime.utcnow(),
                        "created_by": user_id or "",
                    })
                    created_link = True
                    logger.info("Created extract_item_payments link for item %s -> payment %s", item.id, payment.id)
                else:
                    logger.info("extract_item_payments link already exists for item %s", item.id)

                return {
                    "found": True,
                    "table": "invoice",
                    "invoice_id": inv.id,
                    "num": inv.num,
                    "date": inv.date,
                    "total_amount": inv.total_amount,
                    "provider_id": inv.provider_id,
                    "payer_id": inv.payer_id,
                    "matched_payment_id": payment.id,
                    "payment_created": created_payment,
                    "link_created": created_link,
                    "payments": [
                        {"id": p.id, "value": p.value, "paid": p.paid, "paid_at": p.paid_at}
                        for p in invoice_repo.get_invoice_payments(inv.id)
                    ],
                }
            return {"found": False, "reason": "invoice not found by num + provider_id"}

        if item.credit and item.credit > 0:
            provider_id = item.credit_counterparties_id
            payer_id = item.debet_counterparties_id
            if not provider_id or not payer_id:
                return {"found": False, "reason": "missing counterparties"}

            matched_outgoing = None
            matched_contract = None
            amount = item.credit

            if inv_num:
                logger.info("CREDIT_SEARCH: inv_num=%s provider_id=%s payer_id=%s inv_date=%s",
                            inv_num, provider_id, payer_id, inv_date)
                outgoings = self._find_outgoing_invoices(outgoing_repo, inv_num, provider_id, payer_id, inv_date)
                logger.info("CREDIT_SEARCH: found %d outgoing invoices", len(outgoings))
                if outgoings:
                    for og_i, og_tmp in enumerate(outgoings):
                        logger.info("CREDIT_SEARCH: outgoing[%d] id=%s num=%s sum=%s date=%s",
                                    og_i, og_tmp.id, og_tmp.num, og_tmp.sum, og_tmp.date)
                    og = outgoings[0]
                    if og.sum is None or float(og.sum) <= float(amount):
                        matched_outgoing = og
                        logger.info("CREDIT_SEARCH: selected outgoing id=%s sum=%s <= amount=%s",
                                    og.id, og.sum, amount)
                    else:
                        logger.info("CREDIT_SEARCH: outgoing sum=%s > amount=%s, skipping", og.sum, amount)

            if contract_num:
                contracts = self._find_contracts(contract_repo, contract_num, provider_id, payer_id, contract_date)
                if contracts:
                    matched_contract = contracts[0]

            created_link = False
            created_payment = False

            if matched_outgoing:
                existing_link = self.repo.get_payment_by_item_and_source(item.id, str(matched_outgoing.id), "invoice_outgoing")
                if not existing_link:
                    self.repo.create_payment({
                        "id": str(uuid.uuid4()),
                        "extract_item_id": item.id,
                        "source_id": str(matched_outgoing.id),
                        "type": "invoice_outgoing",
                        "created_at": datetime.utcnow(),
                        "created_by": user_id or "",
                    })
                    created_payment = True
                else:
                    logger.info("extract_item_payments link already exists for item %s -> outgoing %s",
                                item.id, matched_outgoing.id)

                if matched_contract:
                    logger.info("CREDIT_SEARCH: both outgoing and contract found. Creating documents_link.")
                    existing_doc_link = doc_link_repo.get_all(
                        document_linked_first=str(matched_contract.id),
                        document_type_first="contract",
                        document_linked_second=str(matched_outgoing.id),
                        document_type_second="invoice_outgoing",
                    ) if doc_link_repo else []
                    logger.info("CREDIT_SEARCH: existing_doc_link count=%d", len(existing_doc_link))
                    if not existing_doc_link:
                        doc_link_repo.create({
                            "document_linked_first": str(matched_contract.id),
                            "document_type_first": "contract",
                            "document_linked_second": str(matched_outgoing.id),
                            "document_type_second": "invoice_outgoing",
                            "created_by": user_id or "",
                        })
                        created_link = True
                        logger.info("DocumentsLink created: contract %s <-> outgoing %s",
                                    matched_contract.id, matched_outgoing.id)

                return {
                    "found": True,
                    "table": "invoice_outgoing",
                    "outgoing_id": matched_outgoing.id,
                    "num": matched_outgoing.num,
                    "date": matched_outgoing.date,
                    "sum": matched_outgoing.sum,
                    "provider_id": matched_outgoing.provider_id,
                    "payer_id": matched_outgoing.payer_id,
                    "contract_id": matched_contract.id if matched_contract else None,
                    "contract_num": matched_contract.num if matched_contract else None,
                    "doc_link_created": created_link,
                    "payment_created": created_payment,
                }

            if matched_contract:
                existing_link = self.repo.get_payment_by_item_and_source(item.id, str(matched_contract.id), "contract")
                if not existing_link:
                    self.repo.create_payment({
                        "id": str(uuid.uuid4()),
                        "extract_item_id": item.id,
                        "source_id": str(matched_contract.id),
                        "type": "contract",
                        "created_at": datetime.utcnow(),
                        "created_by": user_id or "",
                    })
                    created_payment = True

                return {
                    "found": True,
                    "table": "contract",
                    "contract_id": matched_contract.id,
                    "num": matched_contract.num,
                    "date": matched_contract.date,
                    "customer_id": matched_contract.customer_id,
                    "contractor_id": matched_contract.contractor_id,
                    "payment_created": created_payment,
                }

            return {"found": False, "reason": "no matching documents found"}

        return {"found": False, "reason": "no debit or credit"}

    def _find_invoices_by_provider(self, invoice_repo, num: str, provider_id: str, date) -> list:
        from app.models.invoice import Invoice
        q = invoice_repo.db.query(Invoice).filter(
            Invoice.num == num,
            Invoice.provider_id == provider_id,
        )
        if date:
            q = q.filter(Invoice.date == date)
        return q.order_by(Invoice.id.desc()).all()

    def parse_purpose_with_ai(self, purpose: str) -> dict:
        logger.info("parse_purpose_with_ai: purpose=%s", purpose[:150])
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MISTRAL_API_KEY is not set")

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="mistralai package is not installed") from exc

        prompt = (
            "Проанализируй назначение платежа (payment_purpose) из банковской выписки.\n"
            "Ответь строго в формате JSON:\n"
            "{\n"
            '  "payment_type": "invoice" | "salary" | "card" | "travel" | "alimony" | "enforcement" | "tax" | "other",\n'
            '  "payment_type_label": "Оплата по счету" | "Заработная плата" | "Покупка по карте" | "Командировочные" | "Алименты" | "Исполнительный лист" | "Налоги" | "Прочее",\n'
            '  "has_invoice": true/false,\n'
            '  "invoice_num": "24" | null,\n'
            '  "invoice_date": "2026-06-26" | null,\n'
            '  "has_contract": true/false,\n'
            '  "contract_num": "18-03-2026" | null,\n'
            '  "contract_date": "2026-03-18" | null\n'
            "}\n\n"
            "ВАЖНО: Перед ответом убедись, что выбранный тип подтверждается текстом payment_purpose.\n\n"
            "Правила классификации (по приоритету):\n"
            '1. Если есть "счёт", "счет", "счета", "invoice" ИЛИ номер после "№" — "invoice"\n'
            '2. Если есть "зарплата", "заработная плата", "аванс" (и нет "№") — "salary"\n'
            '3. Если есть "командировочные", "суточные" — "travel"\n'
            '4. Если есть слово "алименты" — "alimony"\n'
            '5. Если есть "исполнительный лист", "ФССП" — "enforcement"\n'
            '6. Если есть "налог", "сбор", "УСН", "ЕНВД" (и нет "№") — "tax"\n'
            '7. Если есть "оплата картой", "покупка по карте" — "card"\n'
            '8. Иначе — "other"\n\n'
            "Правила извлечения:\n"
            "- has_invoice: true если есть номер после '№'\n"
            "- invoice_num: любой номер после '№'\n"
            "- invoice_date: дата после 'от' рядом с номером (YYYY-MM-DD)\n"
            "- has_contract: true если есть 'договор', 'контракт'\n"
            "- contract_num: номер после '№' рядом с договором\n"
            "- contract_date: дата после 'от' рядом с договором (YYYY-MM-DD)\n"
            "- Если данных нет — null\n\n"
            f"Назначение платежа: {purpose}"
        )

        logger.info("Sending payment_purpose to Mistral: %s", purpose[:150])
        logger.debug("Full prompt:\n%s", prompt)

        client = Mistral(api_key=api_key)
        chat_response = mistral_retry(
            client.chat.complete,
            model="ministral-8b-2512",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = chat_response.choices[0].message.content
        if isinstance(raw, list):
            raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)

        logger.info("Mistral response:\n%s", raw)
        return self._extract_json_payload(raw)

    def match_items(self, extract_id: int, user_id: str,
                    invoice_repo, outgoing_repo, contract_repo, doc_link_repo) -> dict:
        logger.info("Starting match_items for extract_id=%d user_id=%s", extract_id, user_id)
        items = self.repo.get_items_by_extract_id(extract_id)
        if not items:
            logger.warning("No items found for extract_id=%d", extract_id)
            return {"matched": 0, "results": []}

        parsed_items = self._ai_parse_items(items)
        logger.info("AI parsed %d items", len(parsed_items))

        results = []
        for item, parsed in zip(items, parsed_items):
            result = self._match_single_item(item, user_id, parsed,
                                             invoice_repo, outgoing_repo, contract_repo, doc_link_repo)
            results.append(result)

        matched_count = sum(1 for r in results if r.get("status") == "matched")
        logger.info("Match complete: extract_id=%d total=%d matched=%d", extract_id, len(items), matched_count)
        return {"matched": matched_count, "results": results}

    def _ai_parse_items(self, items: list[ExtractItem]) -> list[dict]:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            logger.error("MISTRAL_API_KEY is not set, falling back to regex")
            return [self._regex_fallback(item) for item in items]

        try:
            from mistralai import Mistral
        except Exception:
            logger.error("mistralai package not installed, falling back to regex")
            return [self._regex_fallback(item) for item in items]

        items_text = ""
        for i, item in enumerate(items):
            purpose = (item.payment_purpose or "").strip()
            debet_name = self._get_counterparty_name(item.debet_counterparties_id) or ""
            credit_name = self._get_counterparty_name(item.credit_counterparties_id) or ""
            items_text += (
                f"[ITEM {i}]\n"
                f"payment_purpose: {purpose}\n"
                f"debet_counterparty: {debet_name}\n"
                f"credit_counterparty: {credit_name}\n"
                f"debit_amount: {item.debit}\n"
                f"credit_amount: {item.credit}\n"
                f"date: {item.date}\n\n"
            )

        prompt = (
            "Проанализируй назначение платежа (payment_purpose) из банковской выписки.\n"
            "Верни ТОЛЬКО JSON-массив, каждый элемент:\n"
            "{\n"
            '  "payment_type": "invoice" | "salary" | "card" | "travel" | "alimony" | "enforcement" | "tax" | "other",\n'
            '  "payment_type_label": "Оплата по счету" | "Заработная плата" | "Покупка по карте" | "Командировочные" | "Алименты" | "Исполнительный лист" | "Налоги" | "Прочее",\n'
            '  "has_invoice": true/false,\n'
            '  "invoice_num": "24" | null,\n'
            '  "invoice_date": "2026-06-26" | null,\n'
            '  "has_contract": true/false,\n'
            '  "contract_num": "18-03-2026" | null,\n'
            '  "contract_date": "2026-03-18" | null\n'
            "}\n\n"
            "ВАЖНО: Перед ответом убедись, что выбранный тип подтверждается текстом payment_purpose.\n"
            "Если в payment_purpose нет явного слова для выбранного типа — это ошибка.\n\n"
            "Правила классификации (по приоритету):\n"
            '1. Если есть "счёт", "счет", "счета", "invoice" ИЛИ номер после "№" — "invoice"\n'
            '2. Если есть "зарплата", "заработная плата", "аванс" (и нет "№") — "salary"\n'
            '3. Если есть "командировочные", "суточные" — "travel"\n'
            '4. Если есть слово "алименты" — "alimony"\n'
            '5. Если есть "исполнительный лист", "ФССП" — "enforcement"\n'
            '6. Если есть "налог", "сбор", "УСН", "ЕНВД" (и нет "№") — "tax"\n'
            '7. Если есть "оплата картой", "покупка по карте" — "card"\n'
            '8. Иначе — "other"\n\n'
            "Правила извлечения:\n"
            "- has_invoice: true если есть номер после '№'\n"
            "- invoice_num: любой номер после '№'\n"
            "- invoice_date: дата после 'от' рядом с номером (YYYY-MM-DD)\n"
            "- has_contract: true если есть 'договор', 'контракт'\n"
            "- contract_num: номер после '№' рядом с договором\n"
            "- contract_date: дата после 'от' рядом с договором (YYYY-MM-DD)\n"
            "- Если данных нет — null\n"
            "- Количество элементов строго соответствует количеству транзакций\n\n"
            "Транзакции:\n"
            f"{items_text}"
        )

        logger.info("Sending to Mistral: %d items, prompt length=%d chars", len(items), len(prompt))
        logger.debug("Mistral prompt:\n%s", prompt)

        client = Mistral(api_key=api_key)
        chat_response = mistral_retry(
            client.chat.complete,
            model="ministral-8b-2512",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = chat_response.choices[0].message.content
        if isinstance(raw, list):
            raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)

        logger.info("Mistral response length=%d chars", len(raw) if raw else 0)
        logger.info("Mistral raw response:\n%s", raw)

        try:
            parsed_list = self._extract_json_array(raw)
        except Exception as e:
            logger.error("Failed to parse Mistral response, falling back to regex: %s", e)
            return [self._regex_fallback(item) for item in items]

        while len(parsed_list) < len(items):
            parsed_list.append({
                "payment_type": None, "payment_type_label": None,
                "has_invoice": False, "invoice_num": None, "invoice_date": None,
                "has_contract": False, "contract_num": None, "contract_date": None,
            })

        return parsed_list[:len(items)]

    def _regex_fallback(self, item: ExtractItem) -> dict:
        purpose = (item.payment_purpose or "").strip()
        inv_num, inv_date = self._extract_invoice_ref(purpose)
        contract_num, contract_date = self._extract_contract_ref(purpose)
        has_inv = bool(inv_num)
        has_cont = bool(contract_num)
        ptype = "invoice" if has_inv else "other"
        return {
            "payment_type": ptype,
            "payment_type_label": "Оплата по счету" if has_inv else "Прочее",
            "has_invoice": has_inv,
            "invoice_num": inv_num,
            "invoice_date": inv_date,
            "has_contract": has_cont,
            "contract_num": contract_num,
            "contract_date": contract_date,
        }

    def _match_single_item(self, item: ExtractItem, user_id: str, parsed: dict,
                           invoice_repo, outgoing_repo, contract_repo, doc_link_repo) -> dict:
        item_id = item.id
        inv_num = parsed.get("invoice_num")
        inv_date = parsed.get("invoice_date")
        contract_num = parsed.get("contract_num")
        contract_date = parsed.get("contract_date")

        if item.debit and item.debit > 0:
            return self._match_debit(item, user_id, inv_num, inv_date, invoice_repo, contract_repo, doc_link_repo)
        elif item.credit and item.credit > 0:
            return self._match_credit(item, user_id, inv_num, inv_date, contract_num, contract_date, outgoing_repo, contract_repo, doc_link_repo)
        else:
            logger.info("Item %s has neither debit nor credit, skipping", item_id)
            return {"item_id": item_id, "status": "skipped", "reason": "no debit or credit"}

    def _match_debit(self, item: ExtractItem, user_id: str,
                     inv_num: str | None, inv_date: dt_date | None,
                     invoice_repo, contract_repo, doc_link_repo) -> dict:
        item_id = item.id
        credit_cp = item.credit_counterparties_id
        amount = item.debit

        reasons = []
        if not inv_num:
            reasons.append("invoice_num not found by AI")
        if not credit_cp:
            reasons.append("credit_counterparty_id is empty")
        if reasons:
            logger.info("Item %s debit skip: %s", item_id, "; ".join(reasons))
            return {"item_id": item_id, "status": "skipped", "reason": "; ".join(reasons)}

        logger.info("DEBIT match: looking for invoice num=%s provider_id=%s", inv_num, credit_cp)
        invoices = self._find_invoices_by_provider(invoice_repo, inv_num, credit_cp, inv_date)
        if not invoices:
            logger.info("Item %s: no invoice found", item_id)
            return {"item_id": item_id, "status": "skipped", "reason": "invoice not found"}

        invoice = invoices[0]
        if invoice.total_amount is not None and amount and amount > invoice.total_amount:
            logger.warning("Item %s: debit amount %s > invoice total %s, skipping", item_id, amount, invoice.total_amount)
            return {"item_id": item_id, "status": "skipped", "reason": "amount exceeds invoice total"}

        payments = invoice_repo.get_invoice_payments(invoice.id)
        payment = next((p for p in payments if p.value is not None and abs(p.value - amount) < 0.01), None)

        if payment:
            if payment.paid is None or payment.paid == 0:
                logger.info("Item %s: marking existing payment %s as paid", item_id, payment.id)
                payment.paid = amount
                payment.paid_by = user_id
                payment.paid_at = datetime.combine(item.date, datetime.min.time()) if item.date else datetime.utcnow()
                invoice_repo.save_invoice_payment(payment)
            else:
                logger.info("Item %s: payment %s already paid", item_id, payment.id)
        else:
            logger.info("Item %s: creating new payment for invoice %s", item_id, invoice.id)
            payment = invoice_repo.create_invoice_payment(invoice.id, {
                "value": amount,
                "paid": amount,
                "paid_by": user_id,
                "paid_at": datetime.combine(item.date, datetime.min.time()) if item.date else datetime.utcnow(),
                "date_plan": item.date,
                "created_by": user_id or "",
            })

        self.repo.create_payment({
            "id": str(uuid.uuid4()),
            "extract_item_id": item_id,
            "source_id": str(payment.id),
            "type": "invoice_payment",
            "created_at": datetime.utcnow(),
            "created_by": user_id,
        })
        logger.info("Item %s: extract_item_payment created (type=invoice_payment)", item_id)
        return {"item_id": item_id, "status": "matched", "type": "invoice_payment", "invoice_id": invoice.id}

    def _match_credit(self, item: ExtractItem, user_id: str,
                      inv_num: str | None, inv_date: dt_date | None,
                      contract_num: str | None, contract_date: dt_date | None,
                      outgoing_repo, contract_repo, doc_link_repo) -> dict:
        item_id = item.id
        credit_cp = item.credit_counterparties_id
        debit_cp = item.debet_counterparties_id
        amount = item.credit

        matched_outgoing = None
        matched_contract = None

        if inv_num and credit_cp and debit_cp:
            logger.info("CREDIT match: looking for outgoing invoice num=%s provider_id=%s payer_id=%s",
                         inv_num, credit_cp, debit_cp)
            outgoings = self._find_outgoing_invoices(outgoing_repo, inv_num, credit_cp, debit_cp, inv_date)
            if outgoings:
                matched_outgoing = outgoings[0]
                logger.info("Item %s: outgoing invoice found id=%s", item_id, matched_outgoing.id)

        if matched_outgoing:
            self.repo.create_payment({
                "id": str(uuid.uuid4()),
                "extract_item_id": item_id,
                "source_id": str(matched_outgoing.id),
                "type": "invoice_outgoing",
                "created_at": datetime.utcnow(),
                "created_by": user_id,
            })
            logger.info("Item %s: extract_item_payment created (type=invoice_outgoing)", item_id)

        if contract_num and credit_cp and debit_cp:
            logger.info("Looking for contract num=%s contractor_id=%s customer_id=%s",
                         contract_num, credit_cp, debit_cp)
            contracts = self._find_contracts(contract_repo, contract_num, credit_cp, debit_cp, contract_date)
            if contracts:
                matched_contract = contracts[0]
                logger.info("Item %s: contract found id=%s", item_id, matched_contract.id)

        if matched_outgoing and matched_contract:
            doc_link_repo.create({
                "document_linked_first": str(matched_outgoing.id),
                "document_type_first": "invoice_outgoing",
                "document_linked_second": str(matched_contract.id),
                "document_type_second": "contract",
                "created_by": user_id,
            })
            logger.info("Item %s: documents_link created between outgoing %s and contract %s",
                         item_id, matched_outgoing.id, matched_contract.id)

        if not matched_outgoing and matched_contract:
            self.repo.create_payment({
                "id": str(uuid.uuid4()),
                "extract_item_id": item_id,
                "source_id": str(matched_contract.id),
                "type": "contract",
                "created_at": datetime.utcnow(),
                "created_by": user_id,
            })
            logger.info("Item %s: extract_item_payment created (type=contract)", item_id)

        if not matched_outgoing and not matched_contract:
            logger.info("Item %s: no outgoing invoice or contract found", item_id)
            return {"item_id": item_id, "status": "skipped", "reason": "no documents matched"}

        return {
            "item_id": item_id,
            "status": "matched",
            "outgoing_id": matched_outgoing.id if matched_outgoing else None,
            "contract_id": matched_contract.id if matched_contract else None,
        }

    def _find_invoices(self, invoice_repo, num: str, from_by: str, date: dt_date | None) -> list:
        from app.models.invoice import Invoice
        q = invoice_repo.db.query(Invoice).filter(Invoice.num == num, Invoice.from_by == from_by)
        if date:
            q = q.filter(Invoice.date == date)
        return q.order_by(Invoice.id.desc()).all()

    def _find_outgoing_invoices(self, outgoing_repo, num: str, provider_id: str, payer_id: str, date: dt_date | None) -> list:
        from app.models.invoice_outgoing import InvoiceOutgoing
        q = outgoing_repo.db.query(InvoiceOutgoing).filter(
            InvoiceOutgoing.num.like(f"%{num}"),
            InvoiceOutgoing.provider_id == provider_id,
            InvoiceOutgoing.payer_id == payer_id,
        )
        if date:
            date_arg = date
            if isinstance(date_arg, str):
                try:
                    date_arg = datetime.strptime(date_arg, "%Y-%m-%d").date()
                except ValueError:
                    pass
            msg = f"_find_outgoing_invoices: date={date_arg} (type={type(date_arg).__name__}) provider={provider_id} payer={payer_id} num_like=%{num}"
            logger.info(msg)
            q = q.filter(InvoiceOutgoing.date == date_arg)
        result = q.order_by(InvoiceOutgoing.id.desc()).all()
        logger.info("_find_outgoing_invoices: query returned %d rows", len(result))
        return result

    def _find_contracts(self, contract_repo, num: str, contractor_id: str, customer_id: str, date: dt_date | None) -> list:
        from app.models.contract import Contract
        q = contract_repo.db.query(Contract).filter(
            Contract.num == num,
            Contract.contractor_id == contractor_id,
            Contract.customer_id == customer_id,
        )
        if date:
            if isinstance(date, str):
                try:
                    date = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            q = q.filter(Contract.date == date)
        return q.order_by(Contract.id.desc()).all()

    @staticmethod
    def _extract_invoice_ref(text: str) -> tuple[str | None, dt_date | None]:
        if not text:
            return None, None
        m = re.search(r"(?:счет[ау]?|счета|invoice)\s*(?:№|#|номер)\s*(\d[\d/-]*)", text, re.I)
        num = m.group(1).strip() if m else None
        date = None
        if num:
            m2 = re.search(r"(?:от\s+)(\d{2})\.(\d{2})\.(\d{2,4})", text)
            if m2:
                day, month, year = m2.group(1), m2.group(2), m2.group(3)
                year = int(year) + 2000 if len(year) == 2 else int(year)
                try:
                    date = dt_date(year, int(month), int(day))
                except Exception:
                    pass
        return num, date

    @staticmethod
    def _extract_contract_ref(text: str) -> tuple[str | None, dt_date | None]:
        if not text:
            return None, None
        m = re.search(r"(?:договор[аеу]?|контракт[аеу]?)\s*(?:подряда[^\d]*)?\s*№\s*(\S+)", text, re.I)
        num = m.group(1).strip().rstrip(".,;") if m else None
        date = None
        if num:
            matches = list(re.finditer(r"(?:от\s+)(\d{2})\.(\d{2})\.(\d{2,4})", text))
            if len(matches) >= 2:
                m2 = matches[1]
            elif matches:
                m2 = matches[0]
            else:
                m2 = None
            if m2:
                day, month, year = m2.group(1), m2.group(2), m2.group(3)
                year = int(year) + 2000 if len(year) == 2 else int(year)
                try:
                    date = dt_date(year, int(month), int(day))
                except Exception:
                    pass
        return num, date

    def _save_file(self, original: UploadFile, file_bytes: bytes, extract_id: int, user_id: str) -> ExtractFile:
        Path(EXTRACTS_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(original.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{EXTRACTS_FILES_DIR}/{storage_name}"

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return self.repo.create_file({
            "id": str(uuid.uuid4()),
            "extract_id": extract_id,
            "original_name": original.filename or storage_name,
            "storage_name": storage_name,
            "extension": ext.lstrip("."),
            "mime_type": original.content_type,
            "file_path": file_path,
            "uploaded_by": user_id,
        })

    def _ocr_extract(self, file_bytes: bytes, file_name: str) -> dict:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            logger.error("MISTRAL_API_KEY is not set")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MISTRAL_API_KEY is not set",
            )
        logger.info("MISTRAL_API_KEY found")

        try:
            from mistralai import Mistral
        except Exception as exc:
            logger.error("mistralai package is not installed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        logger.info("Uploading file=%s size=%d to Mistral OCR", file_name, len(file_bytes))
        client = Mistral(api_key=api_key)
        uploaded_file = mistral_retry(
            client.files.upload,
            file={"file_name": file_name, "content": file_bytes},
            purpose="ocr",
        )
        logger.info("File uploaded to Mistral: file_id=%s", uploaded_file.id)

        signed_url = mistral_retry(client.files.get_signed_url, file_id=uploaded_file.id)
        logger.info("Got signed URL for file_id=%s", uploaded_file.id)

        document_text = recognize_document_text(client, signed_url.url)
        logger.info("OCR text length=%d chars", len(document_text))

        prompt = (
            "Extract bank statement (выписка) data from the document.\n"
            "Return ONLY valid JSON object with keys:\n"
            "{\n"
            '  "account_number": string|null,\n'
            '  "date": "YYYY-MM-DD"|null,\n'
            '  "date_start": "YYYY-MM-DD"|null,\n'
            '  "date_end": "YYYY-MM-DD"|null,\n'
            '  "items": [\n'
            "    {\n"
            '      "date": "YYYY-MM-DD"|null,\n'
            '      "debet_inn": string|null,\n'
            '      "debet_name": string|null,\n'
            '      "credit_inn": string|null,\n'
            '      "credit_name": string|null,\n'
            '      "debit": number|null,\n'
            '      "credit": number|null,\n'
            '      "num_document": int|null,\n'
            '      "bank_name": string|null,\n'
            '      "payment_purpose": string|null\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Fields:\n"
            "- account_number: bank account number (расчётный счёт) of the statement owner\n"
            "- date: statement date (дата выписки)\n"
            "- date_start: start of statement period\n"
            "- date_end: end of statement period\n\n"
            "Items fields:\n"
            "- date: transaction date (дата проводки) in YYYY-MM-DD format\n"
            "- debet_inn: INN of the counterparty on the debit side (10 or 12 digits)\n"
            "- debet_name: name of the counterparty on the debit side\n"
            "- credit_inn: INN of the counterparty on the credit side\n"
            "- credit_name: name of the counterparty on the credit side\n"
            "- debit: debit amount (сумма дебета) - money going out\n"
            "- credit: credit amount (сумма кредита) - money coming in\n"
            "- num_document: document number (номер документа)\n"
            "- bank_name: bank name\n"
            "- payment_purpose: payment purpose (назначение платежа)\n\n"
            "Rules:\n"
            "- If a field is missing in the document, set null.\n"
            "- Numbers without spaces or currency symbols, only digits and dots.\n"
            "- INN must be exactly 10 or 12 digits, no letters.\n"
            "- Dates must be in YYYY-MM-DD format.\n\n"
            "Document:\n"
            f"{document_text[:25000]}"
        )

        logger.info("Calling Mistral chat (ministral-8b-2512) for JSON extraction")
        chat_response = mistral_retry(
            client.chat.complete,
            model="ministral-8b-2512",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_content = chat_response.choices[0].message.content
        if isinstance(raw_content, list):
            raw_content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        logger.info("Mistral chat response received, length=%d chars", len(raw_content) if raw_content else 0)
        try:
            result = self._extract_json_payload(raw_content)
            logger.info("JSON parsed successfully: keys=%s", list(result.keys()))
            return result
        except HTTPException:
            logger.error("Failed to parse Mistral response as JSON. Raw response (first 500): %s", (raw_content or "")[:500])
            raise

    def _normalize_extract_payload(self, payload: dict) -> dict:
        items = payload.get("items")
        if not isinstance(items, list):
            items = []
        return {
            "account_number": self._as_str(payload.get("account_number")),
            "date": self._as_date(payload.get("date")),
            "date_start": self._as_date(payload.get("date_start")),
            "date_end": self._as_date(payload.get("date_end")),
            "items": [
                {
                    "date": self._as_date(item.get("date")),
                    "debet_inn": self._clean_inn(item.get("debet_inn")),
                    "debet_name": self._as_str(item.get("debet_name")),
                    "credit_inn": self._clean_inn(item.get("credit_inn")),
                    "credit_name": self._as_str(item.get("credit_name")),
                    "debit": self._as_float(item.get("debit")),
                    "credit": self._as_float(item.get("credit")),
                    "num_document": self._as_int(item.get("num_document")),
                    "bank_name": self._as_str(item.get("bank_name")),
                    "payment_purpose": self._as_str(item.get("payment_purpose")),
                }
                for item in items
                if isinstance(item, dict)
            ],
        }

    def _resolve_item_counterparties(self, items: list[dict]) -> list[dict]:
        resolved = []
        for item in items:
            debit_cp_id = self._resolve_counterparty(item.get("debet_inn"), item.get("debet_name"))
            credit_cp_id = self._resolve_counterparty(item.get("credit_inn"), item.get("credit_name"))
            resolved.append({
                "debet_counterparties_id": debit_cp_id,
                "credit_counterparties_id": credit_cp_id,
                "date": item.get("date"),
                "debit": item.get("debit"),
                "credit": item.get("credit"),
                "num_document": item.get("num_document"),
                "bank_name": item.get("bank_name"),
                "payment_purpose": item.get("payment_purpose"),
            })
        return resolved

    def _resolve_counterparty(self, inn: str | None, name: str | None) -> str | None:
        if not inn:
            return None
        if not self.ref_db:
            logger.warning("reference_db not provided, skipping counterparty resolution for INN=%s", inn)
            return None
        existing = self._find_counterparty_by_inn(inn)
        if existing:
            logger.info("Counterparty found by INN=%s: id=%s", inn, existing)
            return existing
        logger.info("Counterparty not found by INN=%s, creating...", inn)
        return self._create_counterparty(inn, name)

    def _find_counterparty_by_inn(self, inn: str) -> str | None:
        logger.debug("Looking up INN=%s in reference DB", inn)
        llc = self.ref_db.query(DetailsLLC).filter(DetailsLLC.inn == inn).first()
        if llc:
            logger.debug("Found in details_llc: counterparties_id=%s", llc.counterparties_id)
            return llc.counterparties_id
        ip = self.ref_db.query(DetailsIP).filter(DetailsIP.inn == inn).first()
        if ip:
            logger.debug("Found in details_ip: counterparty_id=%s", ip.counterparty_id)
            return ip.counterparty_id
        logger.debug("INN=%s not found in reference DB", inn)
        return None

    def _create_counterparty(self, inn: str, name: str | None) -> str | None:
        logger.info("Creating counterparty for INN=%s name=%s", inn, name)
        try:
            llc_resp = httpx.get(
                "https://api.checko.ru/v2/company",
                params={"key": CHECKO_API_KEY, "inn": inn},
                timeout=30.0,
            )
            if llc_resp.status_code == 200:
                data = llc_resp.json().get("data", {})
                if data.get("ОГРН"):
                    logger.info("checko.ru returned LLC data for INN=%s", inn)
                    return self._create_llc(data, inn)
                else:
                    logger.warning("checko.ru company response missing ОГРН for INN=%s", inn)
            else:
                logger.warning("checko.ru company API returned status=%d for INN=%s", llc_resp.status_code, inn)

            logger.info("Trying checko.ru entrepreneur API for INN=%s", inn)
            ip_resp = httpx.get(
                "https://api.checko.ru/v2/entrepreneur",
                params={"key": CHECKO_API_KEY, "inn": inn},
                timeout=30.0,
            )
            if ip_resp.status_code == 200:
                data = ip_resp.json().get("data", {})
                if data.get("ОГРНИП"):
                    logger.info("checko.ru returned IP data for INN=%s", inn)
                    return self._create_ip(data, inn)
                else:
                    logger.warning("checko.ru entrepreneur response missing ОГРНИП for INN=%s", inn)
            else:
                logger.warning("checko.ru entrepreneur API returned status=%d for INN=%s", ip_resp.status_code, inn)

        except httpx.TimeoutException:
            logger.warning("checko.ru API timeout for INN=%s", inn)
        except Exception as e:
            logger.warning("checko.ru API error for INN=%s: %s", inn, e, exc_info=True)

        if name:
            logger.info("Creating minimal counterparty for INN=%s name=%s", inn, name)
            return self._create_minimal(inn, name)

        logger.warning("Cannot create counterparty for INN=%s: no name provided", inn)
        return None

    def _create_llc(self, data: dict, inn: str) -> str:
        cp_id = str(uuid.uuid4())
        short_name = (data.get("НаимСокр") or data.get("НаимПолн") or "")[:300]
        full_name = (data.get("НаимПолн") or "")[:500]
        logger.info("Creating LLC counterparty: id=%s inn=%s short_name=%s", cp_id, inn, short_name)

        ref = CounterpartyRef(id=cp_id, short_name=short_name or None, full_name=full_name or None, type="LLC", is_internal=False)
        self.ref_db.add(ref)
        self.ref_db.flush()

        person_id = None
        directors = data.get("Руковод", []) or []
        if directors:
            director = directors[0]
            fio = director.get("ФИО", "").strip()
            if fio:
                parts = fio.split(" ", 2)
                person = Person(
                    id=str(uuid.uuid4()),
                    last_naem=parts[0] if len(parts) > 0 else "",
                    name=parts[1] if len(parts) > 1 else "",
                    middle_name=parts[2] if len(parts) > 2 else "",
                )
                self.ref_db.add(person)
                self.ref_db.flush()
                person_id = person.id
                logger.debug("Created director person: id=%s fio=%s", person.id, fio)

        legal_address = data.get("ЮрАдрес", {}).get("АдресРФ") if isinstance(data.get("ЮрАдрес"), dict) else ""
        ogrn = data.get("ОГРН") or ""
        kpp = data.get("КПП") or ""

        llc = DetailsLLC(counterparties_id=cp_id, inn=inn, kpp=kpp, ogrn=ogrn, legal_address=legal_address, director_person_id=person_id)
        self.ref_db.add(llc)
        self.ref_db.commit()
        logger.info("LLC counterparty created: id=%s", cp_id)
        return cp_id

    def _create_ip(self, data: dict, inn: str) -> str:
        cp_id = str(uuid.uuid4())
        fio = (data.get("ФИО") or "").strip()
        short_name = f"ИП {fio}"[:300]
        full_name = f"{data.get('Тип', '')} {fio}"[:500]
        logger.info("Creating IP counterparty: id=%s inn=%s fio=%s", cp_id, inn, fio)

        ref = CounterpartyRef(id=cp_id, short_name=short_name, full_name=full_name, type="IP", is_internal=False)
        self.ref_db.add(ref)
        self.ref_db.flush()

        parts = fio.split(" ", 2)
        person = Person(
            id=str(uuid.uuid4()),
            last_naem=parts[0] if len(parts) > 0 else "",
            name=parts[1] if len(parts) > 1 else "",
            middle_name=parts[2] if len(parts) > 2 else "",
        )
        self.ref_db.add(person)
        self.ref_db.flush()

        ip = DetailsIP(counterparty_id=cp_id, inn=inn, ogrnip=data.get("ОГРНИП"), person_id=person.id)
        self.ref_db.add(ip)
        self.ref_db.commit()
        return cp_id

    def _create_minimal(self, inn: str, name: str) -> str:
        cp_id = str(uuid.uuid4())
        short_name = name if len(name) <= 300 else name[:300]
        ref = CounterpartyRef(id=cp_id, short_name=short_name, full_name=name, type="LLC", is_internal=False)
        self.ref_db.add(ref)
        self.ref_db.flush()
        llc = DetailsLLC(counterparties_id=cp_id, inn=inn, kpp="", ogrn="", legal_address="")
        self.ref_db.add(llc)
        self.ref_db.commit()
        return cp_id

    # --- Serialization ---

    def _serialize_extract(self, row: Extract) -> dict:
        return {
            "id": row.id,
            "account_number": row.account_number,
            "counterparties_id": row.counterparties_id,
            "date": row.date,
            "date_start": row.date_start,
            "date_end": row.date_end,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def _serialize_item(self, row: ExtractItem) -> dict:
        debet = self._get_counterparty_name(row.debet_counterparties_id)
        credit = self._get_counterparty_name(row.credit_counterparties_id)
        return {
            "id": row.id,
            "extract_id": row.extract_id,
            "debet_counterparties_id": row.debet_counterparties_id,
            "credit_counterparties_id": row.credit_counterparties_id,
            "debet_counterparty": debet,
            "credit_counterparty": credit,
            "date": row.date,
            "debit": row.debit,
            "credit": row.credit,
            "num_document": row.num_document,
            "bank_name": row.bank_name,
            "payment_purpose": row.payment_purpose,
        }

    def _get_counterparty_name(self, cp_id: str | None) -> str | None:
        if not cp_id or not self.counterparty_repo:
            return None
        brief = self.counterparty_repo.get_counterparty_brief(cp_id)
        if brief:
            return brief.get("short_name")
        return None

    def _serialize_file(self, row: ExtractFile) -> dict:
        return {
            "id": row.id,
            "extract_id": row.extract_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "mime_type": row.mime_type,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
        }

    def _serialize_payment(self, row: ExtractItemPayment) -> dict:
        return {
            "id": row.id,
            "extract_item_id": row.extract_item_id,
            "source_id": row.source_id,
            "type": row.type,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    # --- Helpers ---

    @staticmethod
    def _extract_json_array(content: str) -> list:
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mistral returned empty response")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            payload = json.loads(cleaned)
        except Exception:
            match = re.search(r"\[.*\]", cleaned, flags=re.S)
            if not match:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot parse JSON from Mistral response")
            try:
                payload = json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot parse JSON from Mistral response") from exc
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unexpected JSON format from Mistral")
        return payload

    @staticmethod
    def _extract_json_payload(content: str) -> dict:
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mistral returned empty response")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            payload = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot parse JSON from Mistral response")
            try:
                payload = json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot parse JSON from Mistral response") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unexpected JSON format from Mistral")
        return payload

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
    def _as_float(value) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ".").replace(" ", ""))
        except Exception:
            return None

    @staticmethod
    def _as_int(value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).replace(",", ".").replace(" ", "")))
        except Exception:
            return None

    @staticmethod
    def _extract_any_number(text: str) -> str | None:
        if not text:
            return None
        m = re.search(r"№\s*(\S+)", text)
        if m:
            return m.group(1).strip().rstrip(".,;")
        m = re.search(r"(?:номер|#)\s*(\S+)", text, re.I)
        if m:
            return m.group(1).strip().rstrip(".,;")
        return None

    @staticmethod
    def _clean_inn(value) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"[^\d]", "", str(value))
        if len(cleaned) in (10, 12):
            return cleaned
        return None

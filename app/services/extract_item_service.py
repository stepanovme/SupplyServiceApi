import uuid
from datetime import datetime

from fastapi import HTTPException, status

from app.models.extract_item import (
    ExtractItem,
    ExtractItemSetObjectRequest,
    ExtractItemUpdate,
    FetchSberbankStatementRequest,
    FetchTbankStatementRequest,
)
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.contract_extract_repository import ContractExtractRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.invoice_payment_extract_repository import InvoicePaymentExtractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.excel_statement_parser import parse_bank_excel
from app.services.sberbank_client import fetch_sberbank_statement
from app.services.tbank_client import fetch_tbank_statement, parse_tbank_operation


class ExtractItemService:
    def __init__(
        self,
        repo: ExtractItemRepository,
        bank_settings_repo: SettingsApiBankRepository,
        counterparty_repo: CounterpartyRepository | None = None,
        contract_extract_repo: ContractExtractRepository | None = None,
        contract_repo: ContractRepository | None = None,
        extract_business_card_repo: ExtractBusinessCardRepository | None = None,
        business_card_repo: BusinessCardRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        invoice_payment_extract_repo: InvoicePaymentExtractRepository | None = None,
    ) -> None:
        self.repo = repo
        self.bank_settings_repo = bank_settings_repo
        self.counterparty_repo = counterparty_repo
        self.contract_extract_repo = contract_extract_repo
        self.contract_repo = contract_repo
        self.extract_business_card_repo = extract_business_card_repo
        self.business_card_repo = business_card_repo
        self.reference_repo = reference_repo
        self.invoice_payment_extract_repo = invoice_payment_extract_repo

    @staticmethod
    def _serialize(
        row: ExtractItem,
        contract: dict | None = None,
        business_card: dict | None = None,
        invoice_payments: list[dict] | None = None,
        object_info: dict | None = None,
    ) -> dict:
        return {
            "id": row.id,
            "operationDate": row.operationDate,
            "amount": row.amount,
            "direction": row.direction,
            "paymentPurpose": row.paymentPurpose,
            "payeeInn": row.payeeInn,
            "payeeKpp": row.payeeKpp,
            "payeeName": row.payeeName,
            "payerInn": row.payerInn,
            "payerKpp": row.payerKpp,
            "payerName": row.payerName,
            "payeeBankName": row.payeeBankName,
            "payeeAccount": row.payeeAccount,
            "account_number": row.account_number,
            "bank_type": row.bank_type,
            "external_id": row.external_id,
            "payee_id": row.payee_id,
            "payer_id": row.payer_id,
            "created_at": row.created_at,
            "contract": contract,
            "business_card": business_card,
            # kept for older clients: the first linked payment; the full list is `invoice_payments`
            "invoice_payment": invoice_payments[0] if invoice_payments else None,
            "invoice_payments": invoice_payments or [],
            "object_id": row.object_id,
            "object": object_info,
        }

    def _build_contract_map(self, extract_ids: list[str]) -> dict[str, dict]:
        """extract_id -> {contract_extract_id, contract_id, contract_num, contract_date, contract_full_name}."""
        if not self.contract_extract_repo or not extract_ids:
            return {}

        links = self.contract_extract_repo.get_by_extract_ids(extract_ids)
        if not links:
            return {}

        contract_ids = list({link.contract_id for link in links})
        contracts_by_id = {}
        doc_type_map: dict = {}
        if self.contract_repo:
            contracts_by_id = {c.id: c for c in self.contract_repo.get_contracts_by_ids(contract_ids)}
            doc_type_map = {dt.id: dt.name for dt in self.contract_repo.get_document_types()}

        result: dict[str, dict] = {}
        for link in links:
            contract = contracts_by_id.get(link.contract_id)
            full_name = None
            if contract:
                doc_type_name = doc_type_map.get(contract.document_type_id)
                full_name = " ".join(part for part in [doc_type_name, contract.name, "№", contract.num] if part).strip()
            result[link.extract_id] = {
                "contract_extract_id": link.id,
                "contract_id": link.contract_id,
                "contract_num": contract.num if contract else None,
                "contract_date": contract.date if contract else None,
                "contract_full_name": full_name,
            }
        return result

    def _build_business_card_map(self, extract_ids: list[str]) -> dict[str, dict]:
        """extract_id -> {extract_business_card_id, business_card_id, card_number_mask, holder_name, object_id, object_short_name}."""
        if not self.extract_business_card_repo or not extract_ids:
            return {}

        links = self.extract_business_card_repo.get_by_extract_ids(extract_ids)
        if not links:
            return {}

        card_ids = list({link.business_card_id for link in links})
        cards_by_id = {}
        if self.business_card_repo:
            cards_by_id = {c.id: c for c in self.business_card_repo.get_by_ids(card_ids)}

        object_ids = list({link.object_id for link in links if link.object_id})
        object_names_by_id = {}
        if object_ids and self.reference_repo:
            object_names_by_id = {o.id: o.short_name for o in self.reference_repo.get_objects_by_ids(object_ids)}

        result: dict[str, dict] = {}
        for link in links:
            card = cards_by_id.get(link.business_card_id)
            result[link.extract_id] = {
                "extract_business_card_id": link.id,
                "business_card_id": link.business_card_id,
                "card_number_mask": card.card_number_mask if card else None,
                "holder_name": card.holder_name if card else None,
                "object_id": link.object_id,
                "object_short_name": object_names_by_id.get(link.object_id),
            }
        return result

    def _build_invoice_payment_map(self, extract_ids: list[str]) -> dict[str, list[dict]]:
        """extract_id -> links to the invoice payments this statement row paid (or was matched to).
        A row can be spread over several invoices, so it's always a list."""
        repo = self.invoice_payment_extract_repo
        if not repo or not extract_ids:
            return {}

        links = repo.get_by_extract_ids(extract_ids)
        if not links:
            return {}

        payments = {p.id: p for p in repo.get_payments_by_ids([l.invoice_payment_id for l in links])}
        invoices = {i.id: i for i in repo.get_invoices_by_ids(list({p.invoice_id for p in payments.values()}))}

        result: dict[str, list[dict]] = {}
        for link in links:
            payment = payments.get(link.invoice_payment_id)
            invoice = invoices.get(payment.invoice_id) if payment else None
            result.setdefault(link.extract_id, []).append(
                {
                    "invoice_payment_extract_id": link.id,
                    "scenario": link.scenario,
                    "amount": link.amount,
                    "invoice_payment_id": link.invoice_payment_id,
                    "invoice_id": payment.invoice_id if payment else None,
                    "invoice_num": invoice.num if invoice else None,
                    "invoice_date": invoice.date if invoice else None,
                    "paid": float(payment.paid) if payment and payment.paid is not None else None,
                }
            )
        return result

    def _build_object_map(self, rows: list[ExtractItem]) -> dict[str, dict]:
        """object_id -> {id, short_name, full_name} for the objects the rows are attached to."""
        if not self.reference_repo:
            return {}
        object_ids = list({row.object_id for row in rows if row.object_id})
        return {
            o.id: {"id": o.id, "short_name": o.short_name, "full_name": o.full_name}
            for o in self.reference_repo.get_objects_by_ids(object_ids)
        }

    def _serialize_rows(self, rows: list[ExtractItem]) -> list[dict]:
        ids = [row.id for row in rows]
        contract_map = self._build_contract_map(ids)
        business_card_map = self._build_business_card_map(ids)
        invoice_payment_map = self._build_invoice_payment_map(ids)
        object_map = self._build_object_map(rows)
        return [
            self._serialize(
                row,
                contract_map.get(row.id),
                business_card_map.get(row.id),
                invoice_payment_map.get(row.id),
                object_map.get(row.object_id) if row.object_id else None,
            )
            for row in rows
        ]

    def _resolve_counterparty_id(self, inn: str | None) -> str | None:
        if not inn or not self.counterparty_repo:
            return None
        found = self.counterparty_repo.find_by_inn(inn)
        return found.get("id") if found else None

    @staticmethod
    def _parse_operation_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_amount(amount_obj: dict | None) -> float | None:
        if not amount_obj:
            return None
        raw = amount_obj.get("amount")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _store_parsed_row(self, parsed: dict, account_number: str | None, bank_type: str | None) -> ExtractItem | None:
        """Dedup-checks and inserts one already-parsed row (same shape for every source:
        Sberbank/T-Bank API transactions and uploaded Excel statements alike). Returns
        None if a matching row already exists.

        Prefers the bank's own transaction id (`external_id`, e.g. operationId) for
        dedup when the source provides one - exact match, no false positives. Falls back
        to content-based matching (date/amount/purpose/parties) only for sources with no
        stable id (currently the Excel parsers), which is inherently heuristic: two
        genuinely different operations that happen to share every one of those fields
        (e.g. a card auth + capture pair reported as separate statement lines with
        identical description) will be treated as the same and collapsed into one.
        """
        external_id = parsed.get("external_id")

        if external_id and bank_type:
            if self.repo.find_by_external_id(bank_type, external_id):
                return None
            # Rows loaded before external_id existed have it NULL, so an exact-id lookup can't
            # see them. Match those by content and back-fill the id instead of inserting a twin.
            legacy = self.repo.find_legacy_duplicate(
                bank_type=bank_type,
                operation_date=parsed["operation_date"],
                amount=parsed["amount"],
                direction=parsed["direction"],
                payment_purpose=parsed["payment_purpose"],
                payee_inn=parsed["payee_inn"],
                payer_inn=parsed["payer_inn"],
                payee_account=parsed["payee_account"],
            )
            if legacy:
                legacy.external_id = external_id
                legacy.bank_type = legacy.bank_type or bank_type
                legacy.account_number = legacy.account_number or account_number
                self.repo.save(legacy)
                return None
        else:
            duplicate = self.repo.find_duplicate(
                operation_date=parsed["operation_date"],
                amount=parsed["amount"],
                direction=parsed["direction"],
                payment_purpose=parsed["payment_purpose"],
                payee_inn=parsed["payee_inn"],
                payer_inn=parsed["payer_inn"],
                payee_account=parsed["payee_account"],
                account_number=account_number,
            )
            if duplicate:
                return None

        row = ExtractItem(
            id=str(uuid.uuid4()),
            operationDate=parsed["operation_date"],
            amount=parsed["amount"],
            direction=parsed["direction"],
            paymentPurpose=parsed["payment_purpose"],
            payeeInn=parsed["payee_inn"],
            payeeKpp=parsed["payee_kpp"],
            payeeName=parsed["payee_name"],
            payerInn=parsed["payer_inn"],
            payerKpp=parsed["payer_kpp"],
            payerName=parsed["payer_name"],
            payeeBankName=parsed["payee_bank_name"],
            payeeAccount=parsed["payee_account"],
            account_number=account_number,
            bank_type=bank_type,
            external_id=external_id,
            payee_id=self._resolve_counterparty_id(parsed["payee_inn"]),
            payer_id=self._resolve_counterparty_id(parsed["payer_inn"]),
        )
        return self.repo.create(row)

    def _fetch_and_store_one_day(
        self,
        account_number: str,
        statement_date: str,
        api_host: str,
        api_token: str,
        pfx_path: str | None,
        pfx_passphrase: str | None,
        ca_bundle_path: str | None,
        ssl_verify: bool,
    ) -> dict:
        transactions = fetch_sberbank_statement(
            api_host=api_host,
            api_token=api_token,
            pfx_path=pfx_path,
            pfx_passphrase=pfx_passphrase,
            ca_bundle_path=ca_bundle_path,
            ssl_verify=ssl_verify,
            account_number=account_number,
            statement_date=statement_date,
        )

        created_items: list[dict] = []
        skipped_duplicates = 0

        for tx in transactions:
            rur_transfer = tx.get("rurTransfer") or {}
            parsed = {
                "operation_date": self._parse_operation_date(tx.get("operationDate")),
                "amount": self._parse_amount(tx.get("amount")),
                "direction": tx.get("direction"),
                "payment_purpose": tx.get("paymentPurpose"),
                "payee_inn": rur_transfer.get("payeeInn"),
                "payee_kpp": rur_transfer.get("payeeKpp"),
                "payee_name": rur_transfer.get("payeeName"),
                "payer_inn": rur_transfer.get("payerInn"),
                "payer_kpp": rur_transfer.get("payerKpp"),
                "payer_name": rur_transfer.get("payerName"),
                "payee_bank_name": rur_transfer.get("payeeBankName"),
                "payee_account": rur_transfer.get("payeeAccount"),
                "external_id": tx.get("operationId") or tx.get("uuid") or tx.get("hashAbc"),
            }

            created = self._store_parsed_row(parsed, account_number=account_number, bank_type="sberbank")
            if created is None:
                skipped_duplicates += 1
                continue
            created_items.append(self._serialize(created))

        return {
            "statement_date": statement_date,
            "fetched": len(transactions),
            "created": len(created_items),
            "skipped_duplicates": skipped_duplicates,
            "items": created_items,
        }

    def upload_excel_statement(self, bank_type: str, account_number: str | None, file_bytes: bytes) -> dict:
        rows, detected_account_number = parse_bank_excel(bank_type, file_bytes)
        final_account_number = account_number or detected_account_number

        created_items: list[dict] = []
        skipped_duplicates = 0

        for parsed in rows:
            created = self._store_parsed_row(parsed, account_number=final_account_number, bank_type=bank_type)
            if created is None:
                skipped_duplicates += 1
                continue
            created_items.append(self._serialize(created))

        return {
            "bank_type": bank_type,
            "account_number": final_account_number,
            "fetched": len(rows),
            "created": len(created_items),
            "skipped_duplicates": skipped_duplicates,
            "items": created_items,
        }

    def fetch_and_store_tbank_statement(self, payload: FetchTbankStatementRequest, user_id: str) -> dict:
        bank_setting = self.bank_settings_repo.get_by_id(payload.settings_api_bank_id)
        if not bank_setting:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        if bank_setting.bank_type != "tbank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Эта интеграция не относится к bank_type=tbank",
            )
        if not bank_setting.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Интеграция отключена (is_active=false)")

        config = bank_setting.config or {}
        api_token = config.get("api_token")
        api_host = config.get("api_host")
        cert_path = config.get("cert_path")
        key_path = config.get("key_path")
        ca_bundle_path = config.get("ca_bundle_path")
        ssl_verify = config.get("ssl_verify", True)
        if not api_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У интеграции не заполнен api_token")

        operations = fetch_tbank_statement(
            api_token=api_token,
            account_number=payload.account_number,
            date_from=payload.date_from,
            date_to=payload.date_to,
            api_host=api_host,
            cert_path=cert_path,
            key_path=key_path,
            ca_bundle_path=ca_bundle_path,
            ssl_verify=ssl_verify,
        )

        created_items: list[dict] = []
        skipped_duplicates = 0

        for op in operations:
            parsed = parse_tbank_operation(op)
            created = self._store_parsed_row(parsed, account_number=payload.account_number, bank_type="tbank")
            if created is None:
                skipped_duplicates += 1
                continue
            created_items.append(self._serialize(created))

        return {
            "settings_api_bank_id": payload.settings_api_bank_id,
            "account_number": payload.account_number,
            "date_from": payload.date_from,
            "date_to": payload.date_to,
            "fetched": len(operations),
            "created": len(created_items),
            "skipped_duplicates": skipped_duplicates,
            "items": created_items,
        }

    def fetch_and_store_sberbank_statement(self, payload: FetchSberbankStatementRequest, user_id: str) -> dict:
        bank_setting = self.bank_settings_repo.get_by_id(payload.settings_api_bank_id)
        if not bank_setting:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        if bank_setting.bank_type != "sberbank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Эта интеграция не относится к bank_type=sberbank",
            )
        if not bank_setting.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Интеграция отключена (is_active=false)")

        config = bank_setting.config or {}
        api_host = config.get("api_host")
        api_token = config.get("api_token")
        pfx_path = config.get("pfx_path")
        pfx_passphrase = config.get("pfx_passphrase")
        ca_bundle_path = config.get("ca_bundle_path")
        ssl_verify = config.get("ssl_verify", True)
        if not api_host or not api_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У интеграции не заполнены api_host/api_token",
            )

        dates = payload.iter_dates()

        days_results: list[dict] = []
        days_failed: list[dict] = []
        total_fetched = 0
        total_created = 0
        total_skipped_duplicates = 0

        for statement_date in dates:
            try:
                day_result = self._fetch_and_store_one_day(
                    account_number=payload.account_number,
                    statement_date=statement_date,
                    api_host=api_host,
                    api_token=api_token,
                    pfx_path=pfx_path,
                    pfx_passphrase=pfx_passphrase,
                    ca_bundle_path=ca_bundle_path,
                    ssl_verify=ssl_verify,
                )
            except HTTPException as exc:
                # A single failed day (e.g. Sberbank has no data for that date, or a
                # transient error) shouldn't abort the whole period - record it and continue.
                days_failed.append({"statement_date": statement_date, "detail": exc.detail})
                continue

            total_fetched += day_result["fetched"]
            total_created += day_result["created"]
            total_skipped_duplicates += day_result["skipped_duplicates"]
            days_results.append(day_result)

        return {
            "settings_api_bank_id": payload.settings_api_bank_id,
            "account_number": payload.account_number,
            "days_requested": len(dates),
            "days_succeeded": len(days_results),
            "days_failed": len(days_failed),
            "fetched": total_fetched,
            "created": total_created,
            "skipped_duplicates": total_skipped_duplicates,
            "days": days_results,
            "errors": days_failed,
        }

    def get_list(
        self,
        payee_id_missing: bool | None = None,
        payer_id_missing: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        account_number: str | None = None,
        bank_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        object_id: str | None = None,
        object_missing: bool | None = None,
    ) -> list[dict]:
        rows = self.repo.get_list(
            payee_id_missing, payer_id_missing, date_from, date_to, account_number, bank_type, limit, offset,
            object_id, object_missing,
        )
        return self._serialize_rows(rows)

    def get_by_id(self, item_id: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")
        return self._serialize_rows([row])[0]

    def get_by_object(
        self,
        object_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        exclude_business_cards: bool = True,
    ) -> dict:
        """Statement rows (payments) attached to an object other than via business cards:
        summary + the rows themselves, each with its contract / invoice payment links."""
        self._ensure_object_exists(object_id)
        rows = self.repo.get_by_object_id(object_id, date_from, date_to, exclude_business_cards)

        total_debit = sum(float(r.amount or 0) for r in rows if r.direction == "DEBIT")
        total_credit = sum(float(r.amount or 0) for r in rows if r.direction == "CREDIT")
        operations = self._serialize_rows(rows)

        object_row = self.reference_repo.get_objects_by_ids([object_id])[0]
        return {
            "object_id": object_id,
            "object_short_name": object_row.short_name,
            "period": {"date_from": date_from, "date_to": date_to},
            "exclude_business_cards": exclude_business_cards,
            "summary": {
                "total_debit": total_debit,
                "total_credit": total_credit,
                "net_spent": total_debit - total_credit,
                "operations_count": len(rows),
                "with_invoice_payment": sum(1 for o in operations if o["invoice_payments"]),
                "with_contract": sum(1 for o in operations if o["contract"]),
            },
            "operations": operations,
        }

    def _ensure_object_exists(self, object_id: str) -> None:
        if not self.reference_repo or not self.reference_repo.get_objects_by_ids([object_id]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объект не найден")

    def update(self, item_id: str, payload: ExtractItemUpdate) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")

        data = payload.model_dump(exclude_unset=True)
        if data.get("object_id"):
            self._ensure_object_exists(data["object_id"])
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save(row)
        return self._serialize_rows([updated])[0]

    def set_object(self, payload: ExtractItemSetObjectRequest) -> dict:
        """Attach (or, with object_id=null, detach) many statement rows to one object at once."""
        if payload.object_id:
            self._ensure_object_exists(payload.object_id)
        ids = list(dict.fromkeys(payload.extract_ids))
        rows = self.repo.get_by_ids(ids)
        found = {r.id for r in rows}
        for row in rows:
            row.object_id = payload.object_id
        self.repo.db.commit()
        return {
            "object_id": payload.object_id,
            "updated": len(rows),
            "missing_extract_ids": [i for i in ids if i not in found],
        }

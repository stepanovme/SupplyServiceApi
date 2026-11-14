import calendar
import re
import uuid
from datetime import date, datetime

from fastapi import HTTPException, status

from app.models.business_card import BusinessCard, BusinessCardCreate, BusinessCardUpdate
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.sberbank_client import fetch_sberbank_corporate_cards


class BusinessCardService:
    def __init__(
        self,
        repo: BusinessCardRepository,
        bank_settings_repo: SettingsApiBankRepository | None = None,
        extract_business_card_repo: ExtractBusinessCardRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.bank_settings_repo = bank_settings_repo
        self.extract_business_card_repo = extract_business_card_repo
        self.reference_repo = reference_repo

    @staticmethod
    def _last4(card_number_mask: str | None) -> str | None:
        if not card_number_mask:
            return None
        digits = re.sub(r"\D", "", card_number_mask)
        return digits[-4:] if len(digits) >= 4 else None

    @staticmethod
    def _parse_bank_expiry(value: str | None) -> date | None:
        """Sberbank returns "MM/YY" (e.g. "08/30") - convert to the last day of that month."""
        if not value:
            return None
        match = re.match(r"^(\d{2})/(\d{2})$", value.strip())
        if not match:
            return None
        month = int(match.group(1))
        year = 2000 + int(match.group(2))
        try:
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, last_day)
        except ValueError:
            return None

    @staticmethod
    def _serialize(row: BusinessCard) -> dict:
        return {
            "id": row.id,
            "settings_api_bank_id": row.settings_api_bank_id,
            "bank_business_card_id": row.bank_business_card_id,
            "source": row.source,
            "bank_type": row.bank_type,
            "account_number": row.account_number,
            "card_number_mask": row.card_number_mask,
            "card_last4": row.card_last4,
            "embossed_name": row.embossed_name,
            "holder_name": row.holder_name,
            "holder_user_id": row.holder_user_id,
            "card_open_date": row.card_open_date,
            "expiry_date": row.expiry_date,
            "card_status": row.card_status,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
        }

    def get_list(
        self,
        holder_user_id: str | None = None,
        settings_api_bank_id: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        rows = self.repo.get_list(holder_user_id, settings_api_bank_id, is_active, limit, offset)
        return [self._serialize(row) for row in rows]

    def get_by_id(self, card_id: str) -> dict:
        row = self.repo.get_by_id(card_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business card not found")
        return self._serialize(row)

    def create_manual(self, payload: BusinessCardCreate, created_by: str) -> dict:
        data = payload.model_dump(exclude_unset=True)
        row = BusinessCard(
            id=str(uuid.uuid4()),
            source="manual",
            card_last4=self._last4(payload.card_number_mask),
            created_by=created_by,
            **data,
        )
        created = self.repo.create(row)
        return self._serialize(created)

    def update(self, card_id: str, payload: BusinessCardUpdate) -> dict:
        row = self.repo.get_by_id(card_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business card not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        if "card_number_mask" in data:
            row.card_last4 = self._last4(row.card_number_mask)

        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, card_id: str) -> None:
        row = self.repo.get_by_id(card_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business card not found")
        self.repo.delete(row)

    def fetch_from_sberbank(self, settings_api_bank_id: str, created_by: str) -> dict:
        if not self.bank_settings_repo:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="bank_settings_repo is not configured")

        bank_setting = self.bank_settings_repo.get_by_id(settings_api_bank_id)
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

        cards = fetch_sberbank_corporate_cards(
            api_host=api_host,
            api_token=api_token,
            pfx_path=pfx_path,
            pfx_passphrase=pfx_passphrase,
            ca_bundle_path=ca_bundle_path,
            ssl_verify=ssl_verify,
        )

        created_count = 0
        updated_count = 0
        items: list[dict] = []

        for card in cards:
            bank_business_card_id = card.get("businessCardId")
            masked = card.get("maskedCardNumber")

            existing = None
            if bank_business_card_id:
                existing = self.repo.get_by_bank_business_card_id(settings_api_bank_id, bank_business_card_id)

            if existing:
                existing.account_number = card.get("accountNumber")
                existing.card_number_mask = masked
                existing.card_last4 = self._last4(masked)
                existing.bank_type = "sberbank"
                existing.embossed_name = card.get("embossedName")
                existing.holder_name = card.get("holderName")
                existing.card_open_date = self._parse_iso_date(card.get("cardOpenDate"))
                existing.expiry_date = self._parse_bank_expiry(card.get("cardExpiryDate"))
                existing.card_status = card.get("cardStatus")
                saved = self.repo.save(existing)
                updated_count += 1
                items.append(self._serialize(saved))
            else:
                row = BusinessCard(
                    id=str(uuid.uuid4()),
                    settings_api_bank_id=settings_api_bank_id,
                    bank_business_card_id=bank_business_card_id,
                    source="sberbank",
                    bank_type="sberbank",
                    account_number=card.get("accountNumber"),
                    card_number_mask=masked,
                    card_last4=self._last4(masked),
                    embossed_name=card.get("embossedName"),
                    holder_name=card.get("holderName"),
                    card_open_date=self._parse_iso_date(card.get("cardOpenDate")),
                    expiry_date=self._parse_bank_expiry(card.get("cardExpiryDate")),
                    card_status=card.get("cardStatus"),
                    created_by=created_by,
                )
                created = self.repo.create(row)
                created_count += 1
                items.append(self._serialize(created))

        return {
            "settings_api_bank_id": settings_api_bank_id,
            "fetched": len(cards),
            "created": created_count,
            "updated": updated_count,
            "items": items,
        }

    @staticmethod
    def _parse_iso_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _summarize(rows: list) -> dict:
        total_debit = sum(float(item.amount or 0) for _link, item in rows if item.direction == "DEBIT")
        total_credit = sum(float(item.amount or 0) for _link, item in rows if item.direction == "CREDIT")
        return {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "net_spent": total_debit - total_credit,
            "operations_count": len(rows),
        }

    @staticmethod
    def _serialize_operation(link, item, object_names: dict[str, str]) -> dict:
        return {
            "extract_business_card_id": link.id,
            "extract_id": item.id,
            "business_card_id": link.business_card_id,
            "operationDate": item.operationDate,
            "amount": float(item.amount) if item.amount is not None else None,
            "direction": item.direction,
            "paymentPurpose": item.paymentPurpose,
            "payeeName": item.payeeName,
            "payerName": item.payerName,
            "object_id": link.object_id,
            "object_short_name": object_names.get(link.object_id) if link.object_id else None,
        }

    @classmethod
    def _serialize_operations(cls, rows: list, object_names: dict[str, str]) -> list[dict]:
        operations = [cls._serialize_operation(link, item, object_names) for link, item in rows]
        operations.sort(key=lambda o: o["operationDate"] or datetime.min, reverse=True)
        return operations

    @staticmethod
    def _group_by_object(rows: list, object_names: dict[str, str]) -> list[dict]:
        buckets: dict[str | None, dict] = {}
        for link, item in rows:
            key = link.object_id
            bucket = buckets.setdefault(
                key,
                {
                    "object_id": key,
                    "object_short_name": object_names.get(key) if key else None,
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                    "operations_count": 0,
                },
            )
            amount = float(item.amount or 0)
            if item.direction == "DEBIT":
                bucket["total_debit"] += amount
            elif item.direction == "CREDIT":
                bucket["total_credit"] += amount
            bucket["operations_count"] += 1

        result = []
        for bucket in buckets.values():
            bucket["net_spent"] = bucket["total_debit"] - bucket["total_credit"]
            result.append(bucket)
        result.sort(key=lambda b: b["net_spent"], reverse=True)
        return result

    def get_spending(
        self,
        card_ids: list[str] | None = None,
        holder_user_id: str | None = None,
        settings_api_bank_id: str | None = None,
        bank_type: str | None = None,
        is_active: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        if not self.extract_business_card_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="extract_business_card_repo is not configured",
            )

        if card_ids:
            cards = self.repo.get_by_ids(card_ids)
        else:
            cards = self.repo.get_list(holder_user_id, settings_api_bank_id, is_active, limit=1000, offset=0)
            if bank_type:
                cards = [c for c in cards if c.bank_type == bank_type]

        period = {"date_from": date_from, "date_to": date_to}

        if not cards:
            return {
                "period": period,
                "summary": {"total_debit": 0.0, "total_credit": 0.0, "net_spent": 0.0, "operations_count": 0},
                "by_object": [],
                "by_holder": [],
                "operations": [],
                "cards": [],
            }

        rows = self.extract_business_card_repo.get_spending_rows([c.id for c in cards], date_from, date_to)

        rows_by_card: dict[str, list] = {c.id: [] for c in cards}
        for link, item in rows:
            rows_by_card.setdefault(link.business_card_id, []).append((link, item))

        object_ids = {link.object_id for link, _item in rows if link.object_id}
        object_names: dict[str, str] = {}
        if object_ids and self.reference_repo:
            object_names = {o.id: o.short_name for o in self.reference_repo.get_objects_by_ids(list(object_ids))}

        cards_result: list[dict] = []
        for card in cards:
            card_rows = rows_by_card.get(card.id, [])
            cards_result.append(
                {
                    "card": self._serialize(card),
                    "summary": self._summarize(card_rows),
                    "by_object": self._group_by_object(card_rows, object_names),
                    "operations": self._serialize_operations(card_rows, object_names),
                }
            )

        # Holder grouping uses whatever identifies a person on the card: holder_user_id
        # when known, otherwise falls back to the free-text holder_name from the bank.
        by_holder_map: dict[str, dict] = {}
        for card in cards:
            key = card.holder_user_id or card.holder_name or card.id
            bucket = by_holder_map.setdefault(
                key,
                {
                    "holder_user_id": card.holder_user_id,
                    "holder_name": card.holder_name,
                    "card_ids": [],
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                    "operations_count": 0,
                },
            )
            bucket["card_ids"].append(card.id)
            card_summary = self._summarize(rows_by_card.get(card.id, []))
            bucket["total_debit"] += card_summary["total_debit"]
            bucket["total_credit"] += card_summary["total_credit"]
            bucket["operations_count"] += card_summary["operations_count"]

        by_holder = []
        for bucket in by_holder_map.values():
            bucket["net_spent"] = bucket["total_debit"] - bucket["total_credit"]
            by_holder.append(bucket)
        by_holder.sort(key=lambda b: b["net_spent"], reverse=True)

        return {
            "period": period,
            "summary": self._summarize(rows),
            "by_object": self._group_by_object(rows, object_names),
            "by_holder": by_holder,
            "operations": self._serialize_operations(rows, object_names),
            "cards": cards_result,
        }

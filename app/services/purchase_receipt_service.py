import hashlib
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.purchase_receipt import (
    PurchaseReceipt,
    PurchaseReceiptAccess,
    PurchaseReceiptAutoCategorize,
    PurchaseReceiptBulkDelete,
    PurchaseReceiptBulkShare,
    PurchaseReceiptBulkUpdate,
    PurchaseReceiptCategoriesAdd,
    PurchaseReceiptCategory,
    PurchaseReceiptComment,
    PurchaseReceiptCommentCreate,
    PurchaseReceiptCommentUpdate,
    PurchaseReceiptCreate,
    PurchaseReceiptFile,
    PurchaseReceiptFromQr,
    PurchaseReceiptHashtag,
    PurchaseReceiptItem,
    PurchaseReceiptShare,
    PurchaseReceiptUpdate,
    msk_now,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.purchase_receipt_repository import PurchaseReceiptRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services import receipt_category_ai
from app.services.proverkacheka_client import fetch_receipt
from app.services.receipt_seller_logo_service import logo_public_url, normalize_inn

logger = logging.getLogger(__name__)

# QR strings being looked up right now: a scanner can fire the same code several times, and the
# receipt service refuses a repeat of the same receipt for about a minute.
_inflight_lock = threading.Lock()
_inflight_qr: set[tuple] = set()

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_FILES_PER_RECEIPT = 20
ALLOWED_FILE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif", "gif", "pdf"}
BASE_RECEIPT_FILES_DIR = os.getenv("SUPPLY_RECEIPT_FILES_DIR") or os.path.join(os.getcwd(), "storage", "receipts")
FILES_URL_PREFIX = "/api/supply/purchase-receipts"
# Public address under which the receipt folder is served, e.g. https://supply.st29.ru/storage/receipts
# (the file is then <base>/<receipt_id>/<storage_name>). Empty - only the API download link is given.
BASE_RECEIPT_FILES_URL = (os.getenv("SUPPLY_RECEIPT_FILES_URL") or "").strip().rstrip("/")


def _norm_num(value) -> str | None:
    """Fiscal numbers arrive as strings from the QR but as numbers in the API answer; compare
    them in one form (no padding, no spaces)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return (text.lstrip("0") or "0") if text.isdigit() else text


def _clean(value, limit: int | None = None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[:limit] if limit else text


MAX_HASHTAG_LENGTH = 50
MAX_HASHTAGS = 100
_HASHTAG_JUNK = re.compile(r"[^\w\-]", re.UNICODE)


def normalize_hashtags(tags) -> list[str]:
    """'#Командировка ', 'ремонт  кровли' -> ['командировка', 'ремонт_кровли']: no '#', lower case,
    spaces become '_', anything but letters, digits, '_' and '-' is dropped; duplicates and empty tags go."""
    result: list[str] = []
    for raw in tags or []:
        tag = re.sub(r"\s+", "_", str(raw).strip().lstrip("#").strip().lower())
        tag = _HASHTAG_JUNK.sub("", tag).strip("_-")
        if not tag:
            continue
        if len(tag) > MAX_HASHTAG_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Хештег «{tag[:20]}…» длиннее {MAX_HASHTAG_LENGTH} символов",
            )
        if tag not in result:
            result.append(tag)
    if len(result) > MAX_HASHTAGS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Не больше {MAX_HASHTAGS} хештегов у чека")
    return result


def _rub(kopecks) -> float | None:
    """The receipt API reports money in kopecks."""
    if kopecks is None:
        return None
    return round(float(kopecks) / 100, 2)


def parse_qr(qrraw: str) -> dict:
    """t=20260923T2230&s=1719.45&fn=...&i=26770&fp=...&n=1 -> normalized fields."""
    pairs = {k.strip().lower(): v.strip() for k, v in parse_qsl(qrraw.strip().lstrip("?"), keep_blank_values=True)}
    missing = [k for k in ("t", "s", "fn", "i", "fp") if not pairs.get(k)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"В строке QR-кода не хватает полей: {', '.join(missing)}",
        )
    return {
        "t": pairs["t"],
        "s": pairs["s"],
        "fn": _norm_num(pairs["fn"]),
        "fd": _norm_num(pairs["i"]),
        "fp": _norm_num(pairs["fp"]),
        "n": pairs.get("n") or "1",
    }


def _parse_qr_time(value: str | None) -> datetime | None:
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime((value or "").upper(), fmt)
        except ValueError:
            continue
    return None


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def map_api_receipt(data: dict) -> dict:
    """proverkacheka `data.json` -> our receipt fields + items (money converted to rubles)."""
    items = []
    for idx, raw in enumerate(data.get("items") or [], start=1):
        quantity = float(raw.get("quantity") or 1)
        total = _rub(raw.get("sum"))
        price = _rub(raw.get("price"))
        items.append(
            {
                "position": idx,
                "name": _clean(raw.get("name"), 500) or "Без названия",
                "price": price if price is not None else (round(total / quantity, 2) if total is not None and quantity else 0),
                "quantity": quantity,
                "sum": total if total is not None else round((price or 0) * quantity, 2),
                "nds_code": raw.get("nds"),
                "nds_sum": _rub(raw.get("ndsSum")),
            }
        )

    total_sum = _rub(data.get("totalSum"))
    if total_sum is None:
        total_sum = round(sum(i["sum"] for i in items), 2)

    return {
        "fn": _norm_num(data.get("fiscalDriveNumber")),
        "fd": _norm_num(data.get("fiscalDocumentNumber")),
        "fp": _norm_num(data.get("fiscalSign")),
        "receipt_type": int(data.get("operationType") or 1),
        "purchased_at": _parse_iso(data.get("dateTime")),
        "total_sum": total_sum,
        "cash_sum": _rub(data.get("cashTotalSum")),
        "ecash_sum": _rub(data.get("ecashTotalSum")),
        "seller_name": _clean(data.get("user"), 500),
        "seller_inn": _clean(data.get("userInn"), 12),
        "retail_place": _clean(data.get("retailPlace"), 500),
        "retail_place_address": _clean(data.get("retailPlaceAddress"), 1000),
        "items": items,
    }


class PurchaseReceiptService:
    def __init__(
        self,
        repo: PurchaseReceiptRepository,
        auth_user_repo: AuthUserRepository,
        reference_repo: ReferenceObjectRepository,
        business_card_repo: BusinessCardRepository,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.business_card_repo = business_card_repo

    # --- permissions ------------------------------------------------------------------------
    def _role(self, receipt: PurchaseReceipt, user_id: str) -> str | None:
        """owner | edit | view | None"""
        if receipt.created_by == user_id:
            return "owner"
        access = self.repo.get_access(receipt.id, user_id)
        return access.access_level if access else None

    def _get_for(self, receipt_id: str, user_id: str, need: str = "view") -> tuple[PurchaseReceipt, str]:
        receipt = self.repo.get_by_id(receipt_id)
        role = self._role(receipt, user_id) if receipt else None
        # A receipt the user can't see looks exactly like one that doesn't exist.
        if not receipt or role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не найден")
        allowed = {"view": ("owner", "edit", "view"), "edit": ("owner", "edit"), "owner": ("owner",)}[need]
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для этого действия с чеком")
        return receipt, role

    # --- validation of attachments ----------------------------------------------------------
    def _check_object(self, object_id: str | None) -> None:
        if object_id and not self.reference_repo.get_objects_by_ids([object_id]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объект не найден")

    def _check_card(self, card_id: str | None) -> None:
        if card_id and not self.business_card_repo.get_by_id(card_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бизнес-карта не найдена")

    def _check_users(self, user_ids: list[str | None]) -> None:
        ids = [u for u in dict.fromkeys(user_ids) if u]
        if not ids:
            return
        found = {u.id for u in self.auth_user_repo.get_by_ids(ids)}
        missing = [u for u in ids if u not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пользователи не найдены: {', '.join(missing)}")

    @staticmethod
    def _payment_for_new(card_id: str | None, method: str | None) -> str | None:
        """Payment method of a new receipt: a business card means the method is business_card."""
        if card_id:
            if method not in (None, "business_card"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Бизнес-карту можно указать только при способе оплаты business_card",
                )
            return "business_card"
        return method

    @staticmethod
    def _apply_payment(receipt: PurchaseReceipt, data: dict) -> str | None:
        """Applies business_card_id / payment_method from a change request to a receipt keeping the two
        consistent. Returns an error text when the combination is impossible (nothing is changed then)."""
        has_card, has_method = "business_card_id" in data, "payment_method" in data
        card, method = data.get("business_card_id"), data.get("payment_method")

        if has_card and card:
            if has_method and method not in (None, "business_card"):
                return "Бизнес-карту можно указать только при способе оплаты business_card"
            receipt.business_card_id, receipt.payment_method = card, "business_card"
            return None
        if has_method:
            if method is None and receipt.business_card_id and not has_card:
                return "Чтобы убрать способ оплаты «бизнес-карта», снимите business_card_id"
            if method in ("cash", "credit_card"):
                receipt.business_card_id = None  # paid another way: no business card
            if has_card:
                receipt.business_card_id = None
            receipt.payment_method = method
            return None
        if has_card:  # card removed, the method stays as it was
            receipt.business_card_id = None
        return None

    def _check_categories(self, category_ids: list[str], user_id: str) -> list[str]:
        """Only categories the user can use: standard ones or their own. Somebody else's personal
        category is reported as not found, like a missing one."""
        ids = list(dict.fromkeys(category_ids))
        found = {c.id for c in self.repo.get_categories_by_ids(ids) if c.owner_user_id is None or c.owner_user_id == user_id}
        missing = [c for c in ids if c not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Категории чеков не найдены: {', '.join(missing)}"
            )
        return ids

    # --- serialization ----------------------------------------------------------------------
    @staticmethod
    def _short_fio(user) -> dict | None:
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        fio = " ".join(p for p in [user.surname, name_initial, patronymic_initial] if p).strip()
        return {"id": user.id, "short_fio": fio or None}

    @staticmethod
    def _serialize_file(f: PurchaseReceiptFile) -> dict:
        return {
            "id": f.id,
            "original_name": f.original_name,
            "mime_type": f.mime_type,
            "file_size": f.file_size,
            "source": f.source,
            "uploaded_by": f.uploaded_by,
            "created_at": f.created_at,
            # direct link to the file when SUPPLY_RECEIPT_FILES_URL is configured, otherwise the API one
            "url": (
                f"{BASE_RECEIPT_FILES_URL}/{f.receipt_id}/{f.storage_name}"
                if BASE_RECEIPT_FILES_URL
                else f"{FILES_URL_PREFIX}/{f.receipt_id}/files/{f.id}"
            ),
            # always the API download link (checks access rights on every request)
            "download_url": f"{FILES_URL_PREFIX}/{f.receipt_id}/files/{f.id}",
        }

    def _serialize_many(self, receipts: list[PurchaseReceipt], user_id: str, with_items: bool = True,
                        with_comments: bool = False) -> list[dict]:
        ids = [r.id for r in receipts]
        items_by_receipt: dict[str, list] = {}
        if with_items:
            for item in self.repo.get_items(ids):
                items_by_receipt.setdefault(item.receipt_id, []).append(item)

        links = self.repo.get_category_links(ids)
        categories = {c.id: c for c in self.repo.get_categories_by_ids([l.category_id for l in links])}
        cats_by_receipt: dict[str, list[dict]] = {}
        for link in links:
            cat = categories.get(link.category_id)
            cats_by_receipt.setdefault(link.receipt_id, []).append(
                {
                    "id": link.category_id,
                    "name": cat.name if cat else None,
                    "color": cat.color if cat else None,
                    "is_system": cat.owner_user_id is None if cat else None,
                }
            )

        files_by_receipt: dict[str, list] = {}
        for f in self.repo.get_files(ids):
            files_by_receipt.setdefault(f.receipt_id, []).append(f)

        access_rows = self.repo.get_access_rows(ids)
        access_by_receipt: dict[str, list] = {}
        for row in access_rows:
            access_by_receipt.setdefault(row.receipt_id, []).append(row)

        tags_by_receipt: dict[str, list[str]] = {}
        for h in self.repo.get_hashtags(ids):
            tags_by_receipt.setdefault(h.receipt_id, []).append(h.tag)

        comment_counts = self.repo.get_comment_counts(ids)
        comments_by_receipt: dict[str, list] = {}
        if with_comments:
            for rid in ids:
                comments_by_receipt[rid] = self.repo.get_comments(rid)

        user_ids = (
            {r.created_by for r in receipts}
            | {a.user_id for a in access_rows}
            | {r.from_user_id for r in receipts if r.from_user_id}
            | {r.for_user_id for r in receipts if r.for_user_id}
            | {c.user_id for cs in comments_by_receipt.values() for c in cs}
        )
        users = {u.id: u for u in self.auth_user_repo.get_by_ids(list(user_ids))}
        objects = {o.id: o for o in self.reference_repo.get_objects_by_ids([r.object_id for r in receipts if r.object_id])}
        cards = {c.id: c for c in self.business_card_repo.get_by_ids([r.business_card_id for r in receipts if r.business_card_id])}

        reports = self.repo.get_advance_reports(ids)
        logos = self.repo.get_seller_logos([normalize_inn(r.seller_inn) for r in receipts if r.seller_inn])

        result = []
        for r in receipts:
            role = "owner" if r.created_by == user_id else next(
                (a.access_level for a in access_by_receipt.get(r.id, []) if a.user_id == user_id), None
            )
            obj, card = objects.get(r.object_id), cards.get(r.business_card_id)
            data = {
                "id": r.id,
                "source": r.source,
                "my_access": role,
                "created_by": self._short_fio(users.get(r.created_by)) or {"id": r.created_by, "short_fio": None},
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "purchased_at": r.purchased_at,
                "receipt_type": r.receipt_type,
                "total_sum": float(r.total_sum),
                "cash_sum": float(r.cash_sum) if r.cash_sum is not None else None,
                "ecash_sum": float(r.ecash_sum) if r.ecash_sum is not None else None,
                "seller_name": r.seller_name,
                "seller_inn": r.seller_inn,
                "seller_logo_url": logo_public_url(logos.get(normalize_inn(r.seller_inn))) if r.seller_inn else None,
                "retail_place": r.retail_place,
                "retail_place_address": r.retail_place_address,
                "fn": r.fn,
                "fd": r.fd,
                "fp": r.fp,
                "comment": r.comment,
                "from_user_id": r.from_user_id,
                "from_user": self._short_fio(users.get(r.from_user_id)) if r.from_user_id else None,
                "for_user_id": r.for_user_id,
                "for_user": self._short_fio(users.get(r.for_user_id)) if r.for_user_id else None,
                "hashtags": tags_by_receipt.get(r.id, []),
                "comments_count": comment_counts.get(r.id, 0),
                "advance_report": reports.get(r.id),
                "payment_method": r.payment_method,
                "object_id": r.object_id,
                "object": {"id": obj.id, "short_name": obj.short_name} if obj else None,
                "business_card_id": r.business_card_id,
                "business_card": (
                    {
                        "id": card.id,
                        "card_number_mask": card.card_number_mask,
                        "card_last4": card.card_last4,
                        "holder_name": card.holder_name,
                        "bank_type": card.bank_type,
                    }
                    if card
                    else None
                ),
                "categories": cats_by_receipt.get(r.id, []),
                "files": [self._serialize_file(f) for f in files_by_receipt.get(r.id, [])],
                "shared_with_count": len(access_by_receipt.get(r.id, [])),
            }
            if with_items:
                data["items"] = [
                    {
                        "position": i.position,
                        "name": i.name,
                        "price": float(i.price),
                        "quantity": float(i.quantity),
                        "sum": float(i.sum),
                        "nds_code": i.nds_code,
                        "nds_sum": float(i.nds_sum) if i.nds_sum is not None else None,
                    }
                    for i in items_by_receipt.get(r.id, [])
                ]
            if with_comments:
                data["comments"] = [
                    self._serialize_comment(c, users, user_id, owner=(r.created_by == user_id))
                    for c in comments_by_receipt.get(r.id, [])
                ]
            if role == "owner":
                data["shared_with"] = [
                    {
                        "user": self._short_fio(users.get(a.user_id)) or {"id": a.user_id, "short_fio": None},
                        "access_level": a.access_level,
                    }
                    for a in access_by_receipt.get(r.id, [])
                ]
            result.append(data)
        return result

    # --- creating ---------------------------------------------------------------------------
    def _conflict(self, existing: PurchaseReceipt, user_id: str) -> HTTPException:
        has_access = self._role(existing, user_id) is not None
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Этот чек уже добавлен"
                + ("" if has_access else " другим пользователем — попросите владельца открыть вам доступ"),
                "receipt_id": existing.id if has_access else None,
                "has_access": has_access,
            },
        )

    @staticmethod
    def _receipt_dir(receipt_id: str) -> str:
        return os.path.join(BASE_RECEIPT_FILES_DIR, receipt_id)

    @staticmethod
    def _validate_file(original_name: str, file_bytes: bytes, max_bytes: int = MAX_FILE_BYTES) -> str:
        extension = os.path.splitext(original_name or "")[1].lower().lstrip(".")
        if extension not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Допустимы файлы: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}",
            )
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Файл «{original_name}» пустой")
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Файл «{original_name}» больше {max_bytes // (1024 * 1024)} МБ",
            )
        return extension

    def _store_file(self, receipt_id: str, original_name: str, mime_type: str, file_bytes: bytes,
                    extension: str, source: str, user_id: str) -> PurchaseReceiptFile:
        """Writes the bytes to disk and returns the (not yet added) DB row; the caller removes the
        file again if the database transaction fails."""
        directory = self._receipt_dir(receipt_id)
        os.makedirs(directory, exist_ok=True)
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        with open(os.path.join(directory, storage_name), "wb") as stream:
            stream.write(file_bytes)
        return PurchaseReceiptFile(
            id=str(uuid.uuid4()),
            receipt_id=receipt_id,
            original_name=(original_name or storage_name)[:255],
            storage_name=storage_name,
            mime_type=(mime_type or "application/octet-stream")[:100],
            file_size=len(file_bytes),
            md5_hash=hashlib.md5(file_bytes).hexdigest(),
            source=source,
            uploaded_by=user_id,
        )

    def _save_new(self, fields: dict, items: list[dict], links: "_Links", source: str, user_id: str, qr_raw=None, raw=None,
                  photo: dict | None = None) -> dict:
        receipt = PurchaseReceipt(
            id=str(uuid.uuid4()),
            created_by=user_id,
            source=source,
            object_id=links.object_id,
            business_card_id=links.business_card_id,
            payment_method=links.payment_method,
            from_user_id=links.from_user_id,
            for_user_id=links.for_user_id,
            comment=links.comment,
            qr_raw=qr_raw,
            raw_data=raw,
            **fields,
        )
        try:
            self.repo.add(receipt)
            self.repo.flush()  # the receipt row must exist before its items / categories
            for item in items:
                self.repo.add(PurchaseReceiptItem(receipt_id=receipt.id, **item))
            for category_id in links.category_ids:
                self.repo.add(PurchaseReceiptCategory(receipt_id=receipt.id, category_id=category_id))
            for tag in links.hashtags:
                self.repo.add(PurchaseReceiptHashtag(receipt_id=receipt.id, tag=tag))
            if photo:  # the photo the receipt was recognized from is kept with it, in the same transaction
                self.repo.add(self._store_file(receipt.id, source="receipt_photo", user_id=user_id, **photo))
            self.repo.commit()
        except IntegrityError:
            self.repo.rollback()
            shutil.rmtree(self._receipt_dir(receipt.id), ignore_errors=True)
            if fields.get("fn"):
                existing = self.repo.find_by_fiscal(fields["fn"], fields["fd"], fields["fp"])
                if existing:  # lost a race with another request for the same receipt
                    raise self._conflict(existing, user_id)
            raise
        except Exception:
            self.repo.rollback()
            shutil.rmtree(self._receipt_dir(receipt.id), ignore_errors=True)
            raise
        self.repo.refresh(receipt)

        if links.auto_categorize and not links.category_ids:
            ai = self._auto_categorize_receipt(receipt, user_id, only_without_categories=True)
        else:
            ai = {"status": "skipped", "reason": "categories_given" if links.category_ids else "disabled", "categories": []}
        out = self._serialize_many([receipt], user_id)[0]
        out["ai_categorization"] = ai
        return out

    def _auto_categorize_receipt(self, receipt: PurchaseReceipt, user_id: str, only_without_categories: bool) -> dict:
        """Mistral picks categories (standard + the user's own) by the receipt's positions and they are
        added to the receipt. Never raises - the receipt is already saved and must stay so."""
        try:
            existing = {l.category_id for l in self.repo.get_category_links([receipt.id])}
            if existing and only_without_categories:
                return {"status": "skipped", "reason": "already_has_categories", "categories": []}

            items = [
                {"name": i.name, "quantity": float(i.quantity), "sum": float(i.sum)} for i in self.repo.get_items([receipt.id])
            ]
            available = [{"id": c.id, "name": c.name} for c in self.repo.get_available_categories(user_id)]
            ids, note = receipt_category_ai.suggest_category_ids(receipt.seller_name, items, available)
            new_ids = [cid for cid in ids if cid not in existing]
            if new_ids:
                for cid in new_ids:
                    self.repo.add(PurchaseReceiptCategory(receipt_id=receipt.id, category_id=cid))
                receipt.updated_at = msk_now()
                self.repo.commit()
            names = {c["id"]: c["name"] for c in available}
            if new_ids:
                return {"status": "applied", "reason": None, "categories": [{"id": c, "name": names[c]} for c in new_ids]}
            if ids:  # the model's picks are already on the receipt
                return {"status": "skipped", "reason": "already_assigned", "categories": []}
            status_name = "no_match" if note == "no_match" else "skipped"
            return {"status": status_name, "reason": note, "categories": []}
        except Exception:
            self.repo.rollback()
            logger.exception("auto categorization of receipt %s failed", receipt.id)
            return {"status": "error", "reason": "internal_error", "categories": []}

    def auto_categorize(self, payload: PurchaseReceiptAutoCategorize, user_id: str) -> dict:
        """Runs the same Mistral categorization for receipts that were added earlier."""
        if not receipt_category_ai.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Подбор категорий не настроен ({receipt_category_ai.API_KEY_ENV} в .env)",
            )
        ids = list(dict.fromkeys(payload.receipt_ids))
        receipts = {r.id: r for r in self.repo.get_by_ids(ids)}
        shared = self.repo.get_access_for_user(list(receipts), user_id)

        results = []
        for rid in ids:
            receipt = receipts.get(rid)
            role = None if receipt is None else ("owner" if receipt.created_by == user_id else shared.get(rid))
            if role is None:
                results.append({"receipt_id": rid, "status": "not_found", "categories": []})
            elif role == "view":
                results.append({"receipt_id": rid, "status": "forbidden", "categories": []})
            else:
                results.append(
                    {"receipt_id": rid, **self._auto_categorize_receipt(receipt, user_id, payload.only_without_categories)}
                )
        return {
            "requested": len(ids),
            "applied": sum(1 for r in results if r["status"] == "applied"),
            "results": results,
        }

    def _prepare_links(self, payload, user_id: str) -> "_Links":
        self._check_object(payload.object_id)
        self._check_card(payload.business_card_id)
        category_ids = self._check_categories(payload.category_ids, user_id)
        payment_method = self._payment_for_new(payload.business_card_id, getattr(payload, "payment_method", None))
        from_user_id = getattr(payload, "from_user_id", None) or None
        for_user_id = getattr(payload, "for_user_id", None) or None
        self._check_users([from_user_id, for_user_id])
        hashtags = normalize_hashtags(getattr(payload, "hashtags", []))
        return _Links(
            payload.object_id, payload.business_card_id, category_ids, payload.comment, getattr(payload, "auto_categorize", True),
            payment_method=payment_method, from_user_id=from_user_id, for_user_id=for_user_id, hashtags=hashtags,
        )

    def create_manual(self, payload: PurchaseReceiptCreate, user_id: str) -> dict:
        links = self._prepare_links(payload, user_id)
        fn, fd, fp = _norm_num(payload.fn), _norm_num(payload.fd), _norm_num(payload.fp)
        if fn:
            existing = self.repo.find_by_fiscal(fn, fd, fp)
            if existing:
                raise self._conflict(existing, user_id)

        items = [
            {
                "position": idx,
                "name": i.name.strip(),
                "price": round(i.price, 2),
                "quantity": i.quantity,
                "sum": round(i.sum if i.sum is not None else i.price * i.quantity, 2),
                "nds_code": i.nds_code,
                "nds_sum": i.nds_sum,
            }
            for idx, i in enumerate(payload.items, start=1)
        ]
        total = payload.total_sum if payload.total_sum is not None else round(sum(i["sum"] for i in items), 2)
        fields = {
            "fn": fn,
            "fd": fd,
            "fp": fp,
            "receipt_type": payload.receipt_type,
            "purchased_at": payload.purchased_at,
            "total_sum": round(total, 2),
            "seller_name": _clean(payload.seller_name, 500),
            "seller_inn": _clean(payload.seller_inn, 12),
            "retail_place": _clean(payload.retail_place, 500),
            "retail_place_address": _clean(payload.retail_place_address, 1000),
        }
        return self._save_new(fields, items, links, "manual", user_id)

    def _create_from_api(self, api_data: dict, links: "_Links", source: str, user_id: str, qr_raw: str | None,
                         photo: dict | None = None) -> dict:
        mapped = map_api_receipt(api_data)
        if mapped["fn"]:
            existing = self.repo.find_by_fiscal(mapped["fn"], mapped["fd"], mapped["fp"])
            if existing:  # e.g. a photo of a receipt that was added earlier
                raise self._conflict(existing, user_id)
        items = mapped.pop("items")
        return self._save_new(mapped, items, links, source, user_id, qr_raw=qr_raw, raw=api_data, photo=photo)

    def create_from_qr(self, payload: PurchaseReceiptFromQr, user_id: str) -> dict:
        links = self._prepare_links(payload, user_id)
        if payload.qrraw:
            qr = parse_qr(payload.qrraw)
        else:
            qr = parse_qr(f"t={payload.t}&s={payload.s}&fn={payload.fn}&i={payload.fd}&fp={payload.fp}&n={payload.n}")

        # Check our own database first - the receipt service is metered and slow.
        existing = self.repo.find_by_fiscal(qr["fn"], qr["fd"], qr["fp"])
        if existing:
            raise self._conflict(existing, user_id)

        qr_raw = f"t={qr['t']}&s={qr['s']}&fn={qr['fn']}&i={qr['fd']}&fp={qr['fp']}&n={qr['n']}"
        key = (qr["fn"], qr["fd"], qr["fp"])
        with _inflight_lock:
            busy = key in _inflight_qr
            _inflight_qr.add(key)
        if busy:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Этот чек уже обрабатывается — подождите, он скоро появится", "receipt_id": None, "has_access": False},
            )
        try:
            api_data = fetch_receipt(qrraw=qr_raw)
            return self._create_from_api(api_data, links, "qr", user_id, qr_raw)
        finally:
            with _inflight_lock:
                _inflight_qr.discard(key)

    def create_from_photo(
        self, file_bytes: bytes, filename: str, content_type: str, links_payload, user_id: str
    ) -> dict:
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
        if len(file_bytes) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Фото больше 10 МБ")
        if not (content_type or "").startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужен файл-изображение с QR-кодом чека")
        extension = self._validate_file(filename or "receipt.jpg", file_bytes, MAX_PHOTO_BYTES)

        links = self._prepare_links(links_payload, user_id)
        api_data = fetch_receipt(file_bytes=file_bytes, filename=filename or "receipt.jpg", content_type=content_type)
        photo = {"original_name": filename or "receipt.jpg", "mime_type": content_type, "file_bytes": file_bytes, "extension": extension}
        return self._create_from_api(api_data, links, "photo", user_id, None, photo=photo)

    # --- reading ----------------------------------------------------------------------------
    def get_list(self, user_id: str, scope="all", object_id=None, business_card_id=None, category_id=None,
                 date_from=None, date_to=None, limit=50, offset=0, payment_method=None, hashtag=None,
                 from_user_id=None, for_user_id=None, sort_by="created_at", order="desc") -> list[dict]:
        tags = normalize_hashtags([hashtag]) if hashtag else []
        rows = self.repo.get_list(
            user_id, scope, object_id, business_card_id, category_id, date_from, date_to, limit, offset,
            payment_method=payment_method, hashtag=tags[0] if tags else None,
            from_user_id=from_user_id, for_user_id=for_user_id, sort_by=sort_by, order=order,
        )
        return self._serialize_many(rows, user_id)

    def get_by_id(self, receipt_id: str, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id)
        return self._serialize_many([receipt], user_id, with_comments=True)[0]

    def get_hashtags(self, user_id: str, scope: str = "all") -> list[dict]:
        """Hashtags used on the receipts the user can see, most used first - for autocomplete and filters."""
        return [{"tag": tag, "receipts_count": count} for tag, count in self.repo.get_hashtag_stats(user_id, scope)]

    def get_objects(self, user_id: str, scope: str = "mine", date_from=None, date_to=None) -> dict:
        """Objects the user has receipts for, with the number of receipts and the net amount;
        receipts without an object are returned as a separate bucket."""
        stats = self.repo.get_object_stats(user_id, scope, date_from, date_to)
        names = {o.id: o for o in self.reference_repo.get_objects_by_ids([row[0] for row in stats if row[0]])}

        objects, without = [], None
        for object_id, count, net, last in stats:
            entry = {
                "object_id": object_id,
                "object_short_name": names[object_id].short_name if object_id in names else None,
                "receipts_count": int(count),
                "net_sum": round(float(net), 2),
                "last_purchased_at": last,
            }
            if object_id is None:
                without = entry
            else:
                objects.append(entry)
        objects.sort(key=lambda o: (-o["receipts_count"], (o["object_short_name"] or "").lower()))

        return {
            "scope": scope,
            "period": {"date_from": date_from, "date_to": date_to},
            "total_receipts": sum(o["receipts_count"] for o in objects) + (without["receipts_count"] if without else 0),
            "objects": objects,
            "without_object": without,
        }

    def get_by_object(self, object_id: str, user_id: str, date_from=None, date_to=None,
                      sort_by="created_at", order="desc") -> dict:
        obj = self.reference_repo.get_objects_by_ids([object_id])
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объект не найден")
        rows = self.repo.get_list(
            user_id, "all", object_id=object_id, date_from=date_from, date_to=date_to, unbounded=True,
            sort_by=sort_by, order=order,
        )
        receipts = self._serialize_many(rows, user_id)

        purchases = sum(r["total_sum"] for r in receipts if r["receipt_type"] == 1)
        returns = sum(r["total_sum"] for r in receipts if r["receipt_type"] == 2)
        return {
            "object_id": object_id,
            "object_short_name": obj[0].short_name,
            "period": {"date_from": date_from, "date_to": date_to},
            "summary": {
                "total_purchases": round(purchases, 2),
                "total_returns": round(returns, 2),
                "net_spent": round(purchases - returns, 2),
                "paid_by_business_card": round(
                    sum(r["total_sum"] for r in receipts if r["business_card_id"] and r["receipt_type"] == 1)
                    - sum(r["total_sum"] for r in receipts if r["business_card_id"] and r["receipt_type"] == 2),
                    2,
                ),
                "receipts_count": len(receipts),
                # net sum by how the receipts were paid (purchases minus returns); "unspecified" = not set
                "by_payment_method": {
                    method or "unspecified": round(
                        sum(r["total_sum"] for r in receipts if r["payment_method"] == method and r["receipt_type"] == 1)
                        - sum(r["total_sum"] for r in receipts if r["payment_method"] == method and r["receipt_type"] == 2),
                        2,
                    )
                    for method in ("business_card", "cash", "credit_card", None)
                },
            },
            "receipts": receipts,
        }

    # --- changing ---------------------------------------------------------------------------
    def update(self, receipt_id: str, payload: PurchaseReceiptUpdate, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id, need="edit")
        data = payload.model_dump(exclude_unset=True)

        if "object_id" in data:
            self._check_object(data["object_id"])
            receipt.object_id = data["object_id"]
        if "business_card_id" in data:
            self._check_card(data["business_card_id"])
        if "business_card_id" in data or "payment_method" in data:
            error = self._apply_payment(receipt, data)
            if error:
                self.repo.rollback()
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
        if "comment" in data:
            receipt.comment = data["comment"]
        for field in ("from_user_id", "for_user_id"):
            if field in data:
                self._check_users([data[field]])
                setattr(receipt, field, data[field] or None)
        if data.get("hashtags") is not None:
            wanted_tags = set(normalize_hashtags(data["hashtags"]))
            current_tags = {h.tag: h for h in self.repo.get_hashtags([receipt.id])}
            for tag, row in current_tags.items():
                if tag not in wanted_tags:
                    self.repo.delete(row)
            for tag in wanted_tags - set(current_tags):
                self.repo.add(PurchaseReceiptHashtag(receipt_id=receipt.id, tag=tag))
        if data.get("category_ids") is not None:
            wanted = set(self._check_categories(data["category_ids"], user_id))
            current = {l.category_id: l for l in self.repo.get_category_links([receipt.id])}
            for category_id, link in current.items():
                if category_id not in wanted:
                    self.repo.delete(link)
            for category_id in wanted - set(current):
                self.repo.add(PurchaseReceiptCategory(receipt_id=receipt.id, category_id=category_id))

        receipt.updated_at = msk_now()
        try:
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.refresh(receipt)
        return self._serialize_many([receipt], user_id)[0]

    def bulk_update(self, payload: PurchaseReceiptBulkUpdate, user_id: str) -> dict:
        """Same object / business card / categories / comment for many receipts. What is wrong with
        the request itself (unknown object, card or category) fails everything; receipts the user
        can't edit are skipped and reported, the rest are changed in one transaction."""
        fields = payload.model_fields_set
        if "object_id" in fields:
            self._check_object(payload.object_id)
        if "business_card_id" in fields:
            self._check_card(payload.business_card_id)
        category_ids = self._check_categories(payload.category_ids, user_id) if payload.category_ids else []
        for field in ("from_user_id", "for_user_id"):
            if field in fields:
                self._check_users([getattr(payload, field)])
        tag_list = normalize_hashtags(payload.hashtags) if payload.hashtags else []
        payment_data = {k: getattr(payload, k) for k in ("business_card_id", "payment_method") if k in fields}
        if payment_data.get("business_card_id") and payment_data.get("payment_method") not in (None, "business_card") and "payment_method" in fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Бизнес-карту можно указать только при способе оплаты business_card",
            )

        ids = list(dict.fromkeys(payload.receipt_ids))
        receipts = {r.id: r for r in self.repo.get_by_ids(ids)}
        shared = self.repo.get_access_for_user(list(receipts), user_id)
        links_by_receipt: dict[str, dict[str, PurchaseReceiptCategory]] = {}
        if "category_ids" in fields:
            for link in self.repo.get_category_links(list(receipts)):
                links_by_receipt.setdefault(link.receipt_id, {})[link.category_id] = link
        tags_by_receipt: dict[str, dict[str, PurchaseReceiptHashtag]] = {}
        if "hashtags" in fields:
            for h in self.repo.get_hashtags(list(receipts)):
                tags_by_receipt.setdefault(h.receipt_id, {})[h.tag] = h

        results, now = [], msk_now()
        try:
            for rid in ids:
                receipt = receipts.get(rid)
                role = None if receipt is None else ("owner" if receipt.created_by == user_id else shared.get(rid))
                if role is None:  # unknown id and "not yours" look the same on purpose
                    results.append({"receipt_id": rid, "status": "not_found"})
                    continue
                if role == "view":
                    results.append({"receipt_id": rid, "status": "forbidden"})
                    continue

                if payment_data:
                    error = self._apply_payment(receipt, payment_data)
                    if error:  # e.g. "no payment method" on a receipt that still has a business card
                        results.append({"receipt_id": rid, "status": "conflict", "detail": error})
                        continue
                if "object_id" in fields:
                    receipt.object_id = payload.object_id
                if "comment" in fields:
                    receipt.comment = payload.comment
                for field in ("from_user_id", "for_user_id"):
                    if field in fields:
                        setattr(receipt, field, getattr(payload, field) or None)
                if "hashtags" in fields:
                    current_tags = tags_by_receipt.get(rid, {})
                    wanted_tags = set(tag_list)
                    if payload.hashtag_mode == "replace":
                        for tag, row in current_tags.items():
                            if tag not in wanted_tags:
                                self.repo.delete(row)
                        add_tags = wanted_tags - set(current_tags)
                    elif payload.hashtag_mode == "remove":
                        for tag in wanted_tags & set(current_tags):
                            self.repo.delete(current_tags[tag])
                        add_tags = set()
                    else:
                        add_tags = wanted_tags - set(current_tags)
                    for tag in add_tags:
                        self.repo.add(PurchaseReceiptHashtag(receipt_id=rid, tag=tag))
                if "category_ids" in fields:
                    current = links_by_receipt.get(rid, {})
                    wanted = set(category_ids)
                    if payload.category_mode == "replace":
                        for cid, link in current.items():
                            if cid not in wanted:
                                self.repo.delete(link)
                        to_add = wanted - set(current)
                    elif payload.category_mode == "remove":
                        for cid in wanted & set(current):
                            self.repo.delete(current[cid])
                        to_add = set()
                    else:
                        to_add = wanted - set(current)
                    for cid in to_add:
                        self.repo.add(PurchaseReceiptCategory(receipt_id=rid, category_id=cid))
                receipt.updated_at = now
                results.append({"receipt_id": rid, "status": "updated"})
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise

        updated = sum(1 for r in results if r["status"] == "updated")
        return {
            "requested": len(ids),
            "updated": updated,
            "skipped": len(ids) - updated,
            "results": results,
        }

    def bulk_delete(self, payload: PurchaseReceiptBulkDelete, user_id: str) -> dict:
        """Deletes the receipts the user owns. Others are skipped and reported (not_found - missing
        or not visible, forbidden - visible but only its owner may delete)."""
        ids = list(dict.fromkeys(payload.receipt_ids))
        receipts = {r.id: r for r in self.repo.get_by_ids(ids)}
        shared = self.repo.get_access_for_user(list(receipts), user_id)

        in_reports = self.repo.get_advance_reports(list(receipts))
        results, to_delete = [], []
        for rid in ids:
            receipt = receipts.get(rid)
            if receipt is None or (receipt.created_by != user_id and rid not in shared):
                results.append({"receipt_id": rid, "status": "not_found"})
            elif receipt.created_by != user_id:
                results.append({"receipt_id": rid, "status": "forbidden"})
            elif rid in in_reports:  # it sits in an advance report (and maybe in 1C): take it out of the report first
                results.append({"receipt_id": rid, "status": "in_advance_report", "report_number": in_reports[rid]["number"]})
            else:
                to_delete.append(receipt)
                results.append({"receipt_id": rid, "status": "deleted"})

        try:
            for receipt in to_delete:
                self.repo.delete(receipt)  # items, categories, files and access rows cascade
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        for receipt in to_delete:  # the photos go only after the database change succeeded
            shutil.rmtree(self._receipt_dir(receipt.id), ignore_errors=True)

        return {"requested": len(ids), "deleted": len(to_delete), "skipped": len(ids) - len(to_delete), "results": results}

    def bulk_share(self, payload: PurchaseReceiptBulkShare, user_id: str) -> dict:
        """Gives every listed user the access level on every receipt the caller owns (an existing
        grant just gets the new level). Unknown users fail the whole request; receipts the caller
        doesn't own are skipped and reported."""
        targets = [u for u in dict.fromkeys(payload.user_ids)]
        found = {u.id for u in self.auth_user_repo.get_by_ids(targets)}
        missing = [u for u in targets if u not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пользователи не найдены: {', '.join(missing)}")

        ids = list(dict.fromkeys(payload.receipt_ids))
        receipts = {r.id: r for r in self.repo.get_by_ids(ids)}
        shared = self.repo.get_access_for_user(list(receipts), user_id)
        existing = {(a.receipt_id, a.user_id): a for a in self.repo.get_access_rows(list(receipts))}

        results, granted = [], 0
        try:
            for rid in ids:
                receipt = receipts.get(rid)
                if receipt is None or (receipt.created_by != user_id and rid not in shared):
                    results.append({"receipt_id": rid, "status": "not_found"})
                    continue
                if receipt.created_by != user_id:
                    results.append({"receipt_id": rid, "status": "forbidden"})
                    continue
                users = [u for u in targets if u != receipt.created_by]  # the owner already has full access
                for target in users:
                    row = existing.get((rid, target))
                    if row:
                        row.access_level = payload.access_level
                    else:
                        self.repo.add(
                            PurchaseReceiptAccess(receipt_id=rid, user_id=target, access_level=payload.access_level, created_by=user_id)
                        )
                granted += len(users)
                results.append({"receipt_id": rid, "status": "shared", "users": len(users)})
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise

        shared_count = sum(1 for r in results if r["status"] == "shared")
        return {
            "requested": len(ids),
            "shared": shared_count,
            "skipped": len(ids) - shared_count,
            "access_level": payload.access_level,
            "grants": granted,
            "results": results,
        }

    def add_categories(self, receipt_id: str, payload: PurchaseReceiptCategoriesAdd, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id, need="edit")
        for category_id in self._check_categories(payload.category_ids, user_id):
            if not self.repo.get_category_link(receipt.id, category_id):
                self.repo.add(PurchaseReceiptCategory(receipt_id=receipt.id, category_id=category_id))
        receipt.updated_at = msk_now()
        self.repo.commit()
        return self._serialize_many([receipt], user_id)[0]

    def remove_category(self, receipt_id: str, category_id: str, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id, need="edit")
        link = self.repo.get_category_link(receipt.id, category_id)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="У чека нет такой категории")
        self.repo.delete(link)
        receipt.updated_at = msk_now()
        self.repo.commit()
        return self._serialize_many([receipt], user_id)[0]

    def delete(self, receipt_id: str, user_id: str) -> None:
        receipt, _role = self._get_for(receipt_id, user_id, need="owner")
        in_report = self.repo.get_advance_reports([receipt.id]).get(receipt.id)
        if in_report:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Чек входит в авансовый отчёт №{in_report['number']}: сначала уберите его из отчёта",
            )
        self.repo.delete(receipt)  # items, categories, files and access rows go with it (ON DELETE CASCADE)
        self.repo.commit()
        shutil.rmtree(self._receipt_dir(receipt_id), ignore_errors=True)

    # --- files (photos / scans) -------------------------------------------------------------
    def add_files(self, receipt_id: str, uploads: list[dict], user_id: str) -> dict:
        """uploads: [{original_name, mime_type, file_bytes}]. All-or-nothing: if any file is
        rejected nothing is saved."""
        receipt, _role = self._get_for(receipt_id, user_id, need="edit")
        if not uploads:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файлы не переданы")
        if self.repo.count_files(receipt.id) + len(uploads) > MAX_FILES_PER_RECEIPT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"У чека не может быть больше {MAX_FILES_PER_RECEIPT} файлов",
            )
        extensions = [self._validate_file(u["original_name"], u["file_bytes"]) for u in uploads]

        try:
            for upload, extension in zip(uploads, extensions):
                self.repo.add(self._store_file(receipt.id, upload["original_name"], upload["mime_type"], upload["file_bytes"],
                                               extension, "upload", user_id))
            receipt.updated_at = msk_now()
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            # remove files written by this call (everything on disk that has no DB row)
            known = {f.storage_name for f in self.repo.get_files([receipt.id])}
            directory = self._receipt_dir(receipt.id)
            if os.path.isdir(directory):
                for name in os.listdir(directory):
                    if name not in known:
                        os.remove(os.path.join(directory, name))
            raise
        return self._serialize_many([receipt], user_id)[0]

    def get_file_for_download(self, receipt_id: str, file_id: str, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id)
        row = self.repo.get_file(receipt.id, file_id)
        path = os.path.join(self._receipt_dir(receipt.id), row.storage_name) if row else None
        if not row or not os.path.isfile(path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
        return {"path": path, "filename": row.original_name, "media_type": row.mime_type}

    def delete_file(self, receipt_id: str, file_id: str, user_id: str) -> dict:
        receipt, _role = self._get_for(receipt_id, user_id, need="edit")
        row = self.repo.get_file(receipt.id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
        path = os.path.join(self._receipt_dir(receipt.id), row.storage_name)
        self.repo.delete(row)
        receipt.updated_at = msk_now()
        self.repo.commit()
        if os.path.isfile(path):  # only after the DB change succeeded
            os.remove(path)
        return self._serialize_many([receipt], user_id)[0]

    # --- comments ---------------------------------------------------------------------------
    def _serialize_comment(self, c: PurchaseReceiptComment, users: dict, user_id: str, owner: bool = False) -> dict:
        return {
            "id": c.id,
            "receipt_id": c.receipt_id,
            "text": c.text,
            "user": self._short_fio(users.get(c.user_id)) or {"id": c.user_id, "short_fio": None},
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "can_edit": c.user_id == user_id,  # only the author edits a comment
            "can_delete": c.user_id == user_id or owner,  # the author or the owner of the receipt removes it
        }

    def _comments_view(self, receipt: PurchaseReceipt, user_id: str, owner: bool) -> list[dict]:
        comments = self.repo.get_comments(receipt.id)
        users = {u.id: u for u in self.auth_user_repo.get_by_ids(list({c.user_id for c in comments}))}
        return [self._serialize_comment(c, users, user_id, owner) for c in comments]

    def get_comments(self, receipt_id: str, user_id: str) -> list[dict]:
        receipt, role = self._get_for(receipt_id, user_id)
        return self._comments_view(receipt, user_id, owner=role == "owner")

    def add_comment(self, receipt_id: str, payload: PurchaseReceiptCommentCreate, user_id: str) -> dict:
        """Anyone who can see the receipt (even with view-only access) may comment on it."""
        receipt, role = self._get_for(receipt_id, user_id)
        comment = PurchaseReceiptComment(id=str(uuid.uuid4()), receipt_id=receipt.id, user_id=user_id, text=payload.text.strip())
        try:
            self.repo.add(comment)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.refresh(comment)
        users = {u.id: u for u in self.auth_user_repo.get_by_ids([user_id])}
        return self._serialize_comment(comment, users, user_id, owner=role == "owner")

    def _get_comment_or_404(self, receipt_id: str, comment_id: str, user_id: str):
        receipt, role = self._get_for(receipt_id, user_id)
        comment = self.repo.get_comment(receipt.id, comment_id)
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комментарий не найден")
        return receipt, role, comment

    def update_comment(self, receipt_id: str, comment_id: str, payload: PurchaseReceiptCommentUpdate, user_id: str) -> dict:
        receipt, role, comment = self._get_comment_or_404(receipt_id, comment_id, user_id)
        if comment.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Изменять можно только свои комментарии")
        comment.text = payload.text.strip()
        comment.updated_at = msk_now()
        self.repo.commit()
        self.repo.refresh(comment)
        users = {u.id: u for u in self.auth_user_repo.get_by_ids([comment.user_id])}
        return self._serialize_comment(comment, users, user_id, owner=role == "owner")

    def delete_comment(self, receipt_id: str, comment_id: str, user_id: str) -> None:
        receipt, role, comment = self._get_comment_or_404(receipt_id, comment_id, user_id)
        if comment.user_id != user_id and role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Удалить чужой комментарий может только владелец чека"
            )
        self.repo.delete(comment)
        self.repo.commit()

    # --- sharing ----------------------------------------------------------------------------
    def get_access(self, receipt_id: str, user_id: str) -> list[dict]:
        receipt, _role = self._get_for(receipt_id, user_id, need="owner")
        rows = self.repo.get_access_rows([receipt.id])
        users = {u.id: u for u in self.auth_user_repo.get_by_ids([r.user_id for r in rows])}
        return [
            {
                "user": self._short_fio(users.get(r.user_id)) or {"id": r.user_id, "short_fio": None},
                "access_level": r.access_level,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def share(self, receipt_id: str, payload: PurchaseReceiptShare, user_id: str) -> list[dict]:
        receipt, _role = self._get_for(receipt_id, user_id, need="owner")
        if payload.user_id == receipt.created_by:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Владелец чека и так имеет полный доступ")
        if not self.auth_user_repo.get_by_ids([payload.user_id]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

        row = self.repo.get_access(receipt.id, payload.user_id)
        if row:
            row.access_level = payload.access_level
        else:
            self.repo.add(
                PurchaseReceiptAccess(
                    receipt_id=receipt.id, user_id=payload.user_id, access_level=payload.access_level, created_by=user_id
                )
            )
        self.repo.commit()
        return self.get_access(receipt_id, user_id)

    def unshare(self, receipt_id: str, target_user_id: str, user_id: str) -> None:
        """The owner can take access away from anyone; a user can also give up their own access."""
        receipt = self.repo.get_by_id(receipt_id)
        if not receipt or self._role(receipt, user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не найден")
        if receipt.created_by != user_id and target_user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для этого действия с чеком")
        row = self.repo.get_access(receipt.id, target_user_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доступ этому пользователю не выдан")
        self.repo.delete(row)
        self.repo.commit()


class _Links:
    def __init__(self, object_id, business_card_id, category_ids, comment, auto_categorize=True,
                 payment_method=None, from_user_id=None, for_user_id=None, hashtags=None) -> None:
        self.auto_categorize = auto_categorize
        self.payment_method = payment_method
        self.from_user_id = from_user_id
        self.for_user_id = for_user_id
        self.hashtags = hashtags or []
        self.object_id = object_id
        self.business_card_id = business_card_id
        self.category_ids = category_ids
        self.comment = comment

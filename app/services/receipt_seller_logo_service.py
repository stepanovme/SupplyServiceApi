import os
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func

from app.models.purchase_receipt import PurchaseReceipt
from app.models.receipt_seller_logo import ReceiptSellerLogo, ReceiptSellerLogoSetUrl, msk_now
from app.repositories.auth_user_repository import AuthUserRepository

# the role that manages shared reference data (standard receipt categories, logos)
ADMIN_ROLE_ID = "697afdbf-4f2e-47fb-8277-7127b9b85317"

BASE_LOGO_FILES_DIR = os.getenv("SUPPLY_RECEIPT_LOGOS_DIR") or os.path.join(os.getcwd(), "storage", "receipt_logos")
# public address of that directory, e.g. https://supply.st29.ru/storage/receipt_logos (empty = API link)
BASE_LOGO_FILES_URL = (os.getenv("SUPPLY_RECEIPT_LOGOS_URL") or "").strip().rstrip("/")
API_PREFIX = "/api/supply/receipt-seller-logos"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}  # no SVG: it can carry scripts
MAX_LOGO_BYTES = 2 * 1024 * 1024


def normalize_inn(value: str | None) -> str | None:
    inn = re.sub(r"\D", "", value or "")
    return inn if len(inn) in (10, 12) else None


def logo_public_url(row: ReceiptSellerLogo | None) -> str | None:
    """Where a client can load the logo from."""
    if row is None:
        return None
    if row.logo_url:
        return row.logo_url
    if row.storage_name:
        if BASE_LOGO_FILES_URL:
            return f"{BASE_LOGO_FILES_URL}/{row.storage_name}"
        return f"{API_PREFIX}/{row.seller_inn}/image"
    return None


class ReceiptSellerLogoService:
    def __init__(self, db, auth_user_repo: AuthUserRepository) -> None:
        self.db = db
        self.auth_user_repo = auth_user_repo

    # --- helpers ----------------------------------------------------------------------------
    def _require_admin(self, user_id: str) -> None:
        if not self.auth_user_repo.has_role(user_id, ADMIN_ROLE_ID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Логотипы продавцов может менять только администратор")

    def _inn_or_400(self, inn: str) -> str:
        normalized = normalize_inn(inn)
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ИНН должен состоять из 10 или 12 цифр")
        return normalized

    def _get_row(self, inn: str) -> ReceiptSellerLogo | None:
        return self.db.query(ReceiptSellerLogo).filter(ReceiptSellerLogo.seller_inn == inn).first()

    def _serialize(self, row: ReceiptSellerLogo) -> dict:
        return {
            "seller_inn": row.seller_inn,
            "seller_name": row.seller_name,
            "logo_url": logo_public_url(row),
            "source": "url" if row.logo_url else "file",
            "created_by": row.created_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _remove_file(storage_name: str | None) -> None:
        if storage_name:
            path = os.path.join(BASE_LOGO_FILES_DIR, storage_name)
            if os.path.isfile(path):
                os.remove(path)

    def _upsert(self, inn: str, user_id: str) -> tuple[ReceiptSellerLogo, bool]:
        row = self._get_row(inn)
        if row:
            return row, False
        row = ReceiptSellerLogo(id=str(uuid.uuid4()), seller_inn=inn, created_by=user_id)
        self.db.add(row)
        return row, True

    # --- API --------------------------------------------------------------------------------
    def get_list(self, search: str | None = None) -> list[dict]:
        q = self.db.query(ReceiptSellerLogo)
        if search:
            like = f"%{search.strip()}%"
            q = q.filter((ReceiptSellerLogo.seller_inn.like(like)) | (ReceiptSellerLogo.seller_name.like(like)))
        return [self._serialize(r) for r in q.order_by(ReceiptSellerLogo.seller_name, ReceiptSellerLogo.seller_inn).all()]

    def get_by_inn(self, inn: str) -> dict:
        row = self._get_row(self._inn_or_400(inn))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Логотип для этого ИНН не задан")
        return self._serialize(row)

    def get_missing(self, user_id: str) -> list[dict]:
        """Sellers that appear on receipts but have no logo yet - the to-do list for whoever adds them.
        Counts every user's receipts, so it is for administrators."""
        self._require_admin(user_id)
        have = self.db.query(ReceiptSellerLogo.seller_inn)
        rows = (
            self.db.query(
                PurchaseReceipt.seller_inn, func.max(PurchaseReceipt.seller_name), func.count(PurchaseReceipt.id)
            )
            .filter(PurchaseReceipt.seller_inn.is_not(None), PurchaseReceipt.seller_inn != "", PurchaseReceipt.seller_inn.notin_(have))
            .group_by(PurchaseReceipt.seller_inn)
            .order_by(func.count(PurchaseReceipt.id).desc())
            .all()
        )
        return [{"seller_inn": inn, "seller_name": name, "receipts_count": int(count)} for inn, name, count in rows]

    def set_url(self, inn: str, payload: ReceiptSellerLogoSetUrl, user_id: str) -> dict:
        self._require_admin(user_id)
        inn = self._inn_or_400(inn)
        row, _created = self._upsert(inn, user_id)
        old_file = row.storage_name
        row.logo_url, row.storage_name, row.mime_type = payload.logo_url, None, None
        if payload.seller_name is not None:
            row.seller_name = payload.seller_name.strip() or None
        row.updated_at = msk_now()
        self.db.commit()
        self._remove_file(old_file)  # an uploaded file is replaced by the link
        self.db.refresh(row)
        return self._serialize(row)

    def upload(self, inn: str, file_bytes: bytes, filename: str, content_type: str, seller_name: str | None, user_id: str) -> dict:
        self._require_admin(user_id)
        inn = self._inn_or_400(inn)
        extension = os.path.splitext(filename or "")[1].lower().lstrip(".")
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Допустимы изображения: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
        if len(file_bytes) > MAX_LOGO_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Логотип больше 2 МБ")

        os.makedirs(BASE_LOGO_FILES_DIR, exist_ok=True)
        storage_name = f"{inn}-{uuid.uuid4().hex[:12]}.{extension}"  # new name each time: no stale caches
        path = os.path.join(BASE_LOGO_FILES_DIR, storage_name)
        with open(path, "wb") as stream:
            stream.write(file_bytes)

        try:
            row, _created = self._upsert(inn, user_id)
            old_file = row.storage_name
            row.logo_url, row.storage_name = None, storage_name
            row.mime_type = (content_type or f"image/{extension}")[:100]
            if seller_name is not None:
                row.seller_name = seller_name.strip() or None
            row.updated_at = msk_now()
            self.db.commit()
        except Exception:
            self.db.rollback()
            self._remove_file(storage_name)
            raise
        self._remove_file(old_file)
        self.db.refresh(row)
        return self._serialize(row)

    def get_image(self, inn: str) -> dict:
        row = self._get_row(self._inn_or_400(inn))
        path = os.path.join(BASE_LOGO_FILES_DIR, row.storage_name) if row and row.storage_name else None
        if not row or not path or not os.path.isfile(path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл логотипа не найден")
        return {"path": path, "media_type": row.mime_type or "image/png"}

    def delete(self, inn: str, user_id: str) -> None:
        self._require_admin(user_id)
        row = self._get_row(self._inn_or_400(inn))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Логотип для этого ИНН не задан")
        old_file = row.storage_name
        self.db.delete(row)
        self.db.commit()
        self._remove_file(old_file)

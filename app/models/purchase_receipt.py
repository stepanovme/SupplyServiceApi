from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CHAR, JSON, Column, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class PurchaseReceipt(SupplyBase):
    __tablename__ = "purchase_receipts"

    id = Column(CHAR(36), primary_key=True)
    created_by = Column(String(36), nullable=False, index=True)
    source = Column(Enum("manual", "qr", "photo"), nullable=False, default="manual")
    object_id = Column(CHAR(36), nullable=True, index=True)
    business_card_id = Column(CHAR(36), nullable=True, index=True)
    payment_method = Column(Enum("business_card", "cash", "credit_card"), nullable=True)
    from_user_id = Column(String(36), nullable=True, index=True)
    for_user_id = Column(String(36), nullable=True, index=True)
    fn = Column(String(32), nullable=True)
    fd = Column(String(20), nullable=True)
    fp = Column(String(20), nullable=True)
    receipt_type = Column(SmallInteger, nullable=False, default=1)
    purchased_at = Column(DateTime, nullable=True)
    total_sum = Column(Numeric(14, 2), nullable=False)
    cash_sum = Column(Numeric(14, 2), nullable=True)
    ecash_sum = Column(Numeric(14, 2), nullable=True)
    seller_name = Column(String(500), nullable=True)
    seller_inn = Column(String(12), nullable=True)
    retail_place = Column(String(500), nullable=True)
    retail_place_address = Column(String(1000), nullable=True)
    qr_raw = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class PurchaseReceiptHashtag(SupplyBase):
    __tablename__ = "purchase_receipt_hashtags"

    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), primary_key=True)
    tag = Column(String(50), primary_key=True)


class PurchaseReceiptComment(SupplyBase):
    __tablename__ = "purchase_receipt_comments"

    id = Column(CHAR(36), primary_key=True)
    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class PurchaseReceiptItem(SupplyBase):
    __tablename__ = "purchase_receipt_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    name = Column(String(500), nullable=False)
    price = Column(Numeric(14, 2), nullable=False)
    quantity = Column(Numeric(14, 3), nullable=False)
    sum = Column(Numeric(14, 2), nullable=False)
    nds_code = Column(Integer, nullable=True)
    nds_sum = Column(Numeric(14, 2), nullable=True)


class PurchaseReceiptCategory(SupplyBase):
    __tablename__ = "purchase_receipt_categories"

    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(CHAR(36), primary_key=True)


class PurchaseReceiptFile(SupplyBase):
    __tablename__ = "purchase_receipt_files"

    id = Column(CHAR(36), primary_key=True)
    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    storage_name = Column(String(100), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    md5_hash = Column(CHAR(32), nullable=False)
    source = Column(Enum("upload", "receipt_photo"), nullable=False, default="upload")
    uploaded_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class PurchaseReceiptAccess(SupplyBase):
    __tablename__ = "purchase_receipt_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(CHAR(36), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    access_level = Column(Enum("view", "edit"), nullable=False, default="view")
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False)


# --- request schemas ---------------------------------------------------------------------------


PaymentMethod = Literal["business_card", "cash", "credit_card"]


class _ReceiptLinks(BaseModel):
    """What can be attached to a receipt however it was added."""

    object_id: str | None = Field(default=None, description="reference_service.objects.id")
    business_card_id: str | None = Field(default=None, description="Чек оплачен этой бизнес-картой")
    category_ids: list[str] = Field(default_factory=list, description="Товарные категории (warehouse_category.id)")
    comment: str | None = Field(default=None)
    payment_method: PaymentMethod | None = Field(
        default=None,
        description="Способ оплаты: business_card - бизнес-карта, cash - наличные, credit_card - кредитная карта. "
        "Если указана business_card_id, способ оплаты - business_card",
    )
    from_user_id: str | None = Field(default=None, description="От кого чек (пользователь), необязательно")
    for_user_id: str | None = Field(default=None, description="Для кого чек (пользователь), необязательно")
    hashtags: list[str] = Field(default_factory=list, max_length=100, description="Хештеги, любое количество или пусто")
    auto_categorize: bool = Field(
        default=True,
        description="Подобрать категории по позициям чека с помощью ИИ, если категории не указаны",
    )


class PurchaseReceiptItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    price: float = Field(ge=0, description="Цена за единицу, руб.")
    quantity: float = Field(default=1, gt=0)
    sum: float | None = Field(default=None, ge=0, description="Не указана - price * quantity")
    nds_code: int | None = Field(default=None)
    nds_sum: float | None = Field(default=None, ge=0)


class PurchaseReceiptCreate(_ReceiptLinks):
    """Manual entry. fn/fd/fp are optional, but if one is given all three are needed
    (they identify the fiscal receipt and protect against adding it twice)."""

    purchased_at: datetime
    total_sum: float | None = Field(default=None, ge=0, description="Не указана - сумма позиций")
    seller_name: str | None = Field(default=None, max_length=500)
    seller_inn: str | None = Field(default=None, max_length=12)
    retail_place: str | None = Field(default=None, max_length=500)
    retail_place_address: str | None = Field(default=None, max_length=1000)
    receipt_type: Literal[1, 2, 3, 4] = Field(default=1, description="1 приход, 2 возврат прихода, 3 расход, 4 возврат расхода")
    fn: str | None = Field(default=None, max_length=32)
    fd: str | None = Field(default=None, max_length=20)
    fp: str | None = Field(default=None, max_length=20)
    items: list[PurchaseReceiptItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        fiscal = [self.fn, self.fd, self.fp]
        if any(fiscal) and not all(fiscal):
            raise ValueError("Фискальные реквизиты fn, fd, fp указываются только все вместе")
        if self.total_sum is None and not self.items:
            raise ValueError("Укажите total_sum или хотя бы одну позицию в items")
        return self


class PurchaseReceiptFromQr(_ReceiptLinks):
    """Either the raw QR string, or its parts (as printed under the QR / typed by hand)."""

    qrraw: str | None = Field(default=None, description="Строка из QR-кода: t=20260923T2230&s=1719.45&fn=...&i=...&fp=...&n=1")
    t: str | None = Field(default=None, description="Дата и время чека: 20260923T2230")
    s: str | None = Field(default=None, description="Сумма чека, руб.: 1719.45")
    fn: str | None = Field(default=None)
    fd: str | None = Field(default=None, description="ФД (параметр i в QR)")
    fp: str | None = Field(default=None, description="ФПД")
    n: int = Field(default=1, description="Тип операции (1 - приход)")

    @model_validator(mode="after")
    def _check(self):
        if not self.qrraw and not all([self.t, self.s, self.fn, self.fd, self.fp]):
            raise ValueError("Передайте qrraw либо все поля t, s, fn, fd, fp")
        return self


class PurchaseReceiptUpdate(BaseModel):
    """Only the attachments are editable; fiscal data of a scanned receipt is not."""

    object_id: str | None = Field(default=None, description="null - снять привязку к объекту")
    business_card_id: str | None = Field(default=None, description="null - снять привязку к карте")
    category_ids: list[str] | None = Field(default=None, description="Заменяет весь набор категорий")
    comment: str | None = Field(default=None)
    payment_method: PaymentMethod | None = Field(
        default=None, description="Способ оплаты; cash/credit_card снимают привязку к бизнес-карте"
    )
    from_user_id: str | None = Field(default=None, description="От кого чек; null - убрать")
    for_user_id: str | None = Field(default=None, description="Для кого чек; null - убрать")
    hashtags: list[str] | None = Field(default=None, max_length=100, description="Заменяет весь набор хештегов; [] - убрать все")


class PurchaseReceiptBulkUpdate(BaseModel):
    """Apply the same attachments to many receipts at once. Only the fields that are present in
    the request are touched; object_id / business_card_id = null detach."""

    receipt_ids: list[str] = Field(min_length=1, max_length=500)
    object_id: str | None = Field(default=None, description="Привязать к объекту; null - снять привязку")
    business_card_id: str | None = Field(default=None, description="Оплачено этой бизнес-картой; null - снять")
    category_ids: list[str] | None = Field(default=None, description="Категории - что с ними делать, задаёт category_mode")
    category_mode: Literal["add", "replace", "remove"] = Field(
        default="add", description="add - добавить к имеющимся, replace - заменить весь набор, remove - убрать указанные"
    )
    comment: str | None = Field(default=None)
    payment_method: PaymentMethod | None = Field(default=None, description="Способ оплаты; null - убрать")
    from_user_id: str | None = Field(default=None, description="От кого чек; null - убрать")
    for_user_id: str | None = Field(default=None, description="Для кого чек; null - убрать")
    hashtags: list[str] | None = Field(default=None, max_length=100, description="Хештеги - что с ними делать, задаёт hashtag_mode")
    hashtag_mode: Literal["add", "replace", "remove"] = Field(
        default="add", description="add - добавить к имеющимся, replace - заменить весь набор, remove - убрать указанные"
    )

    @model_validator(mode="after")
    def _check(self):
        touched = self.model_fields_set & {
            "object_id", "business_card_id", "category_ids", "comment",
            "payment_method", "from_user_id", "for_user_id", "hashtags",
        }
        if not touched:
            raise ValueError(
                "Укажите, что применить: object_id, business_card_id, category_ids, comment, "
                "payment_method, from_user_id, for_user_id или hashtags"
            )
        if "hashtags" in self.model_fields_set:
            if self.hashtags is None:
                raise ValueError("hashtags не может быть null; для замены набора на пустой передайте []")
            if self.hashtag_mode in ("add", "remove") and not self.hashtags:
                raise ValueError("Для hashtag_mode add/remove нужен непустой hashtags")
        if "category_ids" in self.model_fields_set:
            if self.category_ids is None:
                raise ValueError("category_ids не может быть null; для замены набора на пустой передайте []")
            if self.category_mode in ("add", "remove") and not self.category_ids:
                raise ValueError("Для category_mode add/remove нужен непустой category_ids")
        return self


class PurchaseReceiptAutoCategorize(BaseModel):
    receipt_ids: list[str] = Field(min_length=1, max_length=50)
    only_without_categories: bool = Field(
        default=True, description="true - не трогать чеки, у которых уже есть категории; false - добавить к имеющимся"
    )


class PurchaseReceiptBulkDelete(BaseModel):
    receipt_ids: list[str] = Field(min_length=1, max_length=500)


class PurchaseReceiptBulkShare(BaseModel):
    """Give the same access to many receipts for one or several users."""

    receipt_ids: list[str] = Field(min_length=1, max_length=500)
    user_ids: list[str] = Field(min_length=1, max_length=100)
    access_level: Literal["view", "edit"] = Field(default="view")


class PurchaseReceiptCategoriesAdd(BaseModel):
    category_ids: list[str] = Field(min_length=1)


class PurchaseReceiptShare(BaseModel):
    user_id: str
    access_level: Literal["view", "edit"] = Field(default="view")


class PurchaseReceiptCommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class PurchaseReceiptCommentUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

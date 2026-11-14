from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.purchase_receipt import (
    PurchaseReceiptAutoCategorize,
    PurchaseReceiptBulkDelete,
    PurchaseReceiptBulkShare,
    PurchaseReceiptBulkUpdate,
    PurchaseReceiptCategoriesAdd,
    PurchaseReceiptCommentCreate,
    PurchaseReceiptCommentUpdate,
    PurchaseReceiptCreate,
    PurchaseReceiptFromQr,
    PurchaseReceiptShare,
    PurchaseReceiptUpdate,
    _ReceiptLinks,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.purchase_receipt_repository import PurchaseReceiptRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.purchase_receipt_service import PurchaseReceiptService

purchase_receipts_router = APIRouter(prefix="/purchase-receipts", tags=["PurchaseReceipts"])


def build_service(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession) -> PurchaseReceiptService:
    return PurchaseReceiptService(
        PurchaseReceiptRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
        BusinessCardRepository(supply_db),
    )


@purchase_receipts_router.get(
    "",
    summary="Мои чеки и чеки, к которым мне открыт доступ",
    description=(
        "scope: all (по умолчанию) | mine (только мои) | shared (только расшаренные мне). "
        "Порядок по умолчанию — по дате ДОБАВЛЕНИЯ в программу: сверху новые, снизу старые. "
        "sort_by=purchased_at сортирует по дате чека, order=asc — от старых к новым. "
        "Фильтры: payment_method (business_card | cash | credit_card), hashtag, from_user_id, for_user_id."
    ),
)
def get_receipts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    scope: Literal["all", "mine", "shared"] = Query(default="all"),
    object_id: str | None = Query(default=None),
    business_card_id: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    payment_method: Literal["business_card", "cash", "credit_card"] | None = Query(default=None),
    hashtag: str | None = Query(default=None, description="Хештег, с «#» или без"),
    from_user_id: str | None = Query(default=None),
    for_user_id: str | None = Query(default=None),
    sort_by: Literal["created_at", "purchased_at"] = Query(default="created_at", description="created_at — дата добавления, purchased_at — дата чека"),
    order: Literal["desc", "asc"] = Query(default="desc", description="desc — сверху новые"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_list(
        _session.user_id, scope, object_id, business_card_id, category_id, date_from, date_to, limit, offset,
        payment_method=payment_method, hashtag=hashtag, from_user_id=from_user_id, for_user_id=for_user_id,
        sort_by=sort_by, order=order,
    )


# literal paths must be registered before the /{receipt_id} wildcards
@purchase_receipts_router.get(
    "/hashtags",
    summary="Хештеги моих чеков (для подсказок и фильтра)",
    description="Хештеги чеков, доступных мне, с количеством чеков; самые частые сверху. scope: all | mine | shared.",
)
def get_receipt_hashtags(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    scope: Literal["all", "mine", "shared"] = Query(default="all"),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_hashtags(_session.user_id, scope)


# literal paths must be registered before the /{receipt_id} wildcards
@purchase_receipts_router.get(
    "/objects",
    summary="Объекты, по которым есть мои чеки, и количество чеков",
    description=(
        "Список объектов с `receipts_count`, чистой суммой `net_sum` (покупки минус возвраты) и датой "
        "последней покупки; сортировка — по убыванию числа чеков. Чеки без объекта вынесены в `without_object`. "
        "scope: mine (по умолчанию — чеки, которые добавил я) | shared (расшаренные мне) | all (оба). "
        "Фильтры date_from/date_to — по дате покупки. Сами чеки объекта: GET /purchase-receipts/by-object/{object_id}."
    ),
)
def get_receipt_objects(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    scope: Literal["mine", "shared", "all"] = Query(default="mine"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_objects(_session.user_id, scope, date_from, date_to)


@purchase_receipts_router.get(
    "/by-object/{object_id}",
    summary="Чеки по объекту (из доступных мне) со сводкой",
)
def get_receipts_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort_by: Literal["created_at", "purchased_at"] = Query(default="created_at"),
    order: Literal["desc", "asc"] = Query(default="desc"),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_object(
        object_id, _session.user_id, date_from, date_to, sort_by=sort_by, order=order
    )


@purchase_receipts_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить чек вручную",
    description="Чек привязывается к пользователю, который его добавил. Если указаны fn/fd/fp, повторно тот же чек добавить нельзя (409).",
)
def create_receipt(
    payload: PurchaseReceiptCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_manual(payload, _session.user_id)


@purchase_receipts_router.post(
    "/bulk-update",
    summary="Массово применить объект / бизнес-карту / категории / комментарий к нескольким чекам",
    description=(
        "Тело: `receipt_ids` (до 500) и то, что применить; затрагиваются только переданные поля. "
        "`object_id` и `business_card_id` = null снимают привязку. Категории: `category_ids` + `category_mode` "
        "(add — добавить к имеющимся, replace — заменить весь набор, remove — убрать указанные). "
        "Неизвестный объект/карта/категория — 404 на весь запрос. Чеки, которые нельзя изменять, пропускаются "
        "и перечисляются в `results` (not_found — нет или нет доступа, forbidden — доступ только на просмотр); "
        "остальные меняются одной транзакцией."
    ),
)
def bulk_update_receipts(
    payload: PurchaseReceiptBulkUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).bulk_update(payload, _session.user_id)


@purchase_receipts_router.post(
    "/auto-categorize",
    summary="Подобрать категории по позициям чеков с помощью ИИ (для уже добавленных чеков)",
    description=(
        "Тело: `receipt_ids` (до 50) и `only_without_categories` (по умолчанию true — чеки, у которых уже есть "
        "категории, пропускаются; false — подобранные категории добавляются к имеющимся). Модель выбирает "
        "до 3 категорий только из доступных вам (стандартные + ваши личные). Нужны права владельца или edit. "
        "Требует MISTRAL_RECEIPT_CATEGORY_API_KEY."
    ),
)
def auto_categorize_receipts(
    payload: PurchaseReceiptAutoCategorize,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).auto_categorize(payload, _session.user_id)


@purchase_receipts_router.post(
    "/bulk-delete",
    summary="Массово удалить чеки (только свои)",
    description=(
        "Тело: `receipt_ids` (до 500). Удаляются чеки, владельцем которых вы являетесь, вместе с позициями, "
        "категориями, доступами и файлами. Остальные пропускаются и перечисляются в `results`: "
        "not_found — нет такого чека или он вам недоступен, forbidden — чек расшарен вам, но удалить его "
        "может только владелец. Операция необратима."
    ),
)
def bulk_delete_receipts(
    payload: PurchaseReceiptBulkDelete,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).bulk_delete(payload, _session.user_id)


@purchase_receipts_router.post(
    "/bulk-share",
    summary="Массово дать доступ к чекам одному или нескольким пользователям",
    description=(
        "Тело: `receipt_ids` (до 500), `user_ids` (до 100) и `access_level` (view | edit). Доступ выдаётся "
        "на чеки, владельцем которых вы являетесь; если у пользователя доступ уже был, меняется его уровень. "
        "Несуществующий пользователь — 404 на весь запрос; чужие и недоступные чеки пропускаются и "
        "перечисляются в `results` (not_found / forbidden)."
    ),
)
def bulk_share_receipts(
    payload: PurchaseReceiptBulkShare,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).bulk_share(payload, _session.user_id)


@purchase_receipts_router.post(
    "/from-qr",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить чек по QR-коду (строка из QR или его реквизиты)",
    description=(
        "Данные чека (продавец, позиции, суммы) запрашиваются на proverkacheka.com. Передайте `qrraw` "
        "(строка из QR: t=...&s=...&fn=...&i=...&fp=...&n=1) либо поля t, s, fn, fd, fp, n. "
        "Если такой чек уже есть в базе, внешний сервис не вызывается — ответ 409."
    ),
)
def create_receipt_from_qr(
    payload: PurchaseReceiptFromQr,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_from_qr(payload, _session.user_id)


@purchase_receipts_router.post(
    "/from-photo",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить чек по фото (QR-код должен быть виден на снимке)",
    description="multipart/form-data: file (изображение до 10 МБ) и необязательные object_id, business_card_id, comment, category_ids (можно повторять поле), payment_method, from_user_id, for_user_id, hashtags (можно повторять поле), auto_categorize (по умолчанию true — подобрать категории по позициям). Фото автоматически сохраняется как файл чека (source=receipt_photo).",
)
async def create_receipt_from_photo(
    file: Annotated[UploadFile, File(...)],
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    object_id: str | None = Form(default=None),
    business_card_id: str | None = Form(default=None),
    comment: str | None = Form(default=None),
    category_ids: list[str] = Form(default=[]),
    auto_categorize: bool = Form(default=True),
    payment_method: Literal["business_card", "cash", "credit_card"] | None = Form(default=None),
    from_user_id: str | None = Form(default=None),
    for_user_id: str | None = Form(default=None),
    hashtags: list[str] = Form(default=[]),
    _session=Depends(get_session),
):
    file_bytes = await file.read()
    links = _ReceiptLinks(
        object_id=object_id, business_card_id=business_card_id, comment=comment, category_ids=category_ids,
        auto_categorize=auto_categorize, payment_method=payment_method, from_user_id=from_user_id,
        for_user_id=for_user_id, hashtags=hashtags,
    )
    return build_service(supply_db, auth_db, reference_db).create_from_photo(
        file_bytes, file.filename or "receipt.jpg", file.content_type or "", links, _session.user_id
    )


@purchase_receipts_router.get("/{receipt_id}", summary="Получить чек")
def get_receipt(
    receipt_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_id(receipt_id, _session.user_id)


@purchase_receipts_router.patch(
    "/{receipt_id}",
    summary="Изменить привязки чека: объект, бизнес-карта, категории, комментарий",
    description="object_id / business_card_id = null снимают привязку; category_ids заменяет весь набор категорий. Нужны права владельца или edit.",
)
def update_receipt(
    receipt_id: str,
    payload: PurchaseReceiptUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update(receipt_id, payload, _session.user_id)


@purchase_receipts_router.delete(
    "/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить чек (только владелец)"
)
def delete_receipt(
    receipt_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete(receipt_id, _session.user_id)
    return None


@purchase_receipts_router.post("/{receipt_id}/categories", summary="Добавить чеку товарные категории")
def add_receipt_categories(
    receipt_id: str,
    payload: PurchaseReceiptCategoriesAdd,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).add_categories(receipt_id, payload, _session.user_id)


@purchase_receipts_router.delete("/{receipt_id}/categories/{category_id}", summary="Убрать у чека товарную категорию")
def remove_receipt_category(
    receipt_id: str,
    category_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).remove_category(receipt_id, category_id, _session.user_id)


@purchase_receipts_router.post(
    "/{receipt_id}/files",
    status_code=status.HTTP_201_CREATED,
    summary="Прикрепить к чеку фотографии/сканы (можно несколько за раз)",
    description=(
        "multipart/form-data, поле `files` можно повторять. Допустимо: jpg, jpeg, png, webp, heic, heif, gif, pdf; "
        "до 15 МБ каждый, всего до 20 файлов на чек. Всё или ничего: если один файл не подошёл, не сохраняется ни один. "
        "Нужны права владельца или edit. Возвращает чек со списком `files`."
    ),
)
async def add_receipt_files(
    receipt_id: str,
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    uploads = [
        {"original_name": f.filename or "file", "mime_type": f.content_type or "", "file_bytes": await f.read()} for f in files
    ]
    return build_service(supply_db, auth_db, reference_db).add_files(receipt_id, uploads, _session.user_id)


@purchase_receipts_router.get("/{receipt_id}/files/{file_id}", summary="Скачать/открыть фото чека")
def download_receipt_file(
    receipt_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    payload = build_service(supply_db, auth_db, reference_db).get_file_for_download(receipt_id, file_id, _session.user_id)
    return FileResponse(path=payload["path"], filename=payload["filename"], media_type=payload["media_type"],
                        content_disposition_type="inline")


@purchase_receipts_router.delete("/{receipt_id}/files/{file_id}", summary="Удалить фото чека (файл удаляется с диска)")
def delete_receipt_file(
    receipt_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).delete_file(receipt_id, file_id, _session.user_id)


@purchase_receipts_router.get(
    "/{receipt_id}/comments",
    summary="Комментарии к чеку",
    description="Переписка по чеку, от старых к новым. Доступна всем, у кого есть доступ к чеку.",
)
def get_receipt_comments(
    receipt_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_comments(receipt_id, _session.user_id)


@purchase_receipts_router.post(
    "/{receipt_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Оставить комментарий к чеку",
    description="Комментарий может оставить любой, у кого есть доступ к чеку (в том числе только на просмотр).",
)
def add_receipt_comment(
    receipt_id: str,
    payload: PurchaseReceiptCommentCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).add_comment(receipt_id, payload, _session.user_id)


@purchase_receipts_router.patch(
    "/{receipt_id}/comments/{comment_id}",
    summary="Изменить свой комментарий",
)
def update_receipt_comment(
    receipt_id: str,
    comment_id: str,
    payload: PurchaseReceiptCommentUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_comment(receipt_id, comment_id, payload, _session.user_id)


@purchase_receipts_router.delete(
    "/{receipt_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить комментарий (автор или владелец чека)",
)
def delete_receipt_comment(
    receipt_id: str,
    comment_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_comment(receipt_id, comment_id, _session.user_id)
    return None


@purchase_receipts_router.get("/{receipt_id}/access", summary="Кому открыт доступ к чеку (только владелец)")
def get_receipt_access(
    receipt_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_access(receipt_id, _session.user_id)


@purchase_receipts_router.post(
    "/{receipt_id}/access",
    summary="Дать доступ к чеку пользователю (view — просмотр, edit — ещё и привязки)",
    description="Только владелец. Повторный вызов для того же пользователя меняет уровень доступа.",
)
def share_receipt(
    receipt_id: str,
    payload: PurchaseReceiptShare,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).share(receipt_id, payload, _session.user_id)


@purchase_receipts_router.delete(
    "/{receipt_id}/access/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Забрать доступ (владелец — у любого, пользователь — свой собственный)",
)
def unshare_receipt(
    receipt_id: str,
    user_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).unshare(receipt_id, user_id, _session.user_id)
    return None

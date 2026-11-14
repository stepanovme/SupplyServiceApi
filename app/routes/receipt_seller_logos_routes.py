from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.receipt_seller_logo import ReceiptSellerLogoSetUrl
from app.repositories.auth_user_repository import AuthUserRepository
from app.services.receipt_seller_logo_service import ReceiptSellerLogoService

receipt_seller_logos_router = APIRouter(prefix="/receipt-seller-logos", tags=["ReceiptSellerLogos"])


def build_service(supply_db: DbSupplySession, auth_db: DbAuthSession) -> ReceiptSellerLogoService:
    return ReceiptSellerLogoService(supply_db, AuthUserRepository(auth_db))


@receipt_seller_logos_router.get("", summary="Логотипы продавцов (поиск по ИНН или названию)")
def get_logos(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    search: str | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_list(search)


# literal paths must be registered before the /{inn} wildcards
@receipt_seller_logos_router.get(
    "/missing",
    summary="Продавцы из чеков, у которых ещё нет логотипа (только администратор)",
    description="Список ИНН с названием и количеством чеков, по убыванию — что стоит добавить в первую очередь.",
)
def get_missing_logos(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_missing(_session.user_id)


@receipt_seller_logos_router.get("/{inn}", summary="Логотип продавца по ИНН")
def get_logo(inn: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_by_inn(inn)


@receipt_seller_logos_router.get("/{inn}/image", summary="Файл загруженного логотипа")
def get_logo_image(inn: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    payload = build_service(supply_db, auth_db).get_image(inn)
    return FileResponse(path=payload["path"], media_type=payload["media_type"])


@receipt_seller_logos_router.put(
    "/{inn}",
    summary="Задать логотип продавца ссылкой на картинку (только администратор)",
    description="Создаёт запись или заменяет логотип; ранее загруженный файл удаляется.",
)
def set_logo_url(
    inn: str,
    payload: ReceiptSellerLogoSetUrl,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).set_url(inn, payload, _session.user_id)


@receipt_seller_logos_router.post(
    "/{inn}/upload",
    summary="Загрузить файл логотипа продавца (только администратор)",
    description="multipart/form-data: file (png, jpg, jpeg, webp, gif до 2 МБ) и необязательное seller_name.",
)
async def upload_logo(
    inn: str,
    file: Annotated[UploadFile, File(...)],
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    seller_name: str | None = Form(default=None),
    _session=Depends(get_session),
):
    data = await file.read()
    return build_service(supply_db, auth_db).upload(
        inn, data, file.filename or "", file.content_type or "", seller_name, _session.user_id
    )


@receipt_seller_logos_router.delete(
    "/{inn}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить логотип продавца (только администратор)"
)
def delete_logo(inn: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    build_service(supply_db, auth_db).delete(inn, _session.user_id)
    return None

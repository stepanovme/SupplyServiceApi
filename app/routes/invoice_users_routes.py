from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.invoice_user import InvoiceUserCreate, InvoiceUserUpdate
from app.repositories.invoice_user_repository import InvoiceUserRepository
from app.services.invoice_user_service import InvoiceUserService

invoice_users_router = APIRouter(prefix="/invoice-users", tags=["InvoiceUsers"])


@invoice_users_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список пользователей счетов",
)
def get_all_invoice_users(
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    return service.get_all()


@invoice_users_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить пользователя счета по ID",
)
def get_invoice_user_by_id(
    item_id: int,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    return service.get_by_id(item_id)


@invoice_users_router.get(
    "/by-invoice/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить пользователей счета по invoice_id",
)
def get_invoice_users_by_invoice(
    invoice_id: int,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    return service.repo.get_by_invoice_id(invoice_id)


@invoice_users_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя счета",
)
def create_invoice_user(
    data: InvoiceUserCreate,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    return service.create(data, created_by=session.user_id)


@invoice_users_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить пользователя счета",
)
def update_invoice_user(
    item_id: int,
    data: InvoiceUserUpdate,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    return service.update(item_id, data)


@invoice_users_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя счета",
)
def delete_invoice_user(
    item_id: int,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = InvoiceUserService(InvoiceUserRepository(db))
    service.delete(item_id)

from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.smtp import SmtpCreate, SmtpResponse, SmtpSecretResponse, SmtpUpdate
from app.repositories.smtp_repository import SmtpRepository
from app.services.smtp_service import SmtpService

smtp_router = APIRouter(prefix="/smtp", tags=["SMTP"])


def build_service(db: DbSupplySession) -> SmtpService:
    return SmtpService(SmtpRepository(db))


@smtp_router.get(
    "/by-user/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить SMTP настройки по user_id",
    response_model=list[SmtpResponse],
)
def get_smtp_by_user_id(
    user_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_by_user_id(user_id)


@smtp_router.get(
    "/by-user/{user_id}/secret",
    status_code=status.HTTP_200_OK,
    summary="Получить SMTP настройки с расшифрованным паролем по user_id",
    response_model=list[SmtpSecretResponse],
)
def get_smtp_secret_by_user_id(
    user_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_secret_by_user_id(user_id)


@smtp_router.get(
    "/{smtp_id}/secret",
    status_code=status.HTTP_200_OK,
    summary="Получить SMTP запись с расшифрованным паролем по id",
)
def get_smtp_secret_by_id(
    smtp_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_secret_by_id(smtp_id)


@smtp_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать SMTP настройки",
)
def create_smtp(
    payload: SmtpCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).create(payload)


@smtp_router.patch(
    "/{smtp_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить SMTP настройки",
)
def update_smtp(
    smtp_id: str,
    payload: SmtpUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).update(smtp_id, payload)


@smtp_router.delete(
    "/{smtp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить SMTP настройки",
)
def delete_smtp(
    smtp_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(db).delete(smtp_id)
    return None

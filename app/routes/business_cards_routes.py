from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.business_card import BusinessCardCreate, BusinessCardUpdate, FetchSberbankCardsRequest
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.business_card_service import BusinessCardService

business_cards_router = APIRouter(prefix="/business-cards", tags=["BusinessCards"])


def build_service(supply_db: DbSupplySession, reference_db: DbReferenceSession | None = None) -> BusinessCardService:
    return BusinessCardService(
        BusinessCardRepository(supply_db),
        SettingsApiBankRepository(supply_db),
        ExtractBusinessCardRepository(supply_db),
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


@business_cards_router.post(
    "/fetch-sberbank",
    status_code=status.HTTP_200_OK,
    summary="Загрузить бизнес-карты из Сбербанка (corporate-cards/list)",
    description=(
        "Тянет полный список карт по интеграции `settings_api_bank_id` (bank_type=sberbank), с "
        "постраничной подгрузкой. Карты сопоставляются с уже существующими по "
        "businessCardId — повторный вызов обновляет, а не дублирует записи."
    ),
)
def fetch_sberbank_cards(
    payload: FetchSberbankCardsRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).fetch_from_sberbank(payload.settings_api_bank_id, _session.user_id)


@business_cards_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список бизнес-карт",
)
def get_business_cards(
    supply_db: DbSupplySession,
    holder_user_id: str | None = Query(default=None),
    settings_api_bank_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_list(holder_user_id, settings_api_bank_id, is_active, limit, offset)


# literal paths must be registered before the /{card_id} wildcard
@business_cards_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Мои бизнес-карты (где я держатель)",
    description=(
        "Только карты, у которых holder_user_id равен текущему пользователю (берётся из сессии, "
        "передавать ничего не нужно). Фильтры: is_active, limit, offset. Чужие карты не возвращаются. "
        "Траты по своим картам: GET /business-cards/spending?holder_user_id=<мой id>."
    ),
)
def get_my_business_cards(
    supply_db: DbSupplySession,
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_list(_session.user_id, None, is_active, limit, offset)


@business_cards_router.get(
    "/spending",
    status_code=status.HTTP_200_OK,
    summary="Сколько потрачено по бизнес-карте(-ам)/держателям за период/всё время, с разбивкой по объектам",
    description=(
        "Без каких-либо фильтров — общая картина сразу по всем картам: единый `summary` "
        "(итог по всем картам вместе), `by_object` (разбивка по объектам, тоже по всем картам "
        "сразу), `by_holder` (разбивка по держателям — сгруппировано по `holder_user_id`, а если "
        "он не проставлен — по `holder_name`), `operations` (список самих операций — как в "
        "GET /extract-items, но уже отфильтрованных под выбранные карты/период) и `cards` (то же "
        "самое summary/by_object/operations, но по каждой карте отдельно). "
        "Через `holder_user_id`/`settings_api_bank_id`/`bank_type`/`is_active` можно сузить набор "
        "карт, через `card_id` (можно несколько раз — `?card_id=a&card_id=b`) — выбрать конкретные "
        "карты. Без `date_from`/`date_to` — за всё время. Учитывает возвраты: `direction=DEBIT` "
        "считается тратой, `CREDIT` — возвратом, `net_spent = total_debit - total_credit`. Операции "
        "без указанного объекта попадают в бакет `by_object` с `object_id: null`."
    ),
)
def get_business_cards_spending(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    card_id: list[str] | None = Query(default=None),
    holder_user_id: str | None = Query(default=None),
    settings_api_bank_id: str | None = Query(default=None),
    bank_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_spending(
        card_id, holder_user_id, settings_api_bank_id, bank_type, is_active, date_from, date_to
    )


@business_cards_router.get(
    "/{card_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить бизнес-карту по ID",
)
def get_business_card(
    card_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_id(card_id)


@business_cards_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать бизнес-карту вручную",
)
def create_business_card(
    payload: BusinessCardCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_manual(payload, _session.user_id)


@business_cards_router.patch(
    "/{card_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить бизнес-карту",
)
def update_business_card(
    card_id: str,
    payload: BusinessCardUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(card_id, payload)


@business_cards_router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить бизнес-карту",
)
def delete_business_card(
    card_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(card_id)
    return None

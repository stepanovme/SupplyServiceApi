from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.business_card import (
    ExtractBusinessCardCreate,
    ExtractBusinessCardMatchAllRequest,
    ExtractBusinessCardUpdate,
)
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.extract_business_card_service import ExtractBusinessCardService

extract_business_cards_router = APIRouter(prefix="/extract-business-cards", tags=["ExtractBusinessCards"])


def build_service(supply_db: DbSupplySession, reference_db: DbReferenceSession | None = None) -> ExtractBusinessCardService:
    return ExtractBusinessCardService(
        ExtractBusinessCardRepository(supply_db),
        BusinessCardRepository(supply_db),
        ExtractItemRepository(supply_db),
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


@extract_business_cards_router.post(
    "/match/{extract_id}",
    status_code=status.HTTP_200_OK,
    summary="Автосопоставить строку выписки с бизнес-картой по последним 4 цифрам номера карты",
    description=(
        "Ищет в paymentPurpose фрагмент «по карте <СХЕМА> <НОМЕР>» (например «по карте MIR "
        "220220BFAFB19498»), берёт последние 4 символа номера и ищет среди активных "
        "business_cards карту с таким же card_last4. Если карта одна — создаёт связь. Если "
        "карт с такими последними 4 цифрами несколько — не привязывает автоматически "
        "(`reason: ambiguous_match`, `candidates` — список id карт), выберите вручную через "
        "POST/PATCH. Если ссылки на карту в тексте нет вовсе — `reason: "
        "card_reference_not_found_in_text`."
    ),
)
def match_extract_item(
    extract_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).match_extract_item(extract_id, _session.user_id)


@extract_business_cards_router.post(
    "/match-all",
    status_code=status.HTTP_200_OK,
    summary="Пакетно сопоставить выбранные или ещё не привязанные строки extract_items с картами",
    description=(
        "Как и .../contract-extracts/match-all: либо `extract_ids: [...]` — обработать ровно эти "
        "строки, либо `date_from`/`date_to`/`limit` — взять до `limit` ещё не привязанных строк "
        "extract_items за период (по operationDate; период не обязателен)."
    ),
)
def match_all(
    payload: ExtractBusinessCardMatchAllRequest,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).match_all(payload, _session.user_id)


@extract_business_cards_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список связей выписка-карта",
)
def get_extract_business_cards(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    business_card_id: str | None = Query(default=None),
    extract_id: str | None = Query(default=None),
    object_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_list(business_card_id, extract_id, object_id, limit, offset)


@extract_business_cards_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Операции по бизнес-картам, привязанные к объекту",
    description=(
        "Все строки extract_items, у которых через extract_business_cards проставлен данный "
        "object_id (reference_service.objects.id) — то есть операции по бизнес-картам, отнесённые "
        "на этот объект. Возвращает short_name объекта, сводку (total_debit/total_credit/"
        "net_spent — с учётом возвратов) и список самих операций с данными карты по каждой. "
        "Без date_from/date_to — за всё время."
    ),
)
def get_extract_business_cards_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_by_object(object_id, date_from, date_to)


@extract_business_cards_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить связь по ID",
)
def get_extract_business_card(
    item_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_by_id(item_id)


@extract_business_cards_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Вручную связать строку выписки с бизнес-картой (и опционально с объектом)",
)
def create_extract_business_card(
    payload: ExtractBusinessCardCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).create_manual(payload, _session.user_id)


@extract_business_cards_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить связь (карту и/или объект)",
)
def update_extract_business_card(
    item_id: str,
    payload: ExtractBusinessCardUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).update_manual(item_id, payload)


@extract_business_cards_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связь",
)
def delete_extract_business_card(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(item_id)
    return None

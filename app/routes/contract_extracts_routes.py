from fastapi import APIRouter, Depends, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.contract_extract import (
    ContractExtractCreate,
    ContractExtractMatchAllRequest,
    ContractExtractUpdate,
)
from app.repositories.contract_extract_repository import ContractExtractRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.services.contract_extract_service import ContractExtractService

contract_extracts_router = APIRouter(prefix="/contract-extracts", tags=["ContractExtracts"])


def build_service(supply_db: DbSupplySession) -> ContractExtractService:
    return ContractExtractService(
        ContractExtractRepository(supply_db),
        ContractRepository(supply_db),
        ExtractItemRepository(supply_db),
    )


@contract_extracts_router.post(
    "/match/{extract_id}",
    status_code=status.HTTP_200_OK,
    summary="Определить через ИИ, платёж ли это по договору, и связать со строкой extract_items",
    description=(
        "По paymentPurpose строки extract_items определяет (через Mistral), относится ли платёж "
        "к оплате договора (а не счёта/акта/прочего), и если да — извлекает номер и дату договора, "
        "ищет договор в contracts по num+date и, если нашёл, создаёт запись в contract_extracts. "
        "Не находит — просто возвращает причину (`not_a_contract_payment`/`contract_not_found`), "
        "ничего не создаёт."
    ),
)
def match_extract_item(
    extract_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).match_extract_item(extract_id)


@contract_extracts_router.post(
    "/match-all",
    status_code=status.HTTP_200_OK,
    summary="Пакетно обработать выбранные или ещё не привязанные строки extract_items",
    description=(
        "Два режима, по телу запроса:\n"
        "1) `extract_ids: [...]` — обработать ровно эти строки (игнорирует date_from/date_to/limit). "
        "ID, которых нет в extract_items, попадают в `missing_extract_ids` в ответе.\n"
        "2) без `extract_ids` — берёт до `limit` строк extract_items за период "
        "`date_from`..`date_to` (по operationDate; оба поля опциональны — без них период не "
        "ограничен), у которых ещё нет записи в contract_extracts, и прогоняет через ИИ. "
        "Строки, которые ИИ не признал платежом по договору, или для которых договор не нашёлся в "
        "contracts, при повторном вызове будут обработаны заново (в таблице нет отдельного поля "
        "«уже проверено, но не найдено»)."
    ),
)
def match_all(
    payload: ContractExtractMatchAllRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).match_all(payload)


@contract_extracts_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список связей договор-выписка",
)
def get_contract_extracts(
    supply_db: DbSupplySession,
    contract_id: int | None = Query(default=None),
    extract_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_list(contract_id, extract_id, limit, offset)


@contract_extracts_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить связь по ID",
)
def get_contract_extract(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_id(item_id)


@contract_extracts_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Вручную связать строку выписки с договором",
)
def create_contract_extract(
    payload: ContractExtractCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_manual(payload)


@contract_extracts_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить договор в существующей связи",
)
def update_contract_extract(
    item_id: str,
    payload: ContractExtractUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_manual(item_id, payload)


@contract_extracts_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связь",
)
def delete_contract_extract(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(item_id)
    return None

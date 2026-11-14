from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.advance_report import (
    AdvanceReportCreate,
    AdvanceReportReceiptsAdd,
    AdvanceReportUpdate,
    OneCSendOptions,
)
from app.repositories.advance_report_repository import AdvanceReportRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.purchase_receipt_repository import PurchaseReceiptRepository
from app.services.advance_report_service import AdvanceReportService

advance_reports_router = APIRouter(prefix="/advance-reports", tags=["AdvanceReports"])


def build_service(supply_db: DbSupplySession, auth_db: DbAuthSession) -> AdvanceReportService:
    return AdvanceReportService(
        AdvanceReportRepository(supply_db), PurchaseReceiptRepository(supply_db), AuthUserRepository(auth_db)
    )


@advance_reports_router.get("", summary="Мои авансовые отчёты")
def get_reports(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    status_filter: Literal["draft", "sent"] | None = Query(default=None, alias="status", description="draft — собран, в 1С не отправлен; sent — создан в 1С"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_list(_session.user_id, status_filter, limit, offset)


@advance_reports_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать авансовый отчёт из выбранных чеков (и, по желанию, сразу отправить в 1С)",
    description=(
        "Тело: `receipt_ids` (чеки, которые вам доступны; только покупки; чек входит максимум в один отчёт), "
        "необязательные `title`, `report_date`, `comment`, `person_user_id`. Если указан блок `one_c` "
        "(`profile_id`, `organization_ref_key`, `person_ref_key`, …), отчёт сразу уходит в 1С черновиком «Авансовый отчёт» "
        "(раздел «Товары») — отправка доступна администратору. Отчёт сохраняется у нас в любом случае; если 1С не приняла "
        "документ, в ответе `one_c_send.status = failed` с причиной, и отправку можно повторить через `/send-to-1c`."
    ),
)
def create_report(
    payload: AdvanceReportCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)
):
    return build_service(supply_db, auth_db).create(payload, _session.user_id)


# literal paths must be registered before the /{report_id} wildcards
@advance_reports_router.get("/1c/profiles", summary="Профили 1С, через которые можно отправить отчёт (администратор)")
def get_one_c_profiles(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_profiles(_session.user_id)


@advance_reports_router.get(
    "/1c/profiles/{profile_id}/options",
    summary="Организации и физические лица выбранной базы 1С (для выбора при отправке)",
    description="Запрашивает справочники прямо из 1С; `search` — фильтр физических лиц по части ФИО.",
)
def get_one_c_options(
    profile_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    search: str | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_options(profile_id, _session.user_id, search)


@advance_reports_router.get("/{report_id}", summary="Авансовый отчёт с чеками")
def get_report(report_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_by_id(report_id, _session.user_id)


@advance_reports_router.patch("/{report_id}", summary="Изменить реквизиты отчёта (пока он не отправлен в 1С)")
def update_report(
    report_id: str,
    payload: AdvanceReportUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update(report_id, payload, _session.user_id)


@advance_reports_router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить отчёт (чеки остаются; отправленный в 1С удалить нельзя)",
)
def delete_report(report_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    build_service(supply_db, auth_db).delete(report_id, _session.user_id)
    return None


@advance_reports_router.post("/{report_id}/receipts", summary="Добавить чеки в отчёт (пока он не отправлен в 1С)")
def add_report_receipts(
    report_id: str,
    payload: AdvanceReportReceiptsAdd,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).add_receipts(report_id, payload, _session.user_id)


@advance_reports_router.delete("/{report_id}/receipts/{receipt_id}", summary="Убрать чек из отчёта (пока он не отправлен в 1С)")
def remove_report_receipt(
    report_id: str, receipt_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)
):
    return build_service(supply_db, auth_db).remove_receipt(report_id, receipt_id, _session.user_id)


@advance_reports_router.post(
    "/{report_id}/send-to-1c",
    summary="Отправить отчёт в 1С через выбранный профиль (черновик «Авансовый отчёт», раздел «Товары»)",
    description=(
        "Только администратор, только неотправленный отчёт (повторная отправка — 409, чтобы не создать документ в 1С дважды). "
        "Режим подбора номенклатуры `nomenclature_mode`: match (по точному названию; по умолчанию для рабочих баз), "
        "create (создавать недостающую — только в тестовых профилях), generic (одна общая номенклатура). "
        "Документ создаётся непроведённым."
    ),
)
def send_report_to_1c(
    report_id: str,
    payload: OneCSendOptions,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).send_to_1c(report_id, payload, _session.user_id)

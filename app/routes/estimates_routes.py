from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.estimate import (
    EstimateCreate, EstimateKind, EstimateStatus, ResourceType, SaveToCatalog, EstimateUpdate, PeriodCreate, PeriodUpdate, ResourceCreate, ResourceUpdate,
    SectionCreate, SectionUpdate, WorkCreate, WorkUpdate,
)
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.estimate_export_service import EstimateExportService
from app.services.estimate_service import EstimateService

estimates_router = APIRouter(prefix="/estimates", tags=["Estimates"])


def build_service(supply_db, reference_db) -> EstimateService:
    return EstimateService(supply_db, ReferenceObjectRepository(reference_db))


# --- static paths first ---
@estimates_router.get("/meta", summary="Статусы смет и виды ресурсов")
def get_meta(_session=Depends(get_session)):
    return EstimateService.get_meta()


@estimates_router.get("/contractor-contracts", summary="Договоры подрядчика из реестра договоров (для выбора)")
def list_contracts(contractor_id: str, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).list_contracts(contractor_id)


@estimates_router.get("/", include_in_schema=False)
@estimates_router.get("", summary="Список смет")
def list_estimates(supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
                   status_filter: EstimateStatus | None = Query(default=None, alias="status"), object_id: str | None = Query(default=None),
                   kind: EstimateKind | None = Query(default=None, description="main - основные, contractor - сметы подрядчиков"),
                   executor_id: str | None = Query(default=None, description="Только сметы этого подрядчика")):
    return build_service(supply_db, reference_db).list_estimates(status_filter, object_id, kind, executor_id)


@estimates_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@estimates_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать смету")
def create_estimate(payload: EstimateCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).create_estimate(payload, str(_session.user_id))


# sections / works / periods / resources by their own id
@estimates_router.patch("/sections/{section_id}", summary="Изменить раздел / переместить")
def update_section(section_id: int, payload: SectionUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_section(section_id, payload)


@estimates_router.delete("/sections/{section_id}", summary="Удалить раздел (с работами и ресурсами)")
def delete_section(section_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).delete_section(section_id)


@estimates_router.post("/sections/{section_id}/works", status_code=status.HTTP_201_CREATED, summary="Добавить работу в раздел")
def create_work(section_id: int, payload: WorkCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).create_work(section_id, payload)


@estimates_router.patch("/works/{work_id}", summary="Изменить работу / переместить")
def update_work(work_id: int, payload: WorkUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_work(work_id, payload)


@estimates_router.delete("/works/{work_id}", summary="Удалить работу")
def delete_work(work_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).delete_work(work_id)


@estimates_router.post("/works/{work_id}/periods", status_code=status.HTTP_201_CREATED, summary="Добавить период графика работы")
def add_period(work_id: int, payload: PeriodCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).add_period(work_id, payload)


@estimates_router.patch("/periods/{period_id}", summary="Изменить период графика")
def update_period(period_id: int, payload: PeriodUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_period(period_id, payload)


@estimates_router.delete("/periods/{period_id}", summary="Удалить период графика")
def delete_period(period_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).delete_period(period_id)


@estimates_router.post("/works/{work_id}/save-to-catalog", status_code=status.HTTP_201_CREATED, summary="Сохранить работу сметы в справочник работ")
def save_work_to_catalog(work_id: int, payload: SaveToCatalog, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).save_work_to_catalog(work_id, payload, str(_session.user_id))


@estimates_router.post("/resources/{resource_id}/save-to-catalog", status_code=status.HTTP_201_CREATED, summary="Сохранить ресурс сметы в справочник ресурсов")
def save_resource_to_catalog(resource_id: int, payload: SaveToCatalog, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).save_resource_to_catalog(resource_id, payload, str(_session.user_id))


@estimates_router.post("/works/{work_id}/resources", status_code=status.HTTP_201_CREATED, summary="Добавить ресурс в работу")
def create_resource(work_id: int, payload: ResourceCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).create_resource(work_id, payload)


@estimates_router.patch("/resources/{resource_id}", summary="Изменить ресурс")
def update_resource(resource_id: int, payload: ResourceUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_resource(resource_id, payload)


@estimates_router.delete("/resources/{resource_id}", summary="Удалить ресурс")
def delete_resource(resource_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).delete_resource(resource_id)


# the estimate itself
@estimates_router.get("/{estimate_id}", summary="Смета целиком: разделы, работы, ресурсы, итоги")
def get_estimate(estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).get_estimate(estimate_id)


@estimates_router.get("/{estimate_id}/schedule", summary="График работ сметы (плоский список периодов)")
def get_schedule(estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).get_schedule(estimate_id)


@estimates_router.patch("/{estimate_id}", summary="Изменить смету (название, статус, объект)")
def update_estimate(estimate_id: int, payload: EstimateUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_estimate(estimate_id, payload, str(_session.user_id))


@estimates_router.post("/{estimate_id}/approve", summary="Утвердить смету подрядчика (после этого по ней можно создавать акты)")
def approve_estimate(estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).approve(estimate_id, str(_session.user_id))


@estimates_router.post("/{estimate_id}/unapprove", summary="Снять утверждение сметы подрядчика")
def unapprove_estimate(estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).unapprove(estimate_id, str(_session.user_id))


@estimates_router.delete("/{estimate_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить смету")
def delete_estimate(estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(supply_db, reference_db).delete_estimate(estimate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@estimates_router.post("/{estimate_id}/sections", status_code=status.HTTP_201_CREATED, summary="Добавить раздел")
def create_section(estimate_id: int, payload: SectionCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).create_section(estimate_id, payload)


@estimates_router.get("/{estimate_id}/export/customer", summary="Скачать смету для заказчика (xlsx, только цены заказчика)")
def export_customer(
    estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
    include_works: bool = Query(default=True, description="Показывать строки работ"),
    include_resources: bool = Query(default=True, description="Показывать строки ресурсов"),
    resource_types: list[ResourceType] | None = Query(default=None, description="Какие виды ресурсов учитывать (повторяемый параметр); по умолчанию все. Влияет и на суммы"),
):
    content, filename = EstimateExportService(supply_db, ReferenceObjectRepository(reference_db)).customer_xlsx(
        estimate_id, include_works, include_resources, resource_types,
    )
    return Response(
        content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

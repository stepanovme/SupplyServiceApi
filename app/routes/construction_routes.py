from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.estimate import ProgressCreate, ProgressUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.construction_service import ConstructionService

construction_router = APIRouter(prefix="/construction", tags=["Construction"])


def build_service(supply_db, reference_db, auth_db) -> ConstructionService:
    return ConstructionService(supply_db, ReferenceObjectRepository(reference_db), AuthUserRepository(auth_db))


@construction_router.get("/works", summary="Стройка - работы: работы смет, график, подрядчики, прогресс")
def list_works(
    supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session),
    estimate_id: int | None = Query(default=None), object_id: str | None = Query(default=None),
    estimate_status: Literal["draft", "planning", "in_progress", "completed", "all"] = Query(default="in_progress", description="Статус сметы; all - любые"),
    contractor_id: str | None = Query(default=None), search: str | None = Query(default=None),
    state: Literal["not_started", "in_progress", "completed", "overdue"] | None = Query(default=None, description="Не начата / в работе / выполнена / просрочена"),
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
):
    return build_service(supply_db, reference_db, auth_db).list_works(estimate_id, object_id, estimate_status, contractor_id, search, state, limit, offset)


@construction_router.get("/estimates/{estimate_id}/journal", summary="Журнал работ: все записи выполнения по всем работам сметы")
def get_journal(
    estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session),
    date_from: date | None = Query(default=None), date_to: date | None = Query(default=None),
    contractor_id: str | None = Query(default=None), work_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
):
    return build_service(supply_db, reference_db, auth_db).get_journal(estimate_id, date_from, date_to, contractor_id, work_id, limit, offset)


@construction_router.get("/works/{work_id}", summary="Работа: график, подрядчики, ресурсы и история выполнения")
def get_work(work_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db, auth_db).get_work(work_id)


@construction_router.post("/works/{work_id}/progress", status_code=status.HTTP_201_CREATED, summary="Отметить выполненный объём за день")
def add_progress(work_id: int, payload: ProgressCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db, auth_db).add_progress(work_id, payload, str(_session.user_id))


@construction_router.patch("/progress/{progress_id}", summary="Исправить запись выполнения")
def update_progress(progress_id: int, payload: ProgressUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db, auth_db).update_progress(progress_id, payload, str(_session.user_id))


@construction_router.delete("/progress/{progress_id}", summary="Удалить запись выполнения")
def delete_progress(progress_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db, auth_db).delete_progress(progress_id)

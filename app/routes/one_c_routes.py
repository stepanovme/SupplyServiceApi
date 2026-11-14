from app.middleware.auth_middleware import get_session_token
import logging
import os
import threading
from contextvars import copy_context
import traceback
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Query, status

from app.database import DbSupplySession, ReferenceSessionLocal, SupplySessionLocal

logger = logging.getLogger(__name__)

SYNC_LOG_DIR = os.getenv("SYNC_LOG_DIR", "/home/webserver/models/supply/logs/sync")
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.one_c import (
    OneCOrganizationCreate,
    OneCOrganizationUpdate,
    OneCProfileCreate,
    OneCProfileUpdate,
    OneCSyncRequest,
)
from app.repositories.invoice_outgoing_repository import InvoiceOutgoingRepository
from app.repositories.one_c_repository import OneCRepository
from app.services.one_c_service import OneCService
from app.services.one_c_sync_service import OneCSyncService

one_c_router = APIRouter(prefix="/1c", tags=["1C"])


def build_one_c_service(
    supply_db: DbSupplySession,
) -> OneCService:
    return OneCService(OneCRepository(supply_db))


@one_c_router.get(
    "/profiles",
    status_code=status.HTTP_200_OK,
    summary="Получить список профилей 1С",
)
def get_one_c_profiles(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.get_profiles()


@one_c_router.get(
    "/profiles/{profile_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить профиль 1С",
)
def get_one_c_profile(
    profile_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.get_profile(profile_id)


@one_c_router.post(
    "/profiles",
    status_code=status.HTTP_201_CREATED,
    summary="Создать профиль 1С",
)
def create_one_c_profile(
    payload: OneCProfileCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.create_profile(payload, str(session.user_id))


@one_c_router.patch(
    "/profiles/{profile_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить профиль 1С",
)
def update_one_c_profile(
    profile_id: int,
    payload: OneCProfileUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.update_profile(profile_id, payload)


@one_c_router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить профиль 1С",
)
def delete_one_c_profile(
    profile_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    service.delete_profile(profile_id)
    return None


@one_c_router.get(
    "/organizations",
    status_code=status.HTTP_200_OK,
    summary="Получить список организаций 1С",
)
def get_one_c_organizations(
    supply_db: DbSupplySession,
    profile_id: int | None = Query(default=None, description="Фильтр по профилю 1С"),
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.get_organizations(profile_id)


@one_c_router.get(
    "/organizations/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить организацию 1С",
)
def get_one_c_organization(
    org_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.get_organization(org_id)


@one_c_router.post(
    "/organizations",
    status_code=status.HTTP_201_CREATED,
    summary="Создать организацию 1С",
)
def create_one_c_organization(
    payload: OneCOrganizationCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.create_organization(payload, str(session.user_id))


@one_c_router.patch(
    "/organizations/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить организацию 1С",
)
def update_one_c_organization(
    org_id: int,
    payload: OneCOrganizationUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    return service.update_organization(org_id, payload)


@one_c_router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить организацию 1С",
)
def delete_one_c_organization(
    org_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_one_c_service(supply_db)
    service.delete_organization(org_id)
    return None


@one_c_router.post(
    "/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Синхронизировать данные из 1С",
)
def sync_one_c(
    payload: OneCSyncRequest,
    session_token: str | None = Depends(get_session_token),
):
    def _write_sync_log(result: dict, profile_label: str | None = None, fatal_error: str | None = None):
        try:
            os.makedirs(SYNC_LOG_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sync_{timestamp}.log"
            filepath = os.path.join(SYNC_LOG_DIR, filename)
            with open(filepath, "w") as f:
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Profile: {profile_label or 'N/A'}\n")
                f.write(f"\n--- Result ---\n")
                f.write(f"Units created: {result.get('units_created', 0)}\n")
                f.write(f"Units updated: {result.get('units_updated', 0)}\n")
                f.write(f"Nomenclatures created: {result.get('nomenclatures_created', 0)}\n")
                f.write(f"Nomenclatures updated: {result.get('nomenclatures_updated', 0)}\n")
                f.write(f"Invoices created: {result.get('invoices_created', 0)}\n")
                f.write(f"Invoices updated: {result.get('invoices_updated', 0)}\n")
                f.write(f"Counterparties created: {result.get('counterparties_created', 0)}\n")
                if result.get("errors"):
                    f.write(f"\n--- Errors ({len(result['errors'])}) ---\n")
                    for err in result["errors"]:
                        f.write(f"{err}\n")
                if fatal_error:
                    f.write(f"\n--- Fatal Error ---\n")
                    f.write(f"{fatal_error}\n")
            logger.info(f"Sync log written to {filepath}")
        except Exception as e:
            logger.error(f"Failed to write sync log: {e}")

    def _run():
        supply_db = SupplySessionLocal()
        reference_db = ReferenceSessionLocal()
        try:
            sync_service = OneCSyncService(
                OneCRepository(supply_db),
                InvoiceOutgoingRepository(supply_db),
                reference_db,
                session_token=session_token,
            )
            result = sync_service.sync(
                profile_ids=payload.profile_ids,
                organization_ref_keys=payload.organization_ref_keys,
                date_from=payload.date_from,
                date_to=payload.date_to,
            )
            logger.info(
                "Sync completed: "
                f"units: {result['units_created']} created, {result['units_updated']} updated | "
                f"nomenclatures: {result['nomenclatures_created']} created, {result['nomenclatures_updated']} updated | "
                f"invoices: {result['invoices_created']} created, {result['invoices_updated']} updated | "
                f"counterparties: {result['counterparties_created']} created | "
                f"errors: {len(result['errors'])}"
            )
            if result["errors"]:
                logger.error(f"Sync errors: {'; '.join(result['errors'][:10])}")
            _write_sync_log(result)
        except Exception:
            logger.exception("Sync failed with unhandled exception")
            _write_sync_log({}, fatal_error=traceback.format_exc())
        finally:
            supply_db.close()
            reference_db.close()

    threading.Thread(target=copy_context().run, args=(_run,), daemon=True).start()
    return {"status": "started", "message": "Синхронизация запущена в фоне"}

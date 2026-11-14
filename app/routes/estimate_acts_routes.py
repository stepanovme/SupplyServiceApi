from datetime import date

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.estimate import ActCreate, ActUpdate
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.estimate_act_service import EstimateActService
from app.services.ks2_service import Ks2Service

estimate_acts_router = APIRouter(prefix="/estimates", tags=["Estimate acts"])


def build_service(supply_db, reference_db) -> EstimateActService:
    return EstimateActService(supply_db, ReferenceObjectRepository(reference_db))


@estimate_acts_router.get("/acts/{act_id}", summary="Акт: состав, суммы, статус подписи")
def get_act(act_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).get_act(act_id)


@estimate_acts_router.get("/acts/{act_id}/ks2", summary="Скачать акт в форме КС-2 (xlsx)")
def download_ks2(
    act_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
    contract_id: int | None = Query(default=None, description="Договор из реестра для полей «договор подряда»; у акта с подрядчиком берётся из его расценки"),
):
    content, filename = Ks2Service(supply_db, ReferenceObjectRepository(reference_db)).build(act_id, contract_id)
    return Response(
        content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@estimate_acts_router.patch("/acts/{act_id}", summary="Изменить дату / период / состав акта")
def update_act(act_id: int, payload: ActUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).update_act(act_id, payload, str(_session.user_id))


@estimate_acts_router.delete("/acts/{act_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить неподписанный акт")
def delete_act(act_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(supply_db, reference_db).delete_act(act_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@estimate_acts_router.post("/acts/{act_id}/sign", summary="Подписать акт")
def sign_act(act_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).sign(act_id, str(_session.user_id))


@estimate_acts_router.post("/acts/{act_id}/unsign", summary="Снять подпись")
def unsign_act(act_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).unsign(act_id, str(_session.user_id))


@estimate_acts_router.get("/{estimate_id}/acts/preview", summary="Какие работы и сколько можно закрыть за период")
def preview_act(
    estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
    date_from: date = Query(), date_to: date = Query(),
    exclude_act_id: int | None = Query(default=None, description="При редактировании акта - не учитывать его самого"),
):
    return build_service(supply_db, reference_db).preview(estimate_id, date_from, date_to, exclude_act_id)


@estimate_acts_router.get("/{estimate_id}/acts", summary="Акты по смете")
def list_acts(
    estimate_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
    act_status: str | None = Query(default=None, alias="status", pattern="^(signed|unsigned)$"),
):
    return build_service(supply_db, reference_db).list_acts(estimate_id, act_status)


@estimate_acts_router.post("/{estimate_id}/acts", status_code=status.HTTP_201_CREATED, summary="Создать акт (номер присваивается автоматически)")
def create_act(estimate_id: int, payload: ActCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, reference_db).create_act(estimate_id, payload, str(_session.user_id))

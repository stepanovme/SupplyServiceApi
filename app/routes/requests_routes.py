from collections import defaultdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import RequestInvoiceLink, SupplyRequest, SupplyRequestCreate, RequestSplitRequest, SupplyRequestUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.object_setting_repository import ObjectSettingRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.request_repository import RequestRepository
from app.services.request_file_service import RequestFileService
from app.services.request_service import RequestService

requests_router = APIRouter(prefix="/requests", tags=["Requests"])


def build_request_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> RequestService:
    return RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
        ProjectUserRoleRepository(supply_db),
        ObjectSettingRepository(supply_db),
        DepartmentRepository(supply_db),
        supply_db,
    )


@requests_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список всех заявок",
)
def get_all_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.get_all()


@requests_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных мне заявок",
)
def get_my_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.get_available_for_user(str(session.user_id))


@requests_router.get(
    "/my/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить доступную мне заявку по id",
)
def get_my_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    item = service.get_available_for_user_by_id(str(session.user_id), request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item


@requests_router.get(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить заявку по id",
)
def get_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    item = service.get_by_id(request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item


@requests_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать заявку",
)
def create_request(
    payload: SupplyRequestCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.create(payload, str(session.user_id))


@requests_router.post(
    "/{request_id}/copy",
    status_code=status.HTTP_201_CREATED,
    summary="Копировать заявку",
)
def copy_request(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.copy(request_id, str(session.user_id))


@requests_router.post(
    "/{request_id}/split",
    status_code=status.HTTP_200_OK,
    summary="Разделить заявку на несколько",
)
def split_request(
    request_id: int,
    payload: RequestSplitRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.split(request_id, payload.model_dump(), str(session.user_id))


@requests_router.patch(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать заявку",
)
def update_request(
    request_id: int,
    payload: SupplyRequestUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.update(request_id, payload)


@requests_router.post(
    "/{request_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить файл-приложение к заявке",
)
async def upload_request_attachment(
    request_id: int,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = RequestFileService(RequestFileRepository(db))
    file_bytes = await file.read()
    return service.upload_request_attachment(
        request_id=request_id,
        original_name=file.filename or "file",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@requests_router.get(
    "/{request_id}/attachments",
    status_code=status.HTTP_200_OK,
    summary="Получить список файлов заявки",
)
def get_request_attachments(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    return service.get_request_files(request_id)


@requests_router.get(
    "/{request_id}/attachments/{file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать файл заявки",
)
def download_request_attachment(
    request_id: int,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    payload = service.get_download_file_payload(request_id, file_id, str(session.user_id))
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@requests_router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить заявку",
)
def delete_request(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    service.delete(request_id)
    return None


@requests_router.delete(
    "/{request_id}/attachments/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить файл заявки",
)
def delete_request_attachment(
    request_id: int,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    service.delete_request_file(request_id, file_id, str(session.user_id))
    return None


@requests_router.get(
    "/{request_id}/attachments/{file_id}/preview",
    status_code=status.HTTP_200_OK,
    summary="Предпросмотр файла заявки (PDF)",
)
def preview_request_attachment(
    request_id: int,
    file_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    file_path = service.get_preview(file_id)
    return FileResponse(file_path, media_type="application/pdf")


@requests_router.post(
    "/{request_id}/invoices",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить файл счета к заявке",
)
async def upload_request_invoice_file(
    request_id: int,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = RequestFileService(
        RequestFileRepository(db),
        RequestRepository(db),
        ProjectUserRoleRepository(db),
    )
    file_bytes = await file.read()
    return service.upload_request_invoice_file(
        request_id=request_id,
        original_name=file.filename or "file",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@requests_router.get(
    "/{request_id}/invoices",
    status_code=status.HTTP_200_OK,
    summary="Получить список файлов счетов заявки",
)
def get_request_invoice_files(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    return service.get_request_invoice_files(request_id)


@requests_router.post(
    "/{request_id}/attach-invoice/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Прикрепить существующий счёт к заявке",
)
def attach_invoice_to_request(
    request_id: int,
    invoice_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    from app.models.invoice import Invoice
    import uuid

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    request_row = db.query(SupplyRequest).filter(SupplyRequest.id == request_id).first()
    if not request_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    existing = (
        db.query(RequestInvoiceLink)
        .filter(RequestInvoiceLink.request_id == request_id, RequestInvoiceLink.invoice_id == invoice_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already attached to this request")

    link = RequestInvoiceLink(
        id=str(uuid.uuid4()),
        request_id=request_id,
        invoice_id=invoice_id,
        created_by=str(_session.user_id),
    )
    db.add(link)
    db.commit()

    return {"request_id": request_id, "invoice_id": invoice_id}


@requests_router.delete(
    "/{request_id}/detach-invoice/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Открепить счёт от заявки",
)
def detach_invoice_from_request(
    request_id: int,
    invoice_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    link = (
        db.query(RequestInvoiceLink)
        .filter(RequestInvoiceLink.request_id == request_id, RequestInvoiceLink.invoice_id == invoice_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()

    return {"request_id": request_id, "invoice_id": invoice_id, "detached": True}


@requests_router.get(
    "/{request_id}/linked-invoices",
    status_code=status.HTTP_200_OK,
    summary="Получить список привязанных счетов заявки",
)
def get_linked_invoices(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    from app.models.invoice import Invoice
    from app.repositories.request_repository import RequestRepository

    links = (
        db.query(RequestInvoiceLink)
        .filter(RequestInvoiceLink.request_id == request_id)
        .all()
    )
    if not links:
        return []

    invoice_ids = [link.invoice_id for link in links]
    invoices = db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
    invoices_by_id = {inv.id: inv for inv in invoices}

    result = []
    for link in links:
        inv = invoices_by_id.get(link.invoice_id)
        if not inv:
            continue
        result.append({
            "link_id": link.id,
            "invoice_id": inv.id,
            "num": inv.num,
            "date": inv.date,
            "provider_id": inv.provider_id,
            "payer_id": inv.payer_id,
            "status": inv.status,
            "total_amount": inv.total_amount,
            "created_by": link.created_by,
            "created_at": link.created_at,
        })

    return result


@requests_router.post(
    "/parse",
    status_code=status.HTTP_200_OK,
    summary="Распознать заявку из PDF/изображения (OCR + LLM)",
)
async def parse_request_from_file(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return await run_in_threadpool(
        service.parse_request_from_file,
        file_bytes,
        file.filename or "file.pdf",
    )


@requests_router.get(
    "/{request_id}/event-log",
    status_code=status.HTTP_200_OK,
    summary="Получить лог событий заявки",
)
def get_request_event_log(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    repo = RequestRepository(db)
    logs = repo.get_event_logs_by_request(request_id)
    return [
        {
            "id": log.id,
            "request_id": log.request_id,
            "user_id": log.user_id,
            "event_type": log.event_type,
            "description": log.description,
            "metadata_json": log.metadata_json,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@requests_router.get(
    "/{request_id}/item-snapshots",
    status_code=status.HTTP_200_OK,
    summary="Получить снимки количества по позициям заявки",
)
def get_request_item_snapshots(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    repo = RequestRepository(db)
    snapshots = repo.get_snapshots_by_request(request_id)
    items = repo.get_request_items_by_request(request_id)

    snaps_by_item = defaultdict(list)
    for s in snapshots:
        snaps_by_item[s.request_item_id].append(s)

    return [
        {
            "item_id": item.id,
            "name": item.name,
            "num": item.num,
            "is_new": getattr(item, "is_new", False),
            "current_quantity": float(item.quantity),
            "original_quantity": float(item_snaps[0].original_quantity) if item_snaps else float(item.quantity),
            "quantity_diff": float(item.quantity) - float(item_snaps[0].original_quantity if item_snaps else item.quantity),
            "snapshots": sorted(
                [
                    {
                        "id": s.id,
                        "original_quantity": s.original_quantity,
                        "snapshot_quantity": s.snapshot_quantity,
                        "quantity_diff": s.quantity_diff,
                        "created_by": s.created_by,
                        "created_at": s.created_at,
                    }
                    for s in item_snaps
                ],
                key=lambda x: x["created_at"],
            ),
        }
        for item in items
        for item_snaps in [snaps_by_item.get(item.id, [])]
    ]

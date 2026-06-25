from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.invoice_payment_file import InvoicePaymentFileUpdate
from app.models.session import SessionDB
from app.repositories.invoice_payment_file_repository import InvoicePaymentFileRepository
from app.services.invoice_payment_file_service import InvoicePaymentFileService

invoice_payment_files_router = APIRouter(prefix="/invoice-payment-files", tags=["InvoicePaymentFiles"])


def build_service(db: DbSupplySession) -> InvoicePaymentFileService:
    return InvoicePaymentFileService(InvoicePaymentFileRepository(db))


@invoice_payment_files_router.get("", status_code=status.HTTP_200_OK)
def get_payment_files(
    invoice_payment_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_by_payment_id(invoice_payment_id)


@invoice_payment_files_router.get("/{row_id}", status_code=status.HTTP_200_OK)
def get_payment_file(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    return build_service(db).get_by_id(row_id)


@invoice_payment_files_router.post("", status_code=status.HTTP_201_CREATED)
async def upload_payment_file(
    invoice_payment_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_service(db)
    file_bytes = await file.read()
    return service.upload(
        payment_id=invoice_payment_id,
        original_name=file.filename or "file",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@invoice_payment_files_router.patch("/{row_id}", status_code=status.HTTP_200_OK)
def update_payment_file(
    row_id: str,
    payload: InvoicePaymentFileUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).update(row_id, payload)


@invoice_payment_files_router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_file(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    build_service(db).delete(row_id)
    return None


@invoice_payment_files_router.get("/{row_id}/download", status_code=status.HTTP_200_OK)
def download_payment_file(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    file_path, filename = build_service(db).get_download(row_id)
    return FileResponse(file_path, filename=filename)

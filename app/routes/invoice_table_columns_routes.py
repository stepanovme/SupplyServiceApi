from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.invoice_table_column import InvoiceTableColumnBulkUpdate
from app.models.session import SessionDB
from app.repositories.invoice_table_column_repository import InvoiceTableColumnRepository
from app.services.invoice_table_column_service import InvoiceTableColumnService

invoice_table_columns_router = APIRouter(prefix="/invoice-table-columns", tags=["InvoiceTableColumns"])


def _service(db: DbSupplySession) -> InvoiceTableColumnService:
    return InvoiceTableColumnService(InvoiceTableColumnRepository(db))


@invoice_table_columns_router.get("", status_code=status.HTTP_200_OK, summary="Получить положение столбцов")
def get_columns(
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return _service(db).get_columns(str(session.user_id))


@invoice_table_columns_router.put("", status_code=status.HTTP_200_OK, summary="Обновить положение столбцов")
def update_columns(
    payload: InvoiceTableColumnBulkUpdate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return _service(db).update_columns(str(session.user_id), payload)

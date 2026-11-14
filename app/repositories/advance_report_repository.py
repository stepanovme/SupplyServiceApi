from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.advance_report import AdvanceReport, AdvanceReportReceipt
from app.models.purchase_receipt import PurchaseReceipt, PurchaseReceiptItem


class AdvanceReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, report_id: str) -> AdvanceReport | None:
        return self.db.query(AdvanceReport).filter(AdvanceReport.id == report_id).first()

    def get_list(self, user_id: str, status: str | None, limit: int, offset: int) -> list[AdvanceReport]:
        q = self.db.query(AdvanceReport).filter(AdvanceReport.created_by == user_id)
        if status:
            q = q.filter(AdvanceReport.status == status)
        return q.order_by(AdvanceReport.created_at.desc(), AdvanceReport.id.desc()).offset(offset).limit(limit).all()

    def get_links(self, report_ids: list[str]) -> list[AdvanceReportReceipt]:
        if not report_ids:
            return []
        return (
            self.db.query(AdvanceReportReceipt)
            .filter(AdvanceReportReceipt.report_id.in_(report_ids))
            .order_by(AdvanceReportReceipt.id)
            .all()
        )

    def get_link_by_receipt(self, receipt_id: str) -> AdvanceReportReceipt | None:
        return self.db.query(AdvanceReportReceipt).filter(AdvanceReportReceipt.receipt_id == receipt_id).first()

    def get_links_by_receipts(self, receipt_ids: list[str]) -> dict[str, tuple[str, str, int | None]]:
        """receipt_id -> (report_id, report status, report number) for receipts that are in a report."""
        if not receipt_ids:
            return {}
        rows = (
            self.db.query(AdvanceReportReceipt.receipt_id, AdvanceReport.id, AdvanceReport.status, AdvanceReport.number)
            .join(AdvanceReport, AdvanceReport.id == AdvanceReportReceipt.report_id)
            .filter(AdvanceReportReceipt.receipt_id.in_(receipt_ids))
            .all()
        )
        return {rid: (report_id, status, number) for rid, report_id, status, number in rows}

    def get_receipts(self, receipt_ids: list[str]) -> list[PurchaseReceipt]:
        if not receipt_ids:
            return []
        return self.db.query(PurchaseReceipt).filter(PurchaseReceipt.id.in_(receipt_ids)).all()

    def get_items(self, receipt_ids: list[str]) -> list[PurchaseReceiptItem]:
        if not receipt_ids:
            return []
        return (
            self.db.query(PurchaseReceiptItem)
            .filter(PurchaseReceiptItem.receipt_id.in_(receipt_ids))
            .order_by(PurchaseReceiptItem.receipt_id, PurchaseReceiptItem.position)
            .all()
        )

    def get_profile(self, profile_id: int):
        return self.db.execute(
            text("SELECT id, name, username, password, api_link, is_test FROM `1c_profiles` WHERE id = :i"), {"i": profile_id}
        ).first()

    def get_profiles(self):
        return self.db.execute(text("SELECT id, name, api_link, is_test FROM `1c_profiles` ORDER BY id")).fetchall()

    def add(self, row) -> None:
        self.db.add(row)

    def delete(self, row) -> None:
        self.db.delete(row)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, row) -> None:
        self.db.refresh(row)

from datetime import datetime

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.purchase_receipt import (
    PurchaseReceipt,
    PurchaseReceiptAccess,
    PurchaseReceiptCategory,
    PurchaseReceiptComment,
    PurchaseReceiptFile,
    PurchaseReceiptHashtag,
    PurchaseReceiptItem,
)
from app.models.advance_report import AdvanceReport, AdvanceReportReceipt
from app.models.receipt_category import ReceiptCategory
from app.models.receipt_seller_logo import ReceiptSellerLogo


class PurchaseReceiptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- receipts ---------------------------------------------------------------------------
    def get_by_id(self, receipt_id: str) -> PurchaseReceipt | None:
        return self.db.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()

    def get_by_ids(self, receipt_ids: list[str]) -> list[PurchaseReceipt]:
        if not receipt_ids:
            return []
        return self.db.query(PurchaseReceipt).filter(PurchaseReceipt.id.in_(receipt_ids)).all()

    def get_access_for_user(self, receipt_ids: list[str], user_id: str) -> dict[str, str]:
        """receipt_id -> access_level for the receipts shared with the user."""
        if not receipt_ids:
            return {}
        rows = (
            self.db.query(PurchaseReceiptAccess.receipt_id, PurchaseReceiptAccess.access_level)
            .filter(PurchaseReceiptAccess.receipt_id.in_(receipt_ids), PurchaseReceiptAccess.user_id == user_id)
            .all()
        )
        return {rid: level for rid, level in rows}

    def find_by_fiscal(self, fn: str, fd: str, fp: str) -> PurchaseReceipt | None:
        return (
            self.db.query(PurchaseReceipt)
            .filter(PurchaseReceipt.fn == fn, PurchaseReceipt.fd == fd, PurchaseReceipt.fp == fp)
            .first()
        )

    def get_list(
        self,
        user_id: str,
        scope: str = "all",
        object_id: str | None = None,
        business_card_id: str | None = None,
        category_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        unbounded: bool = False,
        payment_method: str | None = None,
        hashtag: str | None = None,
        from_user_id: str | None = None,
        for_user_id: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> list[PurchaseReceipt]:
        """Receipts the user may see: their own plus the ones shared with them.

        By default the newest ADDED receipts come first (created_at desc), not the newest by the
        date on the receipt; sort_by="purchased_at" gives the receipt-date order."""
        shared_ids = self.db.query(PurchaseReceiptAccess.receipt_id).filter(PurchaseReceiptAccess.user_id == user_id)
        q = self.db.query(PurchaseReceipt)
        if scope == "mine":
            q = q.filter(PurchaseReceipt.created_by == user_id)
        elif scope == "shared":
            q = q.filter(PurchaseReceipt.id.in_(shared_ids))
        else:
            q = q.filter(or_(PurchaseReceipt.created_by == user_id, PurchaseReceipt.id.in_(shared_ids)))
        if object_id is not None:
            q = q.filter(PurchaseReceipt.object_id == object_id)
        if business_card_id is not None:
            q = q.filter(PurchaseReceipt.business_card_id == business_card_id)
        if category_id is not None:
            q = q.filter(
                PurchaseReceipt.id.in_(
                    self.db.query(PurchaseReceiptCategory.receipt_id).filter(PurchaseReceiptCategory.category_id == category_id)
                )
            )
        if payment_method is not None:
            q = q.filter(PurchaseReceipt.payment_method == payment_method)
        if from_user_id is not None:
            q = q.filter(PurchaseReceipt.from_user_id == from_user_id)
        if for_user_id is not None:
            q = q.filter(PurchaseReceipt.for_user_id == for_user_id)
        if hashtag is not None:
            q = q.filter(
                PurchaseReceipt.id.in_(
                    self.db.query(PurchaseReceiptHashtag.receipt_id).filter(PurchaseReceiptHashtag.tag == hashtag)
                )
            )
        if date_from is not None:
            q = q.filter(PurchaseReceipt.purchased_at >= date_from)
        if date_to is not None:
            q = q.filter(PurchaseReceipt.purchased_at <= date_to)
        primary = PurchaseReceipt.purchased_at if sort_by == "purchased_at" else PurchaseReceipt.created_at
        direction = (lambda col: col.asc()) if order == "asc" else (lambda col: col.desc())
        # id breaks ties between receipts added within the same second, so pages never reshuffle
        q = q.order_by(direction(primary), direction(PurchaseReceipt.created_at), direction(PurchaseReceipt.id))
        return q.all() if unbounded else q.offset(offset).limit(limit).all()

    # --- hashtags -----------------------------------------------------------------------------
    def get_hashtags(self, receipt_ids: list[str]) -> list[PurchaseReceiptHashtag]:
        if not receipt_ids:
            return []
        return (
            self.db.query(PurchaseReceiptHashtag)
            .filter(PurchaseReceiptHashtag.receipt_id.in_(receipt_ids))
            .order_by(PurchaseReceiptHashtag.tag)
            .all()
        )

    def get_hashtag_stats(self, user_id: str, scope: str = "all") -> list[tuple[str, int]]:
        """(tag, receipts count) over the receipts the user can see, most used first."""
        shared_ids = self.db.query(PurchaseReceiptAccess.receipt_id).filter(PurchaseReceiptAccess.user_id == user_id)
        q = self.db.query(PurchaseReceiptHashtag.tag, func.count(PurchaseReceiptHashtag.receipt_id)).join(
            PurchaseReceipt, PurchaseReceipt.id == PurchaseReceiptHashtag.receipt_id
        )
        if scope == "mine":
            q = q.filter(PurchaseReceipt.created_by == user_id)
        elif scope == "shared":
            q = q.filter(PurchaseReceipt.id.in_(shared_ids))
        else:
            q = q.filter(or_(PurchaseReceipt.created_by == user_id, PurchaseReceipt.id.in_(shared_ids)))
        rows = (
            q.group_by(PurchaseReceiptHashtag.tag)
            .order_by(func.count(PurchaseReceiptHashtag.receipt_id).desc(), PurchaseReceiptHashtag.tag)
            .all()
        )
        return [(tag, int(count)) for tag, count in rows]

    # --- comments -----------------------------------------------------------------------------
    def get_comments(self, receipt_id: str) -> list[PurchaseReceiptComment]:
        return (
            self.db.query(PurchaseReceiptComment)
            .filter(PurchaseReceiptComment.receipt_id == receipt_id)
            .order_by(PurchaseReceiptComment.created_at, PurchaseReceiptComment.id)
            .all()
        )

    def get_comment_counts(self, receipt_ids: list[str]) -> dict[str, int]:
        if not receipt_ids:
            return {}
        rows = (
            self.db.query(PurchaseReceiptComment.receipt_id, func.count(PurchaseReceiptComment.id))
            .filter(PurchaseReceiptComment.receipt_id.in_(receipt_ids))
            .group_by(PurchaseReceiptComment.receipt_id)
            .all()
        )
        return {rid: int(count) for rid, count in rows}

    def get_comment(self, receipt_id: str, comment_id: str) -> PurchaseReceiptComment | None:
        return (
            self.db.query(PurchaseReceiptComment)
            .filter(PurchaseReceiptComment.receipt_id == receipt_id, PurchaseReceiptComment.id == comment_id)
            .first()
        )

    def get_object_stats(
        self,
        user_id: str,
        scope: str = "all",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[tuple]:
        """(object_id, receipts_count, net_sum, last_purchased_at) per object over the receipts the
        user can see; object_id None is the bucket of receipts without an object."""
        shared_ids = self.db.query(PurchaseReceiptAccess.receipt_id).filter(PurchaseReceiptAccess.user_id == user_id)
        net = func.coalesce(
            func.sum(
                case(
                    (PurchaseReceipt.receipt_type == 1, PurchaseReceipt.total_sum),
                    (PurchaseReceipt.receipt_type == 2, -PurchaseReceipt.total_sum),
                    else_=0,
                )
            ),
            0,
        )
        q = self.db.query(
            PurchaseReceipt.object_id, func.count(PurchaseReceipt.id), net, func.max(PurchaseReceipt.purchased_at)
        )
        if scope == "mine":
            q = q.filter(PurchaseReceipt.created_by == user_id)
        elif scope == "shared":
            q = q.filter(PurchaseReceipt.id.in_(shared_ids))
        else:
            q = q.filter(or_(PurchaseReceipt.created_by == user_id, PurchaseReceipt.id.in_(shared_ids)))
        if date_from is not None:
            q = q.filter(PurchaseReceipt.purchased_at >= date_from)
        if date_to is not None:
            q = q.filter(PurchaseReceipt.purchased_at <= date_to)
        return q.group_by(PurchaseReceipt.object_id).all()

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

    # --- items / categories -----------------------------------------------------------------
    def get_items(self, receipt_ids: list[str]) -> list[PurchaseReceiptItem]:
        if not receipt_ids:
            return []
        return (
            self.db.query(PurchaseReceiptItem)
            .filter(PurchaseReceiptItem.receipt_id.in_(receipt_ids))
            .order_by(PurchaseReceiptItem.receipt_id, PurchaseReceiptItem.position)
            .all()
        )

    def get_category_links(self, receipt_ids: list[str]) -> list[PurchaseReceiptCategory]:
        if not receipt_ids:
            return []
        return self.db.query(PurchaseReceiptCategory).filter(PurchaseReceiptCategory.receipt_id.in_(receipt_ids)).all()

    def get_category_link(self, receipt_id: str, category_id: str) -> PurchaseReceiptCategory | None:
        return (
            self.db.query(PurchaseReceiptCategory)
            .filter(PurchaseReceiptCategory.receipt_id == receipt_id, PurchaseReceiptCategory.category_id == category_id)
            .first()
        )

    def get_categories_by_ids(self, category_ids: list[str]) -> list[ReceiptCategory]:
        ids = list({c for c in category_ids if c})
        if not ids:
            return []
        return self.db.query(ReceiptCategory).filter(ReceiptCategory.id.in_(ids)).all()

    def get_available_categories(self, user_id: str) -> list[ReceiptCategory]:
        """Categories the user may attach: standard ones and their own."""
        return (
            self.db.query(ReceiptCategory)
            .filter(or_(ReceiptCategory.owner_user_id.is_(None), ReceiptCategory.owner_user_id == user_id))
            .order_by(ReceiptCategory.owner_user_id.is_not(None), ReceiptCategory.name)
            .all()
        )

    def get_seller_logos(self, inns: list[str]) -> dict[str, ReceiptSellerLogo]:
        inns = [i for i in set(inns) if i]
        if not inns:
            return {}
        rows = self.db.query(ReceiptSellerLogo).filter(ReceiptSellerLogo.seller_inn.in_(inns)).all()
        return {r.seller_inn: r for r in rows}

    def get_advance_reports(self, receipt_ids: list[str]) -> dict[str, dict]:
        """receipt_id -> the advance report the receipt is in (a receipt is in at most one)."""
        if not receipt_ids:
            return {}
        rows = (
            self.db.query(AdvanceReportReceipt.receipt_id, AdvanceReport)
            .join(AdvanceReport, AdvanceReport.id == AdvanceReportReceipt.report_id)
            .filter(AdvanceReportReceipt.receipt_id.in_(receipt_ids))
            .all()
        )
        return {
            rid: {
                "id": rep.id,
                "number": rep.number,
                "title": rep.title,
                "report_date": rep.report_date,
                "status": rep.status,
                "one_c_number": rep.one_c_number,
            }
            for rid, rep in rows
        }

    # --- files ------------------------------------------------------------------------------
    def get_files(self, receipt_ids: list[str]) -> list[PurchaseReceiptFile]:
        if not receipt_ids:
            return []
        return (
            self.db.query(PurchaseReceiptFile)
            .filter(PurchaseReceiptFile.receipt_id.in_(receipt_ids))
            .order_by(PurchaseReceiptFile.created_at, PurchaseReceiptFile.id)
            .all()
        )

    def get_file(self, receipt_id: str, file_id: str) -> PurchaseReceiptFile | None:
        return (
            self.db.query(PurchaseReceiptFile)
            .filter(PurchaseReceiptFile.receipt_id == receipt_id, PurchaseReceiptFile.id == file_id)
            .first()
        )

    def count_files(self, receipt_id: str) -> int:
        return self.db.query(PurchaseReceiptFile).filter(PurchaseReceiptFile.receipt_id == receipt_id).count()

    # --- access -----------------------------------------------------------------------------
    def get_access_rows(self, receipt_ids: list[str]) -> list[PurchaseReceiptAccess]:
        if not receipt_ids:
            return []
        return (
            self.db.query(PurchaseReceiptAccess)
            .filter(PurchaseReceiptAccess.receipt_id.in_(receipt_ids))
            .order_by(PurchaseReceiptAccess.created_at)
            .all()
        )

    def get_access(self, receipt_id: str, user_id: str) -> PurchaseReceiptAccess | None:
        return (
            self.db.query(PurchaseReceiptAccess)
            .filter(PurchaseReceiptAccess.receipt_id == receipt_id, PurchaseReceiptAccess.user_id == user_id)
            .first()
        )

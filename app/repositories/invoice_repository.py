import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem, InvoiceLog, InvoicePayment
from app.models.item_mapping import ItemMapping
from app.models.supply_request import StatusRef, SupplyRequest, UnitRef


class InvoiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_invoice(self, payload: dict) -> Invoice:
        row = Invoice(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_by_id(self, invoice_id: int) -> Invoice | None:
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def get_invoices(self) -> list[Invoice]:
        return self.db.query(Invoice).order_by(Invoice.id.desc()).all()

    def get_invoices_by_ids(self, invoice_ids: list[int]) -> list[Invoice]:
        if not invoice_ids:
            return []
        return self.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).order_by(Invoice.id.desc()).all()

    def save_invoice(self, row: Invoice) -> Invoice:
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_invoice(self, row: Invoice) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_invoice_items(self, invoice_id: int) -> list[InvoiceItem]:
        return (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .all()
        )

    def get_chat_ids_by_invoice(self, invoice_ids: list[int]) -> dict[int, int]:
        from app.models.chat import Chat
        if not invoice_ids:
            return {}
        chats = (
            self.db.query(Chat)
            .filter(Chat.type == "invoice", Chat.invoice_id.in_(invoice_ids))
            .all()
        )
        return {chat.invoice_id: chat.id for chat in chats if chat.invoice_id}

    def get_chat_id_by_invoice(self, invoice_id: int) -> int | None:
        from app.models.chat import Chat
        chat = (
            self.db.query(Chat)
            .filter(Chat.type == "invoice", Chat.invoice_id == invoice_id)
            .first()
        )
        return chat.id if chat else None

    def get_item_mappings_by_invoice_id(self, invoice_id: int) -> list[ItemMapping]:
        return (
            self.db.query(ItemMapping)
            .filter(ItemMapping.invoice_id == invoice_id)
            .order_by(ItemMapping.created_at.desc())
            .all()
        )

    def get_request_names_by_ids(self, request_ids: list[int]) -> dict[int, str | None]:
        if not request_ids:
            return {}
        rows = (
            self.db.query(SupplyRequest.id, SupplyRequest.name)
            .filter(SupplyRequest.id.in_(list({rid for rid in request_ids if rid is not None})))
            .all()
        )
        return {row_id: row_name for row_id, row_name in rows}

    def get_requests_meta_by_ids(self, request_ids: list[int]) -> dict[int, dict]:
        unique_ids = list({rid for rid in request_ids if rid is not None})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(SupplyRequest.id, SupplyRequest.name, SupplyRequest.object_levels_id)
            .filter(SupplyRequest.id.in_(unique_ids))
            .all()
        )
        return {
            row_id: {"name": row_name, "object_levels_id": object_levels_id}
            for row_id, row_name, object_levels_id in rows
        }

    def create_invoice_item(self, invoice_id: int, payload: dict) -> InvoiceItem:
        item = InvoiceItem(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_invoice_item_by_id(self, invoice_id: int, item_id: str) -> InvoiceItem | None:
        return (
            self.db.query(InvoiceItem)
            .filter(
                InvoiceItem.invoice_id == invoice_id,
                InvoiceItem.id == item_id,
            )
            .first()
        )

    def save_invoice_item(self, item: InvoiceItem) -> InvoiceItem:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_invoice_item(self, item: InvoiceItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def delete_invoice_items_by_invoice_id(self, invoice_id: int) -> None:
        (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()

    def get_invoice_logs(self, invoice_id: int) -> list[InvoiceLog]:
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.invoice_id == invoice_id)
            .order_by(InvoiceLog.id.asc())
            .all()
        )

    def create_invoice_log(self, invoice_id: int, payload: dict) -> InvoiceLog:
        row = InvoiceLog(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_log_by_id(self, invoice_id: int, log_id: str) -> InvoiceLog | None:
        return (
            self.db.query(InvoiceLog)
            .filter(
                InvoiceLog.invoice_id == invoice_id,
                InvoiceLog.id == log_id,
            )
            .first()
        )

    def save_invoice_log(self, row: InvoiceLog) -> InvoiceLog:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_invoice_log(self, row: InvoiceLog) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_invoice_logs_by_user(self, user_id: str) -> list[InvoiceLog]:
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.user_id == user_id)
            .order_by(InvoiceLog.id.desc())
            .all()
        )

    def get_invoice_logs_by_invoice_ids(self, invoice_ids: list[int]) -> list[InvoiceLog]:
        if not invoice_ids:
            return []
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.invoice_id.in_(invoice_ids))
            .order_by(InvoiceLog.id.asc())
            .all()
        )

    def get_invoice_payments(self, invoice_id: int) -> list[InvoicePayment]:
        return (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id == invoice_id)
            .order_by(InvoicePayment.created_at.asc(), InvoicePayment.id.asc())
            .all()
        )

    def create_invoice_payment(self, invoice_id: int, payload: dict) -> InvoicePayment:
        row = InvoicePayment(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_payment_by_id(self, invoice_id: int, payment_id: str) -> InvoicePayment | None:
        return (
            self.db.query(InvoicePayment)
            .filter(
                InvoicePayment.invoice_id == invoice_id,
                InvoicePayment.id == payment_id,
            )
            .first()
        )

    def save_invoice_payment(self, row: InvoicePayment) -> InvoicePayment:
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_invoice_payment(self, row: InvoicePayment) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_invoice_payments_by_invoice_ids(self, invoice_ids: list[int]) -> list[InvoicePayment]:
        if not invoice_ids:
            return []
        return (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id.in_(invoice_ids))
            .order_by(InvoicePayment.created_at.asc(), InvoicePayment.id.asc())
            .all()
        )

    def get_status_name(self, status_id: str | None) -> str | None:
        if not status_id:
            return None
        row = self.db.query(StatusRef).filter(StatusRef.id == status_id).first()
        return row.name if row else None

    def find_duplicate_invoice(
        self,
        provider_id: str | None,
        payer_id: str | None,
        num: str | None,
        date,
    ) -> dict | None:
        query = self.db.query(Invoice)
        if provider_id:
            query = query.filter(Invoice.provider_id == provider_id)
        if payer_id:
            query = query.filter(Invoice.payer_id == payer_id)
        if num:
            query = query.filter(Invoice.num == num)
        if date:
            query = query.filter(Invoice.date == date)
        row = query.first()
        if not row:
            return None
        return {
            "id": row.id,
            "num": row.num,
            "date": row.date,
            "provider_id": row.provider_id,
            "payer_id": row.payer_id,
        }

    def get_unit_names(self, unit_ids: list[str]) -> dict[str, str]:
        if not unit_ids:
            return {}

        rows = (
            self.db.query(UnitRef.id, UnitRef.name)
            .filter(UnitRef.id.in_(unit_ids))
            .all()
        )
        return {str(unit_id): unit_name for unit_id, unit_name in rows}

    def get_badge_counts(self, user_id: str) -> dict:
        from app.models.chat import Chat, MessageMention
        from collections import defaultdict

        # 1. approval — InvoiceLog type=approval, user_id, status_name=pending
        approval_rows = (
            self.db.query(InvoiceLog.invoice_id)
            .filter(
                InvoiceLog.type == "approval",
                InvoiceLog.user_id == user_id,
                InvoiceLog.status_name == "pending",
            )
            .distinct()
            .all()
        )
        approval_invoice_ids = {row[0] for row in approval_rows}

        # 2. planning + payment — InvoiceLog type=planing or payment for user
        user_logs = (
            self.db.query(InvoiceLog)
            .filter(
                InvoiceLog.user_id == user_id,
                InvoiceLog.type.in_(["planing", "payment"]),
            )
            .all()
        )
        planning_invoice_ids: set[int] = set()
        payment_invoice_ids: set[int] = set()
        for log in user_logs:
            if log.type == "planing":
                planning_invoice_ids.add(log.invoice_id)
            elif log.type == "payment":
                payment_invoice_ids.add(log.invoice_id)

        all_ids = approval_invoice_ids | planning_invoice_ids | payment_invoice_ids
        if not all_ids:
            return {"approval": 0, "planning_required": 0, "payment_required": 0, "attention": 0, "total": 0}

        # fetch invoices
        invoices_map = {
            inv.id: inv
            for inv in self.db.query(Invoice).filter(Invoice.id.in_(all_ids)).all()
        }

        # fetch payments grouped by invoice_id
        payment_rows = (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id.in_(all_ids))
            .all()
        )
        payments_by_invoice: dict[int, list[InvoicePayment]] = defaultdict(list)
        for pmt in payment_rows:
            payments_by_invoice[pmt.invoice_id].append(pmt)

        # planning_required
        planning_required = 0
        for inv_id in planning_invoice_ids:
            inv = invoices_map.get(inv_id)
            if not inv:
                continue
            inv_payments = payments_by_invoice.get(inv_id, [])
            has_unpaid_planned = any(
                pmt.paid is None or (pmt.paid == 0 and pmt.paid_at is None)
                for pmt in inv_payments
            )
            if has_unpaid_planned:
                continue
            total_paid = sum(pmt.paid or 0 for pmt in inv_payments)
            if not inv_payments or total_paid != (inv.total_amount or 0):
                planning_required += 1

        # payment_required — has unpaid planned payments
        payment_required = 0
        for inv_id in payment_invoice_ids:
            inv_payments = payments_by_invoice.get(inv_id, [])
            has_unpaid_planned = any(
                pmt.paid is None or (pmt.paid == 0 and pmt.paid_at is None)
                for pmt in inv_payments
            )
            if has_unpaid_planned:
                payment_required += 1

        # attention — message_mentions in invoice chats
        chats = (
            self.db.query(Chat)
            .filter(Chat.type == "invoice", Chat.invoice_id.in_(all_ids))
            .all()
        )
        invoice_chat_ids = {chat.id for chat in chats if chat.id}
        attention = 0
        if invoice_chat_ids:
            attention = (
                self.db.query(MessageMention)
                .filter(
                    MessageMention.chat_id.in_(invoice_chat_ids),
                    MessageMention.user_id == user_id,
                    MessageMention.is_notified == False,
                    MessageMention.is_viewed == False,
                )
                .count()
            )

        approval_count = len(approval_invoice_ids)
        total = approval_count + planning_required + payment_required + attention
        return {
            "approval": approval_count,
            "planning_required": planning_required,
            "payment_required": payment_required,
            "attention": attention,
            "total": total,
        }

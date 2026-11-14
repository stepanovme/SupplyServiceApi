import logging
import uuid
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.invoice import InvoicePayment
from app.models.invoice_payment_extract import (
    InvoicePaymentExtract,
    InvoicePaymentExtractBulkCreate,
    InvoicePaymentExtractCreate,
    InvoicePaymentExtractMatchAllRequest,
    InvoicePaymentExtractUpdate,
    msk_now,
)
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.invoice_payment_extract_repository import InvoicePaymentExtractRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.services.invoice_reference_ai import extract_invoice_references_ai, should_try_ai
from app.services.invoice_reference_parser import extract_invoice_references, invoice_num_variants

logger = logging.getLogger(__name__)

# Amounts are money stored with 2 decimals; anything below half a kopeck is float noise.
TOLERANCE = 0.005
BANK_PAID_TYPE = "account"


def _is_paid(payment) -> bool:
    return (payment.paid or 0) > 0


def _value(payment) -> float:
    return float(payment.value or 0)


def _money(value: float) -> str:
    return f"{value:.2f}"


class InvoicePaymentExtractService:
    def __init__(
        self,
        repo: InvoicePaymentExtractRepository,
        invoice_repo: InvoiceRepository,
        extract_item_repo: ExtractItemRepository,
        notifier=None,
    ) -> None:
        self.repo = repo
        self.invoice_repo = invoice_repo
        self.extract_item_repo = extract_item_repo
        # InvoiceService (anything with notify_payment_made) - optional so the planner can be
        # used on its own (tests, dry runs).
        self.notifier = notifier

    # ------------------------------------------------------------------ planning (read-only)

    def _plan(self, item, use_ai: bool = True) -> tuple[dict, dict | None]:
        """Decides what should happen for one statement row without touching the DB.
        Returns (result, ctx); ctx is None when there is nothing to apply."""
        amount = float(item.amount) if item.amount is not None else None
        result: dict = {
            "extract_id": item.id,
            "status": "skipped",
            "reason": None,
            "amount": amount,
            "invoice_ref": None,
            "ref_source": None,
            "invoice": None,
            "scenario": None,
            "invoice_payment_id": None,
            "actions": [],
        }

        existing = self.repo.get_by_extract_id(item.id)
        if existing:
            result.update(status="already_linked", reason="already_linked", invoice_payment_id=existing.invoice_payment_id,
                          scenario=existing.scenario)
            return result, None

        if item.direction != "DEBIT":
            # Incoming money belongs to outgoing invoices, which have no invoice_payment rows.
            result["reason"] = "not_debit"
            return result, None

        if amount is None or amount <= 0:
            result["reason"] = "invalid_amount"
            return result, None

        refs = extract_invoice_references(item.paymentPurpose)
        result["ref_source"] = "regex" if refs else None
        if not refs and use_ai and should_try_ai(item.paymentPurpose):
            # Regex couldn't read it (e.g. a date written in words). The AI answer is only used
            # if every number/date it returns literally appears in the text.
            refs, ai_note = extract_invoice_references_ai(item.paymentPurpose)
            if refs:
                result["ref_source"] = "ai"
            if ai_note:
                result["ai_note"] = ai_note
        if not refs:
            result["reason"] = "no_invoice_reference"
            return result, None
        if len(refs) > 1:
            result["reason"] = "multiple_invoices"
            result["invoice_ref"] = [{"num": num, "date": ref_date} for num, ref_date in refs]
            return result, None

        num, invoice_date = refs[0]
        result["invoice_ref"] = {"num": num, "date": invoice_date}

        if not item.payer_id or not item.payee_id:
            # Both sides are needed to pin down the invoice; fix them via PATCH /extract-items/{id}.
            result["reason"] = "counterparties_not_resolved"
            return result, None

        invoices = self.invoice_repo.find_invoices_by_ref(
            invoice_num_variants(num), invoice_date, provider_id=item.payee_id, payer_id=item.payer_id
        )
        if not invoices:
            result["reason"] = "invoice_not_found"
            return result, None
        if len(invoices) > 1:
            result["reason"] = "ambiguous_invoice"
            result["invoice"] = {"candidate_ids": [inv.id for inv in invoices]}
            return result, None

        invoice = invoices[0]
        result["invoice"] = {
            "id": invoice.id,
            "num": invoice.num,
            "date": invoice.date,
            "total_amount": float(invoice.total_amount) if invoice.total_amount is not None else None,
        }
        if invoice.type == "outgoing":
            result["reason"] = "invoice_is_outgoing"
            return result, None

        payments = self.invoice_repo.get_invoice_payments(invoice.id)
        planned = [p for p in payments if not _is_paid(p) and _value(p) > 0]
        already_paid = sum(float(p.paid) for p in payments if _is_paid(p))

        # Payments somebody already entered by hand as PAID and that no statement row owns yet.
        linked_payment_ids = {l.invoice_payment_id for l in self.repo.get_by_payment_ids([p.id for p in payments])}
        paid_unlinked_exact = sorted(
            (p for p in payments
             if _is_paid(p) and abs(float(p.paid) - amount) < TOLERANCE and p.id not in linked_payment_ids),
            key=lambda p: p.paid_at or p.created_at,
        )

        target = None
        remainder = None
        exact = [p for p in planned if abs(_value(p) - amount) < TOLERANCE]
        larger = [p for p in planned if _value(p) > amount + TOLERANCE]
        smaller = [p for p in planned if _value(p) < amount - TOLERANCE]

        if paid_unlinked_exact:
            # The payment is already recorded as paid - only attach the statement row to it.
            # Creating another one here would count the same money twice.
            scenario, target = "linked_existing", paid_unlinked_exact[0]
            result["actions"].append(
                f"Платёж {target.id} уже оплачен на {_money(float(target.paid))} — строка выписки привязывается к нему, суммы не меняются"
            )
        elif exact:
            scenario, target = "exact", exact[0]
            result["actions"].append(
                f"Запланированный платёж {target.id} на {_money(amount)} отмечается оплаченным"
            )
        elif larger:
            # Pay out of the smallest planned payment that can cover it; the rest stays planned.
            scenario, target = "split", min(larger, key=_value)
            remainder = round(_value(target) - amount, 2)
            result["actions"].append(
                f"Запланированный платёж {target.id} ({_money(_value(target))}) → оплачено {_money(amount)}; "
                f"создаётся новый запланированный остаток {_money(remainder)}"
            )
        elif smaller:
            # Every planned payment is smaller than what was actually paid: raise the biggest one.
            scenario, target = "bumped", max(smaller, key=_value)
            result["actions"].append(
                f"Запланированный платёж {target.id}: сумма {_money(_value(target))} → {_money(amount)}, отмечается оплаченным"
            )
        else:
            scenario = "created"
            result["actions"].append(f"Создаётся новый оплаченный платёж на {_money(amount)}")

        # Never push the invoice past its total automatically - that's almost always a payment
        # that is already on the books under another form. (linked_existing adds no money.)
        total = float(invoice.total_amount) if invoice.total_amount else None
        if scenario != "linked_existing" and total and already_paid + amount > total + 0.01:
            result["actions"] = []
            result["reason"] = "would_exceed_invoice_total"
            result["invoice"].update(already_paid=round(already_paid, 2), would_be_paid=round(already_paid + amount, 2))
            return result, None

        result["scenario"] = scenario
        result["invoice_payment_id"] = target.id if target else None
        ctx = {"item": item, "invoice": invoice, "target": target, "scenario": scenario,
               "amount": amount, "remainder": remainder}
        return result, ctx

    # ------------------------------------------------------------------ applying (single transaction)

    def _apply(self, ctx: dict, user_id: str) -> str:
        """Writes the payment change(s) and the link in ONE transaction. Returns the id of the
        payment that is now marked as paid."""
        db = self.repo.db
        item, invoice, target = ctx["item"], ctx["invoice"], ctx["target"]
        scenario, amount, remainder = ctx["scenario"], ctx["amount"], ctx["remainder"]
        now = msk_now()
        paid_at = item.operationDate or now

        try:
            if scenario == "linked_existing":
                payment = target
            elif scenario == "created":
                payment = InvoicePayment(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    value=amount,
                    paid=amount,
                    paid_type=BANK_PAID_TYPE,
                    paid_by=user_id,
                    paid_at=paid_at,
                    created_by=user_id,
                    priority=2,
                )
                db.add(payment)
            else:
                payment = target
                original_date_plan, original_priority, original_created_by = (
                    payment.date_plan, payment.priority, payment.created_by,
                )
                if scenario in ("split", "bumped"):
                    payment.value = amount
                payment.paid = amount
                payment.paid_type = BANK_PAID_TYPE
                payment.paid_by = user_id
                payment.paid_at = paid_at
                payment.updated_at = now

                if scenario == "split":
                    db.add(
                        InvoicePayment(
                            id=str(uuid.uuid4()),
                            invoice_id=invoice.id,
                            value=remainder,
                            paid=0,
                            paid_type=BANK_PAID_TYPE,
                            date_plan=original_date_plan,
                            priority=original_priority,
                            created_by=original_created_by,
                        )
                    )

            # The link has a real FK to invoice_payment and no ORM relationship, so make sure
            # the payment row is INSERTed before the link row.
            db.flush()
            db.add(
                InvoicePaymentExtract(
                    id=str(uuid.uuid4()),
                    invoice_payment_id=payment.id,
                    extract_id=item.id,
                    scenario=scenario,
                    amount=amount,
                    created_by=user_id,
                )
            )
            db.commit()
            return payment.id
        except Exception:
            db.rollback()
            raise

    def _notify(self, ctx: dict, user_id: str) -> str:
        """linked_existing = the payment was already entered by hand, nobody needs telling again.
        Every other scenario is money newly marked as paid (a planned payment paid, or a payment
        created from scratch) and is announced exactly like a manual payment would be."""
        if ctx["scenario"] == "linked_existing":
            return "not_needed"
        if self.notifier is None:
            return "skipped_no_notifier"
        try:
            self.notifier.notify_payment_made(ctx["invoice"], user_id, ctx["amount"])
            return "sent"
        except Exception:
            # The payment and its link are already committed - a failed push must not undo or hide that.
            logger.exception("payment notification failed for invoice %s", ctx["invoice"].id)
            return "failed"

    def _process(self, item, user_id: str, dry_run: bool, use_ai: bool = True) -> dict:
        result, ctx = self._plan(item, use_ai)
        if ctx is None:
            return result

        if dry_run:
            result["status"] = "would_apply"
            result["notification"] = "not_needed" if ctx["scenario"] == "linked_existing" else "would_send"
            return result

        try:
            payment_id = self._apply(ctx, user_id)
        except IntegrityError:
            # Someone linked this row between our check and the commit (unique extract_id).
            result.update(status="already_linked", reason="already_linked", actions=[])
            return result

        result["status"] = "applied"
        result["invoice_payment_id"] = payment_id
        result["notification"] = self._notify(ctx, user_id)
        return result

    # ------------------------------------------------------------------ public API

    def match_extract_item(self, extract_id: str, user_id: str, dry_run: bool = False, use_ai: bool = True) -> dict:
        item = self.extract_item_repo.get_by_id(extract_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")
        result = self._process(item, user_id, dry_run, use_ai)
        result["dry_run"] = dry_run
        return result

    def match_all(self, payload: InvoicePaymentExtractMatchAllRequest, user_id: str) -> dict:
        if payload.extract_ids:
            items = self.extract_item_repo.get_by_ids(payload.extract_ids)
            found = {item.id for item in items}
            missing_ids = [eid for eid in payload.extract_ids if eid not in found]
        else:
            items = self.repo.get_unmatched_debit_extract_items(payload.limit, payload.date_from, payload.date_to)
            missing_ids = []

        results: list[dict] = []
        for item in items:
            try:
                results.append(self._process(item, user_id, payload.dry_run, payload.use_ai))
            except Exception as exc:  # one bad row must not abort the batch
                self.repo.db.rollback()
                results.append({"extract_id": item.id, "status": "error", "reason": "internal_error",
                                "detail": str(exc), "actions": []})

        by_status = Counter(r["status"] for r in results)
        skipped_by_reason = Counter(r["reason"] for r in results if r["status"] == "skipped")
        return {
            "dry_run": payload.dry_run,
            "use_ai": payload.use_ai,
            "ai_matched": sum(1 for r in results if r.get("ref_source") == "ai"),
            "processed": len(results),
            "applied": by_status.get("applied", 0),
            "would_apply": by_status.get("would_apply", 0),
            "already_linked": by_status.get("already_linked", 0),
            "skipped": by_status.get("skipped", 0),
            "errors": by_status.get("error", 0),
            "skipped_by_reason": dict(skipped_by_reason),
            "missing_extract_ids": missing_ids,
            "results": results,
        }

    # ------------------------------------------------------------------ read + manual links

    def _serialize_many(self, rows: list[InvoicePaymentExtract]) -> list[dict]:
        payments = {p.id: p for p in self.repo.get_payments_by_ids([r.invoice_payment_id for r in rows])}
        invoices = {i.id: i for i in self.repo.get_invoices_by_ids(list({p.invoice_id for p in payments.values()}))}
        out = []
        for row in rows:
            payment = payments.get(row.invoice_payment_id)
            invoice = invoices.get(payment.invoice_id) if payment else None
            out.append(
                {
                    "id": row.id,
                    "extract_id": row.extract_id,
                    "invoice_payment_id": row.invoice_payment_id,
                    "scenario": row.scenario,
                    "amount": row.amount,
                    "created_at": row.created_at,
                    "created_by": row.created_by,
                    "payment": (
                        {"value": payment.value, "paid": payment.paid, "paid_at": payment.paid_at}
                        if payment else None
                    ),
                    "invoice": (
                        {"id": invoice.id, "num": invoice.num, "date": invoice.date, "total_amount": invoice.total_amount}
                        if invoice else None
                    ),
                }
            )
        return out

    def get_list(self, extract_id=None, invoice_id=None, invoice_payment_id=None, limit=50, offset=0) -> list[dict]:
        rows = self.repo.get_list(extract_id, invoice_id, invoice_payment_id, limit, offset)
        return self._serialize_many(rows)

    def get_by_id(self, item_id: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        return self._serialize_many([row])[0]

    def _allocated(self, extract_id: str, exclude_link_id: str | None = None) -> float:
        return sum(
            float(l.amount or 0)
            for l in self.repo.get_links_by_extract_id(extract_id)
            if l.id != exclude_link_id
        )

    def _check_fits(self, item, requested: float, already_allocated: float) -> None:
        """The links of one statement row may not add up to more money than the row has."""
        total = float(item.amount) if item.amount is not None else None
        if total is not None and already_allocated + requested > total + TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Сумма привязок ({_money(already_allocated + requested)}) превышает сумму строки выписки "
                    f"({_money(total)}); уже распределено {_money(already_allocated)}"
                ),
            )

    def create_manual(self, payload: InvoicePaymentExtractCreate, user_id: str) -> dict:
        """Links a statement row to an EXISTING invoice payment without changing the payment
        itself - for cases the matcher can't resolve; the caller has already dealt with the
        payment by hand. One statement row can be linked to several payments (e.g. one bank
        transfer covering several invoices); `amount` is this payment's share of the row."""
        item = self.extract_item_repo.get_by_id(payload.extract_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")
        payment = self.repo.get_payment_by_id(payload.invoice_payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice payment not found")

        existing = self.repo.get_pair(payload.extract_id, payload.invoice_payment_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Эта строка выписки уже привязана к этому платежу (link id={existing.id}); "
                       "измените сумму через PATCH или удалите связь",
            )

        allocated = self._allocated(payload.extract_id)
        total = float(item.amount) if item.amount is not None else None
        amount = payload.amount
        if amount is None:
            # No explicit share: take what's still unallocated on the row.
            amount = round(total - allocated, 2) if total is not None else None
            if amount is not None and amount <= TOLERANCE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Строка выписки уже полностью распределена между платежами; укажите amount явно после освобождения суммы",
                )
        else:
            self._check_fits(item, amount, allocated)

        row = InvoicePaymentExtract(
            id=str(uuid.uuid4()),
            invoice_payment_id=payload.invoice_payment_id,
            extract_id=payload.extract_id,
            scenario="manual",
            amount=amount,
            created_by=user_id,
        )
        created = self.repo.create(row)
        return self._serialize_many([created])[0]

    def create_bulk(self, payload: InvoicePaymentExtractBulkCreate, user_id: str) -> list[dict]:
        """Attaches one statement row to several invoice payments atomically: either every
        link is created or none."""
        item = self.extract_item_repo.get_by_id(payload.extract_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")

        payment_ids = [l.invoice_payment_id for l in payload.links]
        found = {p.id for p in self.repo.get_payments_by_ids(payment_ids)}
        missing = [pid for pid in payment_ids if pid not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice payments not found: {', '.join(missing)}"
            )
        for pid in payment_ids:
            if self.repo.get_pair(payload.extract_id, pid):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Строка выписки уже привязана к платежу {pid}; измените сумму через PATCH",
                )

        self._check_fits(item, sum(l.amount for l in payload.links), self._allocated(payload.extract_id))

        db = self.repo.db
        try:
            rows = [
                InvoicePaymentExtract(
                    id=str(uuid.uuid4()),
                    invoice_payment_id=l.invoice_payment_id,
                    extract_id=payload.extract_id,
                    scenario="manual",
                    amount=l.amount,
                    created_by=user_id,
                )
                for l in payload.links
            ]
            db.add_all(rows)
            db.commit()
        except Exception:
            db.rollback()
            raise
        for row in rows:
            db.refresh(row)
        return self._serialize_many(rows)

    def update_amount(self, item_id: str, payload: InvoicePaymentExtractUpdate) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        item = self.extract_item_repo.get_by_id(row.extract_id)
        if item:
            self._check_fits(item, payload.amount, self._allocated(row.extract_id, exclude_link_id=row.id))
        row.amount = payload.amount
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._serialize_many([row])[0]

    def delete(self, item_id: str) -> None:
        """Removes only the link. The payment it produced is left as is - undo that in the
        invoice itself if needed."""
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        self.repo.delete(row)

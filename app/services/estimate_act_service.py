from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.estimate import (
    ACT_KINDS, ACT_STATUSES, ActCreate, ActItemIn, ActUpdate, EstimateAct, EstimateActItem, EstimateWorkProgress,
)
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.estimate_service import EstimateService, money, not_found


class EstimateActService:
    """Акты закрытия объёмов: по основной смете - с заказчиком, по утверждённой смете подрядчика - с подрядчиком."""

    def __init__(self, db: Session, reference_repo: ReferenceObjectRepository | None = None) -> None:
        self.db = db
        self.reference_repo = reference_repo
        self.estimates = EstimateService(db, reference_repo)

    # ---------- queries ----------
    def list_acts(self, estimate_id: int, act_status: str | None) -> list[dict]:
        kind = self._kind(self.estimates._estimate(estimate_id))
        q = self.db.query(EstimateAct).filter_by(estimate_id=estimate_id, kind=kind)
        if act_status:
            q = q.filter(EstimateAct.status == act_status)
        acts = q.order_by(EstimateAct.date.desc(), EstimateAct.id.desc()).all()
        works = self._works(estimate_id)
        return [self._view(a, works, with_items=False) for a in acts]

    def get_act(self, act_id: int) -> dict:
        act = self._act(act_id)
        return self._view(act, self._works(act.estimate_id), with_items=True)

    def preview(self, estimate_id: int, date_from, date_to, exclude_act_id: int | None = None) -> dict:
        est = self.estimates._estimate(estimate_id)
        kind, cp = self._kind(est), self._counterparty(est)
        self._check_period(date_from, date_to)
        works = self._works(estimate_id)
        prices = self._prices(estimate_id, est)
        in_period, to_date, closed = self._volumes(estimate_id, kind, cp, date_from, date_to, exclude_act_id)
        items = []
        for wid, w in works.items():
            available = max(to_date.get(wid, Decimal(0)) - closed.get(wid, Decimal(0)), Decimal(0))
            if not in_period.get(wid) and not available:
                continue
            price = prices.get(wid)
            items.append({
                "work_id": wid, "number": w["number"], "name": w["name"], "unit_name": w["unit_name"], "planned_quantity": w["quantity"],
                "done_in_period": float(in_period.get(wid, 0)), "done_to_date": float(to_date.get(wid, 0)),
                "closed_quantity": float(closed.get(wid, 0)), "available_quantity": float(available),
                "suggested_quantity": float(min(in_period.get(wid, Decimal(0)), available)),
                "unit_price": float(price) if price is not None else None, "can_close": price is not None,
            })
        return {
            "kind": kind, "kind_label": ACT_KINDS[kind], "counterparty_id": cp, "counterparty_name": self.estimates._contractor_names([cp]).get(cp),
            "date_from": date_from, "date_to": date_to, "prices_ready": self._ready(est), "works": items,
        }

    # ---------- commands ----------
    def create_act(self, estimate_id: int, payload: ActCreate, user_id: str) -> dict:
        est = self.estimates._estimate(estimate_id)
        kind, cp = self._kind(est), self._counterparty(est)
        self._check_period(payload.date_from, payload.date_to)
        number = (self.db.query(func.max(EstimateAct.number)).filter_by(estimate_id=estimate_id, kind=kind, counterparty_id=cp).scalar() or 0) + 1
        act = EstimateAct(estimate_id=estimate_id, kind=kind, counterparty_id=cp, number=number, date=payload.date,
                          date_from=payload.date_from, date_to=payload.date_to, comment=payload.comment, created_by=user_id)
        self.db.add(act)
        self.db.flush()
        self._fill_items_or_rollback(act, payload.items)
        self.db.commit()
        return self.get_act(act.id)

    def update_act(self, act_id: int, payload: ActUpdate, user_id: str) -> dict:
        act = self._act(act_id)
        data = payload.model_dump(exclude_unset=True)
        if act.status == "signed" and set(data) - {"date", "comment"}:
            raise HTTPException(status_code=409, detail="Акт подписан: можно менять только дату и комментарий, либо снимите подпись")
        if data.get("date"):
            act.date = data["date"]
        if "comment" in data:
            act.comment = data["comment"]
        if data.get("date_from") or data.get("date_to"):
            act.date_from, act.date_to = data.get("date_from") or act.date_from, data.get("date_to") or act.date_to
            self._check_period(act.date_from, act.date_to)
        if payload.items is not None:
            self.db.query(EstimateActItem).filter_by(act_id=act.id).delete()
            self.db.flush()
            self._fill_items_or_rollback(act, payload.items)
        elif data.get("date_from") or data.get("date_to"):
            try:
                self._validate_existing(act)
            except HTTPException:
                self.db.rollback()
                raise
        act.updated_at, act.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_act(act_id)

    def sign(self, act_id: int, user_id: str) -> dict:
        act = self._act(act_id)
        if act.status == "signed":
            raise HTTPException(status_code=409, detail="Акт уже подписан")
        self._validate_existing(act)
        act.status, act.signed_at, act.signed_by = "signed", msk_now(), user_id
        act.updated_at, act.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_act(act_id)

    def unsign(self, act_id: int, user_id: str) -> dict:
        act = self._act(act_id)
        act.status, act.signed_at, act.signed_by = "unsigned", None, None
        act.updated_at, act.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_act(act_id)

    def delete_act(self, act_id: int) -> None:
        act = self._act(act_id)
        if act.status == "signed":
            raise HTTPException(status_code=409, detail="Акт подписан: сначала снимите подпись")
        self.db.delete(act)
        self.db.commit()

    # ---------- internals ----------
    def _act(self, act_id: int) -> EstimateAct:
        row = self.db.get(EstimateAct, act_id)
        if not row:
            raise not_found("Акт")
        return row

    @staticmethod
    def _kind(est) -> str:
        return "contractor" if est.kind == "contractor" else "customer"

    def _counterparty(self, est) -> str:
        if est.kind == "contractor":
            return est.executor_id
        if not est.customer_id:
            raise HTTPException(status_code=422, detail="В смете не указан заказчик")
        return est.customer_id

    @staticmethod
    def _ready(est) -> bool:
        return est.kind != "contractor" or est.approval_status == "approved"

    @staticmethod
    def _check_period(date_from, date_to) -> None:
        if date_from > date_to:
            raise HTTPException(status_code=422, detail="Дата начала периода позже даты конца")

    def _works(self, estimate_id: int) -> dict[int, dict]:
        estimate = self.estimates.get_estimate(estimate_id)
        out = {}
        for s in estimate["sections"]:
            for w in s["works"]:
                qty, total = Decimal(str(w["quantity"])), Decimal(str(w["totals"]["customer_total"]))
                out[w["id"]] = {"number": w["number"], "name": w["name"], "unit_name": w["unit_name"], "quantity": w["quantity"],
                                "customer_price": money(total / qty) if qty else None}
        return out

    def _prices(self, estimate_id: int, est) -> dict[int, Decimal]:
        if not self._ready(est):
            return {}
        return {wid: w["customer_price"] for wid, w in self._works(estimate_id).items() if w["customer_price"] is not None}

    def _volumes(self, estimate_id: int, kind: str, cp: str, date_from, date_to, exclude_act_id: int | None):
        work_ids = list(self._works(estimate_id))
        q = self.db.query(EstimateWorkProgress.work_id, EstimateWorkProgress.date, func.sum(EstimateWorkProgress.quantity)).filter(
            EstimateWorkProgress.work_id.in_(work_ids), EstimateWorkProgress.date <= date_to)
        in_period, to_date = {}, {}
        for wid, d, qty in q.group_by(EstimateWorkProgress.work_id, EstimateWorkProgress.date).all() if work_ids else []:
            to_date[wid] = to_date.get(wid, Decimal(0)) + Decimal(qty)
            if d >= date_from:
                in_period[wid] = in_period.get(wid, Decimal(0)) + Decimal(qty)
        cq = self.db.query(EstimateActItem.work_id, func.sum(EstimateActItem.quantity)).join(EstimateAct, EstimateAct.id == EstimateActItem.act_id).filter(
            EstimateAct.estimate_id == estimate_id, EstimateAct.kind == kind, EstimateAct.counterparty_id == cp)
        if exclude_act_id:
            cq = cq.filter(EstimateAct.id != exclude_act_id)
        closed = {wid: Decimal(qty) for wid, qty in cq.group_by(EstimateActItem.work_id).all()}
        return in_period, to_date, closed

    def _fill_items_or_rollback(self, act: EstimateAct, items: list[ActItemIn]) -> None:
        try:
            self._fill_items(act, items)
        except HTTPException:
            self.db.rollback()
            raise

    def _fill_items(self, act: EstimateAct, items: list[ActItemIn]) -> None:
        if len({i.work_id for i in items}) != len(items):
            raise HTTPException(status_code=422, detail="Одна работа указана в акте несколько раз")
        works = self._works(act.estimate_id)
        est = self.estimates._estimate(act.estimate_id)
        if not self._ready(est):
            raise HTTPException(status_code=422, detail="Смета подрядчика не утверждена: закрыть работы нельзя")
        prices = self._prices(act.estimate_id, est)
        _, to_date, closed = self._volumes(act.estimate_id, act.kind, act.counterparty_id, act.date_from, act.date_to, act.id)
        for item in items:
            work = works.get(item.work_id)
            if not work:
                raise HTTPException(status_code=404, detail=f"Работа {item.work_id} не найдена в смете")
            available = max(to_date.get(item.work_id, Decimal(0)) - closed.get(item.work_id, Decimal(0)), Decimal(0))
            if item.quantity > available:
                raise HTTPException(status_code=422, detail=f"«{work['name']}»: можно закрыть не более {available} {work['unit_name'] or ''}".strip())
            price = prices.get(item.work_id)
            if price is None:
                raise HTTPException(status_code=422, detail=f"«{work['name']}»: нет цены")
            self.db.add(EstimateActItem(act_id=act.id, work_id=item.work_id, quantity=item.quantity, unit_price=price))

    def _validate_existing(self, act: EstimateAct) -> None:
        items = self.db.query(EstimateActItem).filter_by(act_id=act.id).all()
        _, to_date, closed = self._volumes(act.estimate_id, act.kind, act.counterparty_id, act.date_from, act.date_to, act.id)
        works = self._works(act.estimate_id)
        for i in items:
            if Decimal(i.quantity) > max(to_date.get(i.work_id, Decimal(0)) - closed.get(i.work_id, Decimal(0)), Decimal(0)):
                raise HTTPException(status_code=422, detail=f"«{works[i.work_id]['name']}»: закрыто больше, чем выполнено в выбранном периоде")

    def _view(self, act: EstimateAct, works: dict, with_items: bool) -> dict:
        rows = self.db.query(EstimateActItem).filter_by(act_id=act.id).order_by(EstimateActItem.id).all()
        items = []
        for i in sorted(rows, key=lambda r: [int(p) for p in works.get(r.work_id, {"number": "0"})["number"].split(".")]):
            w, qty, price = works.get(i.work_id, {}), Decimal(i.quantity), Decimal(i.unit_price)
            amount = money(qty * price)
            item = {"id": i.id, "work_id": i.work_id, "number": w.get("number"), "name": w.get("name"), "unit_name": w.get("unit_name"),
                    "quantity": float(qty), "unit_price": float(price), "amount": float(amount)}
            items.append(item)
        totals = {"amount": float(sum((Decimal(str(i["amount"])) for i in items), Decimal(0))), "items_count": len(items)}
        head = {
            "id": act.id, "estimate_id": act.estimate_id, "kind": act.kind, "kind_label": ACT_KINDS[act.kind],
            "counterparty_id": act.counterparty_id, "counterparty_name": self.estimates._contractor_names([act.counterparty_id]).get(act.counterparty_id),
            "number": act.number, "date": act.date, "date_from": act.date_from, "date_to": act.date_to,
            "status": act.status, "status_label": ACT_STATUSES[act.status], "is_signed": act.status == "signed",
            "signed_at": act.signed_at, "signed_by": act.signed_by, "comment": act.comment,
            "totals": totals, "created_at": act.created_at, "created_by": act.created_by, "updated_at": act.updated_at, "updated_by": act.updated_by,
        }
        return {**head, "items": items} if with_items else head

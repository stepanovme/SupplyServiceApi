from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.estimate import (
    ESTIMATE_STATUSES, Estimate, EstimateResource, EstimateSection, EstimateWork, EstimateWorkPeriod, EstimateWorkProgress,
    ProgressCreate, ProgressUpdate, RESOURCE_TYPES,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.estimate_service import progress_view

WORK_STATES = ("not_started", "in_progress", "completed", "overdue")


class ConstructionService:
    """«Стройка - работы»: работы смет с графиком, подрядчиками и фактом выполнения объёмов."""

    def __init__(self, db: Session, reference_repo: ReferenceObjectRepository | None = None, auth_user_repo: AuthUserRepository | None = None) -> None:
        self.db = db
        self.reference_repo = reference_repo
        self.auth_user_repo = auth_user_repo

    @staticmethod
    def today() -> date:
        return msk_now().date()

    # ---------- list ----------
    def list_works(self, estimate_id, object_id, estimate_status, contractor_id, search, state, limit, offset) -> dict:
        q = self.db.query(EstimateWork, EstimateSection, Estimate).join(EstimateSection, EstimateWork.section_id == EstimateSection.id).join(Estimate, EstimateSection.estimate_id == Estimate.id)
        if estimate_id:
            q = q.filter(Estimate.id == estimate_id)
        if object_id:
            q = q.filter(Estimate.object_id == object_id)
        if estimate_status and estimate_status != "all":
            q = q.filter(Estimate.status == estimate_status)
        if search and search.strip():
            q = q.filter(EstimateWork.name.like(f"%{search.strip()}%"))
        if contractor_id:
            q = q.filter(EstimateWork.id.in_(self.db.query(EstimateResource.work_id).filter(EstimateResource.contractor_id == contractor_id)))
        rows = q.all()
        items = self._build_items(rows)
        summary = {s: sum(1 for i in items if self._state(i) == s) for s in ("not_started", "in_progress", "completed")}
        summary["overdue"] = sum(1 for i in items if i["is_overdue"])
        summary["total"] = len(items)
        if state:
            items = [i for i in items if (i["is_overdue"] if state == "overdue" else self._state(i) == state)]
        items.sort(key=lambda i: (i["estimate"]["id"], i["_order"]))
        total = len(items)
        page = items[offset: offset + limit]
        for i in page:
            i.pop("_order")
        return {"total": total, "limit": limit, "offset": offset, "summary": summary, "items": page}

    @staticmethod
    def _state(item: dict) -> str:
        if item["is_completed"]:
            return "completed"
        return "in_progress" if item["done_quantity"] > 0 else "not_started"

    def _build_items(self, rows: list) -> list[dict]:
        if not rows:
            return []
        work_ids = [w.id for w, _s, _e in rows]
        estimate_ids = list({e.id for _w, _s, e in rows})
        periods, contractors, done, last = defaultdict(list), defaultdict(set), {}, {}
        for p in self.db.query(EstimateWorkPeriod).filter(EstimateWorkPeriod.work_id.in_(work_ids)).order_by(EstimateWorkPeriod.date_from).all():
            periods[p.work_id].append(p)
        for work_id, cid in self.db.query(EstimateResource.work_id, EstimateResource.contractor_id).filter(EstimateResource.work_id.in_(work_ids), EstimateResource.contractor_id.isnot(None)).distinct().all():
            contractors[work_id].add(cid)
        for work_id, total, last_date in self.db.query(EstimateWorkProgress.work_id, func.sum(EstimateWorkProgress.quantity), func.max(EstimateWorkProgress.date)).filter(EstimateWorkProgress.work_id.in_(work_ids)).group_by(EstimateWorkProgress.work_id).all():
            done[work_id], last[work_id] = total, last_date
        cnames = self.reference_repo.get_counterparty_names(list({c for s in contractors.values() for c in s})) if self.reference_repo and contractors else {}
        object_names = {}
        for e in {e.id: e for _w, _s, e in rows}.values():
            if e.object_id and e.object_id not in object_names:
                object_names[e.object_id] = self._object_name(e.object_id, e.object_type)
        numbers = self._numbers(estimate_ids)
        today = self.today()
        items = []
        for w, s, e in rows:
            ps = periods.get(w.id, [])
            deadline = max((p.date_to for p in ps), default=None)
            view = progress_view(w.quantity, done.get(w.id, 0))
            number, order = numbers[w.id]
            items.append({
                "work_id": w.id, "number": number, "name": w.name, "unit_name": w.unit_name, **view,
                "estimate": {"id": e.id, "name": e.name, "status": e.status, "status_label": ESTIMATE_STATUSES[e.status]},
                "object": {"object_id": e.object_id, "name": object_names.get(e.object_id)} if e.object_id else None,
                "section": {"id": s.id, "name": s.name},
                "periods": [{"id": p.id, "date_from": p.date_from, "date_to": p.date_to, "days": (p.date_to - p.date_from).days + 1} for p in ps],
                "date_from": min((p.date_from for p in ps), default=None), "deadline": deadline,
                "days_left": (deadline - today).days if deadline else None,
                "is_overdue": bool(deadline and deadline < today and not view["is_completed"]),
                "contractors": [{"id": c, "name": cnames.get(c)} for c in sorted(contractors.get(w.id, []), key=lambda c: cnames.get(c) or "")],
                "last_progress_date": last.get(w.id), "_order": order,
            })
        return items

    def _numbers(self, estimate_ids: list[int]) -> dict[int, tuple[str, tuple]]:
        out = {}
        for eid in estimate_ids:
            sections = self.db.query(EstimateSection).filter_by(estimate_id=eid).order_by(EstimateSection.position, EstimateSection.id).all()
            for si, s in enumerate(sections, start=1):
                for wi, w in enumerate(self.db.query(EstimateWork).filter_by(section_id=s.id).order_by(EstimateWork.position, EstimateWork.id).all(), start=1):
                    out[w.id] = (f"{si}.{wi}", (si, wi))
        return out

    # ---------- one work ----------
    def get_work(self, work_id: int) -> dict:
        row = self._work_row(work_id)
        item = self._build_items([row])[0]
        item.pop("_order")
        entries = self.db.query(EstimateWorkProgress).filter_by(work_id=work_id).order_by(EstimateWorkProgress.date.desc(), EstimateWorkProgress.id.desc()).all()
        users = self._users([e.created_by for e in entries])
        executors = self.reference_repo.get_counterparty_names(list({e.contractor_id for e in entries if e.contractor_id})) if self.reference_repo else {}
        item["progress"] = [{
            "id": e.id, "date": e.date, "quantity": float(e.quantity), "contractor_id": e.contractor_id,
            "contractor_name": executors.get(e.contractor_id), "comment": e.comment,
            "created_at": e.created_at, "created_by": e.created_by, "created_by_user": users.get(e.created_by),
        } for e in entries]
        by_contractor = defaultdict(float)
        for e in entries:
            by_contractor[e.contractor_id] += float(e.quantity)
        item["done_by_contractor"] = [
            {"contractor_id": cid, "contractor_name": executors.get(cid), "quantity": qty}
            for cid, qty in sorted(by_contractor.items(), key=lambda kv: (kv[0] is None, executors.get(kv[0]) or ""))
        ]
        resources = self.db.query(EstimateResource).filter_by(work_id=work_id).order_by(EstimateResource.position, EstimateResource.id).all()
        names = self.reference_repo.get_counterparty_names(list({r.contractor_id for r in resources if r.contractor_id})) if self.reference_repo else {}
        item["resources"] = [{
            "id": r.id, "type": r.type, "type_label": RESOURCE_TYPES[r.type], "name": r.name, "contractor_id": r.contractor_id,
            "contractor_name": names.get(r.contractor_id), "quantity": float(r.quantity), "unit_name": r.unit_name,
        } for r in resources]
        return item

    def _work_row(self, work_id: int):
        row = (
            self.db.query(EstimateWork, EstimateSection, Estimate)
            .join(EstimateSection, EstimateWork.section_id == EstimateSection.id).join(Estimate, EstimateSection.estimate_id == Estimate.id)
            .filter(EstimateWork.id == work_id).first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Работа не найдена")
        return row

    # ---------- journal of the whole estimate ----------
    def get_journal(self, estimate_id: int, date_from, date_to, contractor_id, work_id, limit: int, offset: int) -> dict:
        estimate = self.db.query(Estimate).filter_by(id=estimate_id).first()
        if not estimate:
            raise HTTPException(status_code=404, detail="Смета не найдена")
        q = (
            self.db.query(EstimateWorkProgress, EstimateWork, EstimateSection)
            .join(EstimateWork, EstimateWorkProgress.work_id == EstimateWork.id)
            .join(EstimateSection, EstimateWork.section_id == EstimateSection.id)
            .filter(EstimateSection.estimate_id == estimate_id)
        )
        if date_from:
            q = q.filter(EstimateWorkProgress.date >= date_from)
        if date_to:
            q = q.filter(EstimateWorkProgress.date <= date_to)
        if contractor_id:
            q = q.filter(EstimateWorkProgress.contractor_id == contractor_id)
        if work_id:
            q = q.filter(EstimateWork.id == work_id)
        total = q.count()
        rows = q.order_by(EstimateWorkProgress.date.desc(), EstimateWorkProgress.id.desc()).offset(offset).limit(limit).all()
        numbers = self._numbers([estimate_id])
        cumulative = self._cumulative_done(estimate_id)
        users = self._users([p.created_by for p, _w, _s in rows])
        names = self.reference_repo.get_counterparty_names(list({p.contractor_id for p, _w, _s in rows if p.contractor_id})) if self.reference_repo else {}
        return {
            "estimate": {"id": estimate.id, "name": estimate.name, "status": estimate.status, "status_label": ESTIMATE_STATUSES[estimate.status]},
            "total": total, "limit": limit, "offset": offset,
            "items": [{
                "id": p.id, "date": p.date, "work_id": w.id, "work_number": numbers[w.id][0], "work_name": w.name,
                "section": {"id": s.id, "name": s.name}, "unit_name": w.unit_name, "quantity": float(p.quantity),
                **self._state_after(w.quantity, cumulative[p.id]),
                "contractor_id": p.contractor_id, "contractor_name": names.get(p.contractor_id), "comment": p.comment,
                "created_at": p.created_at, "created_by": p.created_by, "created_by_user": users.get(p.created_by),
            } for p, w, s in rows],
        }

    def _cumulative_done(self, estimate_id: int) -> dict[int, "Decimal"]:
        """{id записи: сколько по работе выполнено к этой записи включительно} - по порядку (дата, id)."""
        rows = (
            self.db.query(EstimateWorkProgress.id, EstimateWorkProgress.work_id, EstimateWorkProgress.quantity)
            .join(EstimateWork, EstimateWorkProgress.work_id == EstimateWork.id)
            .join(EstimateSection, EstimateWork.section_id == EstimateSection.id)
            .filter(EstimateSection.estimate_id == estimate_id)
            .order_by(EstimateWorkProgress.date, EstimateWorkProgress.id).all()
        )
        running, out = defaultdict(Decimal), {}
        for entry_id, work_id, quantity in rows:
            running[work_id] += quantity
            out[entry_id] = running[work_id]
        return out

    @staticmethod
    def _state_after(planned, done_after) -> dict:
        view = progress_view(planned, done_after)
        return {
            "planned_quantity": view["quantity"], "done_after": view["done_quantity"],
            "remaining_after": view["remaining_quantity"], "progress_percent_after": view["progress_percent"],
            "is_completed_after": view["is_completed"],
        }

    # ---------- progress ----------
    def add_progress(self, work_id: int, payload: ProgressCreate, user_id: str) -> dict:
        self._work_row(work_id)
        self._check_date(payload.date)
        self._check_contractor(payload.contractor_id)
        self.db.add(EstimateWorkProgress(
            work_id=work_id, date=payload.date, quantity=payload.quantity, contractor_id=payload.contractor_id,
            comment=payload.comment, created_by=user_id,
        ))
        self.db.commit()
        return self.get_work(work_id)

    def update_progress(self, progress_id: int, payload: ProgressUpdate, user_id: str) -> dict:
        row = self._progress_row(progress_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("date"):
            self._check_date(data["date"])
        if "contractor_id" in data:
            self._check_contractor(data["contractor_id"])
        for key, value in data.items():
            if value is None and key not in ("comment", "contractor_id"):
                continue
            setattr(row, key, value)
        row.updated_at, row.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_work(row.work_id)

    def delete_progress(self, progress_id: int) -> dict:
        row = self._progress_row(progress_id)
        work_id = row.work_id
        self.db.delete(row)
        self.db.commit()
        return self.get_work(work_id)

    def _progress_row(self, progress_id: int) -> EstimateWorkProgress:
        row = self.db.query(EstimateWorkProgress).filter_by(id=progress_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Запись выполнения не найдена")
        return row

    def _check_contractor(self, contractor_id: str | None) -> None:
        if contractor_id and self.reference_repo and contractor_id not in self.reference_repo.get_counterparty_names([contractor_id]):
            raise HTTPException(status_code=404, detail="Подрядчик (контрагент) не найден")

    def _check_date(self, day: date) -> None:
        if day > self.today():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Дата выполнения не может быть в будущем")

    # ---------- helpers ----------
    def _object_name(self, object_id: str | None, object_type: str | None) -> str | None:
        if not self.reference_repo or not object_id:
            return None
        if object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            return (objs[0].short_name or objs[0].full_name) if objs else None
        return self.reference_repo.resolve_object_name(object_id)

    def _users(self, user_ids: list[str]) -> dict[str, dict]:
        if not self.auth_user_repo:
            return {}
        out = {}
        for u in self.auth_user_repo.get_by_ids(list({i for i in user_ids if i})):
            initials = " ".join(p for p in [u.surname, f"{u.name[0]}." if u.name else "", f"{u.patronymic[0]}." if u.patronymic else ""] if p)
            out[u.id] = {"id": u.id, "name": u.name, "surname": u.surname, "patronymic": u.patronymic, "short_fio": initials}
        return out

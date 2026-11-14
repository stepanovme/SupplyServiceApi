from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.estimate import (
    APPROVAL_STATUSES, ESTIMATE_KINDS, ESTIMATE_STATUSES, RESOURCE_TYPES, Estimate, EstimateResource, EstimateSection, EstimateWork,
    EstimateWorkPeriod, EstimateWorkProgress, EstimateCreate, EstimateUpdate, PeriodCreate, PeriodUpdate, ResourceCreate,
    ResourceUpdate, SaveToCatalog, SectionCreate, SectionUpdate, WorkCreate, WorkUpdate,
)
from app.models.contract import Contract
from app.models.price_catalog import PriceItemCreate, TemplateResourceCreate
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.price_catalog_service import PriceCatalogService

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def progress_view(planned: Decimal, done: Decimal) -> dict:
    """Плановый и фактический объём работы: остаток, процент выполнения, перевыполнение."""
    planned, done = Decimal(planned or 0), Decimal(done or 0)
    return {
        "quantity": float(planned), "done_quantity": float(done),
        "remaining_quantity": float(max(planned - done, Decimal(0))),
        "progress_percent": float((done / planned * 100).quantize(CENT, rounding=ROUND_HALF_UP)) if planned > 0 else None,
        "is_completed": planned > 0 and done >= planned,
        "overrun_quantity": float(max(done - planned, Decimal(0))) if planned > 0 else 0.0,
    }


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} не найден")


class EstimateService:
    def __init__(self, db: Session, reference_repo: ReferenceObjectRepository | None = None) -> None:
        self.db = db
        self.reference_repo = reference_repo

    # ---------- meta ----------
    @staticmethod
    def get_meta() -> dict:
        return {
            "statuses": [{"value": k, "label": v} for k, v in ESTIMATE_STATUSES.items()],
            "kinds": [{"value": k, "label": v} for k, v in ESTIMATE_KINDS.items()],
            "resource_types": [{"value": k, "label": v} for k, v in RESOURCE_TYPES.items()],
        }

    # ---------- estimates ----------
    def list_estimates(self, status_filter: str | None, object_id: str | None, kind: str | None = None, executor_id: str | None = None) -> list[dict]:
        q = self.db.query(Estimate)
        if kind:
            q = q.filter(Estimate.kind == kind)
        if executor_id:
            q = q.filter(Estimate.executor_id == executor_id)
        if status_filter:
            q = q.filter(Estimate.status == status_filter)
        if object_id:
            q = q.filter(Estimate.object_id == object_id)
        rows = q.order_by(Estimate.created_at.desc(), Estimate.id.desc()).all()
        return [self._estimate_head(e, self._totals_for([e.id])[e.id]) for e in rows]

    def create_estimate(self, payload: EstimateCreate, user_id: str) -> dict:
        data = payload.model_dump(exclude={"object"})
        if payload.object:
            self._check_object(payload.object.object_id, payload.object.object_type)
        for key in ("customer_id", "investor_id", "contractor_id"):
            self._check_contractor(data.get(key))
        if payload.kind == "contractor":
            if not payload.executor_id:
                raise HTTPException(status_code=422, detail="Для сметы подрядчика укажите executor_id")
            self._check_contractor(payload.executor_id)
            self._check_contract(payload.contract_id, payload.executor_id)
        elif payload.executor_id or payload.contract_id:
            raise HTTPException(status_code=422, detail="Исполнитель и договор задаются только для сметы подрядчика")
        est = Estimate(**data, created_by=user_id)
        if payload.object:
            est.object_id, est.object_type = payload.object.object_id, payload.object.object_type
        self.db.add(est)
        self.db.commit()
        return self.get_estimate(est.id)

    def update_estimate(self, estimate_id: int, payload: EstimateUpdate, user_id: str) -> dict:
        est = self._estimate(estimate_id)
        data = payload.model_dump(exclude_unset=True)
        if "object" in data:
            obj = payload.object
            if obj:
                self._check_object(obj.object_id, obj.object_type)
            est.object_id, est.object_type = (obj.object_id, obj.object_type) if obj else (None, None)
            data.pop("object")
        for key in ("customer_id", "investor_id", "contractor_id"):
            self._check_contractor(data.get(key))
        if {"executor_id", "contract_id"} & set(data):
            if est.kind != "contractor":
                raise HTTPException(status_code=422, detail="Исполнитель и договор задаются только для сметы подрядчика")
            if "executor_id" in data and (not data["executor_id"] or data["executor_id"] != est.executor_id):
                if est.approval_status == "approved":
                    raise HTTPException(status_code=409, detail="Смета утверждена: сначала снимите утверждение")
                if not data["executor_id"]:
                    raise HTTPException(status_code=422, detail="У сметы подрядчика должен быть исполнитель")
                self._check_contractor(data["executor_id"])
            self._check_contract(data.get("contract_id", est.contract_id), data.get("executor_id", est.executor_id))
        for key, value in data.items():
            if key in ("name", "status") and value is None:
                continue
            setattr(est, key, value)
        est.updated_at, est.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_estimate(estimate_id)

    def approve(self, estimate_id: int, user_id: str) -> dict:
        est = self._contractor_estimate(estimate_id)
        if est.approval_status == "approved":
            raise HTTPException(status_code=409, detail="Смета уже утверждена")
        totals = self.get_estimate(estimate_id)["totals"]
        if not totals["customer_total"]:
            raise HTTPException(status_code=422, detail="Нельзя утвердить смету без стоимости: добавьте работы и ресурсы с ценами")
        est.approval_status, est.approved_at, est.approved_by = "approved", msk_now(), user_id
        est.updated_at, est.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_estimate(estimate_id)

    def unapprove(self, estimate_id: int, user_id: str) -> dict:
        est = self._contractor_estimate(estimate_id)
        est.approval_status, est.approved_at, est.approved_by = "pending", None, None
        est.updated_at, est.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_estimate(estimate_id)

    def list_contracts(self, contractor_id: str) -> list[dict]:
        rows = (self.db.query(Contract).filter((Contract.contractor_id == contractor_id) | (Contract.customer_id == contractor_id))
                .order_by(Contract.date.desc(), Contract.id.desc()).all())
        return [self._contract_view(c) for c in rows]

    def delete_estimate(self, estimate_id: int) -> None:
        self.db.delete(self._estimate(estimate_id))
        self.db.commit()

    def get_estimate(self, estimate_id: int) -> dict:
        est = self._estimate(estimate_id)
        sections = self.db.query(EstimateSection).filter_by(estimate_id=estimate_id).order_by(EstimateSection.position, EstimateSection.id).all()
        section_ids = [s.id for s in sections]
        works = self.db.query(EstimateWork).filter(EstimateWork.section_id.in_(section_ids)).order_by(EstimateWork.position, EstimateWork.id).all() if section_ids else []
        work_ids = [w.id for w in works]
        periods = self.db.query(EstimateWorkPeriod).filter(EstimateWorkPeriod.work_id.in_(work_ids)).order_by(EstimateWorkPeriod.date_from, EstimateWorkPeriod.id).all() if work_ids else []
        resources = self.db.query(EstimateResource).filter(EstimateResource.work_id.in_(work_ids)).order_by(EstimateResource.position, EstimateResource.id).all() if work_ids else []
        names = self._contractor_names([r.contractor_id for r in resources if r.contractor_id])
        done_by_work = dict(self.db.query(EstimateWorkProgress.work_id, func.sum(EstimateWorkProgress.quantity)).filter(EstimateWorkProgress.work_id.in_(work_ids)).group_by(EstimateWorkProgress.work_id).all()) if work_ids else {}

        periods_by_work, resources_by_work, works_by_section = defaultdict(list), defaultdict(list), defaultdict(list)
        for p in periods:
            periods_by_work[p.work_id].append(p)
        for r in resources:
            resources_by_work[r.work_id].append(r)
        for w in works:
            works_by_section[w.section_id].append(w)

        out_sections, estimate_acc = [], self._acc()
        for si, s in enumerate(sections, start=1):
            section_acc, out_works = self._acc(), []
            for wi, w in enumerate(works_by_section[s.id], start=1):
                out_resources = [self._resource(r, ri, names) for ri, r in enumerate(resources_by_work[w.id], start=1)]
                work_acc = self._acc()
                for r in out_resources:
                    self._add(work_acc, r)
                out_periods = [self._period(p) for p in periods_by_work[w.id]]
                schedule = self._schedule(out_periods)
                out_works.append({
                    "id": w.id, "section_id": s.id, "position": w.position, "number": f"{si}.{wi}", "name": w.name,
                    "unit_name": w.unit_name, **progress_view(w.quantity, done_by_work.get(w.id, 0)),
                    "periods": out_periods, **schedule, "resources": out_resources, "totals": self._finish(work_acc),
                })
                self._merge(section_acc, work_acc)
            out_sections.append({
                "id": s.id, "position": s.position, "number": str(si), "name": s.name,
                "works": out_works, "totals": self._finish(section_acc),
            })
            self._merge(estimate_acc, section_acc)
        head = self._estimate_head(est, self._finish(estimate_acc))
        return {**head, "sections": out_sections}

    def get_schedule(self, estimate_id: int) -> dict:
        full = self.get_estimate(estimate_id)
        items = []
        for s in full["sections"]:
            for w in s["works"]:
                for p in w["periods"]:
                    items.append({
                        "work_id": w["id"], "number": w["number"], "work_name": w["name"], "section_name": s["name"],
                        "period_id": p["id"], "date_from": p["date_from"], "date_to": p["date_to"], "days": p["days"],
                    })
        items.sort(key=lambda i: (i["date_from"], i["number"]))
        dates = [(i["date_from"], i["date_to"]) for i in items]
        return {
            "estimate_id": estimate_id, "date_from": min((d[0] for d in dates), default=None),
            "date_to": max((d[1] for d in dates), default=None), "items": items,
            "works_without_schedule": [{"id": w["id"], "number": w["number"], "name": w["name"]} for s in full["sections"] for w in s["works"] if not w["periods"]],
        }

    # ---------- sections / works ----------
    def create_section(self, estimate_id: int, payload: SectionCreate) -> dict:
        self._estimate(estimate_id)
        row = EstimateSection(estimate_id=estimate_id, name=payload.name, position=0)
        self._insert(row, self._siblings(EstimateSection, estimate_id=estimate_id), payload.position)
        self.db.commit()
        return self.get_estimate(estimate_id)

    def update_section(self, section_id: int, payload: SectionUpdate) -> dict:
        row = self._section(section_id)
        if payload.name:
            row.name = payload.name
        if payload.position:
            self._move(row, self._siblings(EstimateSection, estimate_id=row.estimate_id), payload.position)
        self.db.commit()
        return self.get_estimate(row.estimate_id)

    def delete_section(self, section_id: int) -> dict:
        row = self._section(section_id)
        estimate_id = row.estimate_id
        self.db.delete(row)
        self.db.flush()
        self._renumber(self._siblings(EstimateSection, estimate_id=estimate_id))
        self.db.commit()
        return self.get_estimate(estimate_id)

    def create_work(self, section_id: int, payload: WorkCreate) -> dict:
        section = self._section(section_id)
        name, template = payload.name, []
        unit_name, quantity = payload.unit_name, payload.quantity
        if payload.price_item_id:
            catalog = PriceCatalogService(self.db, "works", self.reference_repo)
            item = catalog.get_item(payload.price_item_id)
            name = name or item["name"]
            if "unit_name" not in payload.model_fields_set:
                unit_name = item["unit_name"]
            if "quantity" not in payload.model_fields_set:
                quantity = Decimal(str(item["quantity"]))
            template = catalog.get_template_resources(payload.price_item_id)
        if not name:
            raise HTTPException(status_code=422, detail="Укажите name или price_item_id")
        row = EstimateWork(section_id=section_id, name=name, unit_name=unit_name, quantity=quantity or Decimal(0), position=0)
        self._insert(row, self._siblings(EstimateWork, section_id=section_id), payload.position)
        for position, t in enumerate(template, start=1):
            self.db.add(EstimateResource(
                work_id=row.id, position=position, type=t.type, name=t.name, contractor_id=t.contractor_id,
                quantity=t.quantity, unit_name=t.unit_name, unit_price=t.unit_price, markup_percent=t.markup_percent,
            ))
        self.db.commit()
        return self.get_estimate(section.estimate_id)

    def update_work(self, work_id: int, payload: WorkUpdate) -> dict:
        row = self._work(work_id)
        section = self._section(row.section_id)
        if payload.name:
            row.name = payload.name
        if "unit_name" in payload.model_fields_set:
            row.unit_name = payload.unit_name
        if payload.quantity is not None:
            row.quantity = payload.quantity
        if payload.section_id and payload.section_id != row.section_id:
            target = self._section(payload.section_id)
            if target.estimate_id != section.estimate_id:
                raise HTTPException(status_code=422, detail="Работу можно перенести только в раздел той же сметы")
            old_section = row.section_id
            row.section_id = target.id
            self.db.flush()
            self._renumber(self._siblings(EstimateWork, section_id=old_section))
            others = [w for w in self._siblings(EstimateWork, section_id=target.id) if w.id != row.id]
            self._insert(row, others, payload.position, already_attached=True)
        elif payload.position:
            self._move(row, self._siblings(EstimateWork, section_id=row.section_id), payload.position)
        self.db.commit()
        return self.get_estimate(section.estimate_id)

    def delete_work(self, work_id: int) -> dict:
        row = self._work(work_id)
        section = self._section(row.section_id)
        self.db.delete(row)
        self.db.flush()
        self._renumber(self._siblings(EstimateWork, section_id=section.id))
        self.db.commit()
        return self.get_estimate(section.estimate_id)

    # ---------- schedule periods ----------
    def add_period(self, work_id: int, payload: PeriodCreate) -> dict:
        work = self._work(work_id)
        self._check_period(work_id, payload.date_from, payload.date_to, None)
        self.db.add(EstimateWorkPeriod(work_id=work_id, date_from=payload.date_from, date_to=payload.date_to))
        self.db.commit()
        return self.get_estimate(self._section(work.section_id).estimate_id)

    def update_period(self, period_id: int, payload: PeriodUpdate) -> dict:
        row = self._period_row(period_id)
        date_from, date_to = payload.date_from or row.date_from, payload.date_to or row.date_to
        self._check_period(row.work_id, date_from, date_to, row.id)
        row.date_from, row.date_to = date_from, date_to
        self.db.commit()
        return self.get_estimate(self._estimate_id_of_work(row.work_id))

    def delete_period(self, period_id: int) -> dict:
        row = self._period_row(period_id)
        estimate_id = self._estimate_id_of_work(row.work_id)
        self.db.delete(row)
        self.db.commit()
        return self.get_estimate(estimate_id)

    def _check_period(self, work_id: int, date_from, date_to, exclude_id: int | None) -> None:
        if date_to < date_from:
            raise HTTPException(status_code=422, detail="Дата окончания раньше даты начала")
        for p in self.db.query(EstimateWorkPeriod).filter_by(work_id=work_id).all():
            if p.id != exclude_id and date_from <= p.date_to and p.date_from <= date_to:
                raise HTTPException(status_code=422, detail=f"Период пересекается с уже заданным ({p.date_from:%d.%m.%Y} - {p.date_to:%d.%m.%Y})")

    # ---------- resources ----------
    def create_resource(self, work_id: int, payload: ResourceCreate) -> dict:
        work = self._work(work_id)
        data = payload.model_dump(exclude={"position", "price_item_id"})
        if payload.price_item_id:
            item = PriceCatalogService(self.db, "resources", self.reference_repo).get_item(payload.price_item_id)
            from_catalog = {"type": item["type"], "name": item["name"], "unit_name": item["unit_name"], "unit_price": Decimal(str(item["price"])), "contractor_id": item["contractor_id"]}
            data.update({k: v for k, v in from_catalog.items() if k not in payload.model_fields_set})
        if not data.get("type") or not data.get("name"):
            raise HTTPException(status_code=422, detail="Укажите type и name или price_item_id")
        self._check_contractor(data.get("contractor_id"))
        row = EstimateResource(work_id=work_id, position=0, **data)
        self._insert(row, self._siblings(EstimateResource, work_id=work_id), payload.position)
        self.db.commit()
        return self.get_estimate(self._section(work.section_id).estimate_id)

    def update_resource(self, resource_id: int, payload: ResourceUpdate) -> dict:
        row = self._resource_row(resource_id)
        data = payload.model_dump(exclude_unset=True)
        position = data.pop("position", None)
        if "contractor_id" in data:
            self._check_contractor(data["contractor_id"])
        for key, value in data.items():
            if value is None and key not in ("contractor_id", "unit_name"):
                continue
            setattr(row, key, value)
        if position:
            self._move(row, self._siblings(EstimateResource, work_id=row.work_id), position)
        self.db.commit()
        return self.get_estimate(self._estimate_id_of_work(row.work_id))

    def delete_resource(self, resource_id: int) -> dict:
        row = self._resource_row(resource_id)
        work_id = row.work_id
        estimate_id = self._estimate_id_of_work(work_id)
        self.db.delete(row)
        self.db.flush()
        self._renumber(self._siblings(EstimateResource, work_id=work_id))
        self.db.commit()
        return self.get_estimate(estimate_id)

    # ---------- save to the price catalog ----------
    def save_work_to_catalog(self, work_id: int, payload: SaveToCatalog, user_id: str) -> dict:
        work = self._work(work_id)
        catalog = PriceCatalogService(self.db, "works", self.reference_repo)
        self._reject_duplicate(catalog, work.name, payload.folder_id, None)
        resources = self.db.query(EstimateResource).filter_by(work_id=work_id).order_by(EstimateResource.position, EstimateResource.id).all()
        return catalog.create_item(
            PriceItemCreate(
                folder_id=payload.folder_id, name=work.name, unit_name=work.unit_name, quantity=work.quantity,
                resources=[
                    TemplateResourceCreate(
                        type=r.type, name=r.name, contractor_id=r.contractor_id, quantity=r.quantity,
                        unit_name=r.unit_name, unit_price=r.unit_price, markup_percent=r.markup_percent,
                    ) for r in resources
                ],
            ), user_id,
        )

    def save_resource_to_catalog(self, resource_id: int, payload: SaveToCatalog, user_id: str) -> dict:
        r = self._resource_row(resource_id)
        catalog = PriceCatalogService(self.db, "resources", self.reference_repo)
        self._reject_duplicate(catalog, r.name, payload.folder_id, r.type)
        return catalog.create_item(
            PriceItemCreate(folder_id=payload.folder_id, name=r.name, type=r.type, unit_name=r.unit_name, price=r.unit_price, contractor_id=r.contractor_id), user_id,
        )

    @staticmethod
    def _reject_duplicate(catalog: PriceCatalogService, name: str, folder_id: int | None, item_type: str | None) -> None:
        if folder_id:
            catalog._folder(folder_id)
        existing = catalog.find_duplicate(name, folder_id, item_type)
        if existing:
            raise HTTPException(status_code=409, detail={"message": "Такая позиция уже есть в этой папке справочника", "item_id": existing.id, "code": existing.code})

    # ---------- numbering helpers ----------
    def _siblings(self, model, **filters) -> list:
        return self.db.query(model).filter_by(**filters).order_by(model.position, model.id).all()

    def _renumber(self, rows: list) -> None:
        for i, r in enumerate(rows, start=1):
            r.position = i

    def _insert(self, row, siblings: list, position: int | None, already_attached: bool = False) -> None:
        if not already_attached:
            self.db.add(row)
        index = len(siblings) if not position else min(position - 1, len(siblings))
        ordered = [s for s in siblings if s is not row]
        ordered.insert(index, row)
        self._renumber(ordered)
        self.db.flush()

    def _move(self, row, siblings: list, position: int) -> None:
        ordered = [s for s in siblings if s.id != row.id]
        ordered.insert(min(position - 1, len(ordered)), row)
        self._renumber(ordered)

    # ---------- lookups ----------
    def _estimate(self, estimate_id: int) -> Estimate:
        row = self.db.query(Estimate).filter_by(id=estimate_id).first()
        if not row:
            raise not_found("Смета")
        return row

    def _section(self, section_id: int) -> EstimateSection:
        row = self.db.query(EstimateSection).filter_by(id=section_id).first()
        if not row:
            raise not_found("Раздел")
        return row

    def _work(self, work_id: int) -> EstimateWork:
        row = self.db.query(EstimateWork).filter_by(id=work_id).first()
        if not row:
            raise not_found("Работа")
        return row

    def _period_row(self, period_id: int) -> EstimateWorkPeriod:
        row = self.db.query(EstimateWorkPeriod).filter_by(id=period_id).first()
        if not row:
            raise not_found("Период")
        return row

    def _resource_row(self, resource_id: int) -> EstimateResource:
        row = self.db.query(EstimateResource).filter_by(id=resource_id).first()
        if not row:
            raise not_found("Ресурс")
        return row

    def _estimate_id_of_work(self, work_id: int) -> int:
        return self._section(self._work(work_id).section_id).estimate_id

    def _check_object(self, object_id: str, object_type: str) -> None:
        if self.reference_repo and not self._object_name(object_id, object_type):
            raise HTTPException(status_code=404, detail="Объект не найден")

    def _object_name(self, object_id: str | None, object_type: str | None) -> str | None:
        if not self.reference_repo or not object_id:
            return None
        if object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            return (objs[0].short_name or objs[0].full_name) if objs else None
        return self.reference_repo.resolve_object_name(object_id)

    def _check_contractor(self, contractor_id: str | None) -> None:
        if contractor_id and self.reference_repo and contractor_id not in self.reference_repo.get_counterparty_names([contractor_id]):
            raise HTTPException(status_code=404, detail="Подрядчик (контрагент) не найден")

    def _contractor_estimate(self, estimate_id: int) -> Estimate:
        est = self._estimate(estimate_id)
        if est.kind != "contractor":
            raise HTTPException(status_code=422, detail="Утверждается только смета подрядчика")
        return est

    def _check_contract(self, contract_id: int | None, contractor_id: str | None) -> None:
        if contract_id is None:
            return
        contract = self.db.get(Contract, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Договор не найден в реестре договоров")
        if contractor_id not in (contract.contractor_id, contract.customer_id):
            raise HTTPException(status_code=422, detail="Договор заключён не с этим подрядчиком")

    @staticmethod
    def _contract_view(c: Contract) -> dict:
        return {
            "id": c.id, "num": c.num, "internal_num": c.internal_num, "date": c.date, "name": c.name,
            "date_start": c.date_start, "date_end": c.date_end, "sum": c.sum, "type": c.type,
        }

    def _party(self, counterparty_id: str | None) -> dict | None:
        if not counterparty_id:
            return None
        return {"id": counterparty_id, "name": self._contractor_names([counterparty_id]).get(counterparty_id)}

    def _contractor_names(self, ids: list[str]) -> dict[str, str]:
        return self.reference_repo.get_counterparty_names(list(set(ids))) if self.reference_repo and ids else {}

    # ---------- calculation / serialization ----------
    @staticmethod
    def _acc() -> dict:
        return {"cost": Decimal(0), "customer_total": Decimal(0), "by_type": {t: {"cost": Decimal(0), "customer_total": Decimal(0)} for t in RESOURCE_TYPES}}

    @staticmethod
    def _add(acc: dict, resource: dict) -> None:
        acc["cost"] += Decimal(str(resource["cost"]))
        acc["customer_total"] += Decimal(str(resource["customer_total"]))
        acc["by_type"][resource["type"]]["cost"] += Decimal(str(resource["cost"]))
        acc["by_type"][resource["type"]]["customer_total"] += Decimal(str(resource["customer_total"]))

    @staticmethod
    def _merge(target: dict, source: dict) -> None:
        target["cost"] += source["cost"]
        target["customer_total"] += source["customer_total"]
        for t in RESOURCE_TYPES:
            target["by_type"][t]["cost"] += source["by_type"][t]["cost"]
            target["by_type"][t]["customer_total"] += source["by_type"][t]["customer_total"]

    @staticmethod
    def _finish(acc: dict) -> dict:
        return {
            "cost": float(money(acc["cost"])), "customer_total": float(money(acc["customer_total"])),
            "markup_amount": float(money(acc["customer_total"] - acc["cost"])),
            "by_type": {t: {"label": RESOURCE_TYPES[t], "cost": float(money(v["cost"])), "customer_total": float(money(v["customer_total"]))} for t, v in acc["by_type"].items()},
        }

    def _totals_for(self, estimate_ids: list[int]) -> dict[int, dict]:
        return {i: self.get_estimate(i)["totals"] for i in estimate_ids}

    def _estimate_head(self, e: Estimate, totals: dict) -> dict:
        return {
            "id": e.id, "name": e.name, "status": e.status, "status_label": ESTIMATE_STATUSES[e.status], "comment": e.comment,
            "object": {"object_id": e.object_id, "object_type": e.object_type, "name": self._object_name(e.object_id, e.object_type)} if e.object_id else None,
            "customer": self._party(e.customer_id), "investor": self._party(e.investor_id), "contractor": self._party(e.contractor_id),
            "kind": e.kind, "kind_label": ESTIMATE_KINDS[e.kind], "executor": self._party(e.executor_id),
            "contract_id": e.contract_id, "contract": self._contract_view(contract) if (contract := self.db.get(Contract, e.contract_id) if e.contract_id else None) else None,
            "approval_status": e.approval_status, "approval_label": APPROVAL_STATUSES[e.approval_status], "is_approved": e.approval_status == "approved",
            "approved_at": e.approved_at, "approved_by": e.approved_by,
            "totals": totals, "created_at": e.created_at, "created_by": e.created_by, "updated_at": e.updated_at, "updated_by": e.updated_by,
        }

    @staticmethod
    def _resource(r: EstimateResource, index: int, names: dict[str, str]) -> dict:
        qty, price, markup = Decimal(r.quantity), Decimal(r.unit_price), Decimal(r.markup_percent)
        cost = money(qty * price)
        customer_price = money(price * (1 + markup / 100))
        customer_total = money(qty * price * (1 + markup / 100))
        return {
            "id": r.id, "work_id": r.work_id, "position": r.position, "number": index, "type": r.type, "type_label": RESOURCE_TYPES[r.type],
            "name": r.name, "contractor_id": r.contractor_id, "contractor_name": names.get(r.contractor_id),
            "quantity": float(qty), "unit_name": r.unit_name, "unit_price": float(price), "cost": float(cost),
            "markup_percent": float(markup), "customer_price": float(customer_price), "customer_total": float(customer_total),
        }

    @staticmethod
    def _period(p: EstimateWorkPeriod) -> dict:
        return {"id": p.id, "date_from": p.date_from, "date_to": p.date_to, "days": (p.date_to - p.date_from).days + 1}

    @staticmethod
    def _schedule(periods: list[dict]) -> dict:
        return {
            "days_total": sum(p["days"] for p in periods),
            "date_from": min((p["date_from"] for p in periods), default=None),
            "date_to": max((p["date_to"] for p in periods), default=None),
        }

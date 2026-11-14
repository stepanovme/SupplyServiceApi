from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.estimate import RESOURCE_TYPES
from app.models.price_catalog import (
    FolderCreate, FolderUpdate, PriceItemCreate, PriceItemUpdate, PriceResourceFolder, PriceResourceItem,
    PriceWorkFolder, PriceWorkItem, PriceWorkItemResource, TemplateResourceCreate, TemplateResourceUpdate,
)
from app.repositories.reference_object_repository import ReferenceObjectRepository

MODELS = {"works": (PriceWorkFolder, PriceWorkItem), "resources": (PriceResourceFolder, PriceResourceItem)}
CODE_PREFIX = {"works": "Р", "resources": "РС"}  # code is generated: Р-00001, РС-00001
KIND_LABELS = {"works": "Справочник работ", "resources": "Справочник ресурсов"}


class PriceCatalogService:
    def __init__(self, db: Session, kind: str, reference_repo: ReferenceObjectRepository | None = None) -> None:
        self.db = db
        self.kind = kind
        self.Folder, self.Item = MODELS[kind]
        self.reference_repo = reference_repo

    # ---------- folders ----------
    def _folder(self, folder_id: int):
        row = self.db.query(self.Folder).filter_by(id=folder_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Папка не найдена")
        return row

    def _all_folders(self) -> list:
        return self.db.query(self.Folder).order_by(self.Folder.name, self.Folder.id).all()

    def _children_map(self) -> dict:
        children = defaultdict(list)
        for f in self._all_folders():
            children[f.parent_id].append(f)
        return children

    def _descendant_ids(self, folder_id: int, children: dict | None = None) -> list[int]:
        children = children or self._children_map()
        out, stack = [], [folder_id]
        while stack:
            current = stack.pop()
            out.append(current)
            stack.extend(f.id for f in children.get(current, []))
        return out

    def _direct_item_counts(self) -> dict:
        rows = self.db.query(self.Item.folder_id, func.count(self.Item.id)).group_by(self.Item.folder_id).all()
        return {folder_id: n for folder_id, n in rows}

    def get_tree(self) -> dict:
        children, counts = self._children_map(), self._direct_item_counts()

        def build(parent_id):
            nodes = []
            for f in children.get(parent_id, []):
                sub = build(f.id)
                nodes.append({
                    "id": f.id, "name": f.name, "parent_id": f.parent_id, "items_count": counts.get(f.id, 0),
                    "total_items_count": counts.get(f.id, 0) + sum(n["total_items_count"] for n in sub), "folders": sub,
                })
            return nodes

        tree = build(None)
        return {"kind": self.kind, "label": KIND_LABELS[self.kind], "root_items_count": counts.get(None, 0), "folders": tree}

    def get_content(self, folder_id: int | None) -> dict:
        children, counts = self._children_map(), self._direct_item_counts()
        folder = self._folder(folder_id) if folder_id else None
        items = self.db.query(self.Item).filter(self.Item.folder_id == folder_id).order_by(self.Item.name, self.Item.id).all()
        names = self._contractor_names(items)
        totals = self._work_totals([i.id for i in items])
        return {
            "kind": self.kind,
            "folder": {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id} if folder else None,
            "path": self._path(folder),
            "folders": [
                {"id": f.id, "name": f.name, "parent_id": f.parent_id, "folders_count": len(children.get(f.id, [])), "items_count": counts.get(f.id, 0)}
                for f in children.get(folder_id, [])
            ],
            "items": [self._item(i, names, totals) for i in items],
        }

    def _path(self, folder) -> list[dict]:
        path = []
        while folder:
            path.append({"id": folder.id, "name": folder.name})
            folder = self.db.query(self.Folder).filter_by(id=folder.parent_id).first() if folder.parent_id else None
        return list(reversed(path))

    def create_folder(self, payload: FolderCreate, user_id: str) -> dict:
        if payload.parent_id:
            self._folder(payload.parent_id)
        row = self.Folder(name=payload.name.strip(), parent_id=payload.parent_id, created_by=user_id)
        self.db.add(row)
        self.db.commit()
        return {"id": row.id, "name": row.name, "parent_id": row.parent_id, "path": self._path(row)}

    def update_folder(self, folder_id: int, payload: FolderUpdate) -> dict:
        row = self._folder(folder_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("name"):
            row.name = data["name"].strip()
        if "parent_id" in data:
            new_parent = data["parent_id"]
            if new_parent:
                self._folder(new_parent)
                if new_parent in self._descendant_ids(folder_id):
                    raise HTTPException(status_code=422, detail="Нельзя переместить папку саму в себя или в свою подпапку")
            row.parent_id = new_parent
        self.db.commit()
        return {"id": row.id, "name": row.name, "parent_id": row.parent_id, "path": self._path(row)}

    def delete_folder(self, folder_id: int, recursive: bool) -> None:
        row = self._folder(folder_id)
        ids = self._descendant_ids(folder_id)
        items = self.db.query(func.count(self.Item.id)).filter(self.Item.folder_id.in_(ids)).scalar()
        if (len(ids) > 1 or items) and not recursive:
            raise HTTPException(status_code=409, detail=f"Папка не пустая: подпапок {len(ids) - 1}, позиций {items}. Удалить вместе с содержимым: recursive=true")
        self.db.delete(row)
        self.db.commit()

    # ---------- items ----------
    def _item_row(self, item_id: int):
        row = self.db.query(self.Item).filter_by(id=item_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Позиция не найдена")
        return row

    def search_items(self, search: str | None, folder_id: int | None, include_subfolders: bool, item_type: str | None, limit: int, offset: int) -> dict:
        q = self.db.query(self.Item)
        if folder_id:
            self._folder(folder_id)
            ids = self._descendant_ids(folder_id) if include_subfolders else [folder_id]
            q = q.filter(self.Item.folder_id.in_(ids))
        if item_type:
            if self.kind != "resources":
                raise HTTPException(status_code=422, detail="Фильтр type есть только у справочника ресурсов")
            q = q.filter(self.Item.type == item_type)
        if search and search.strip():
            like = f"%{search.strip()}%"
            q = q.filter(or_(self.Item.name.like(like), self.Item.code.like(like)))
        total = q.count()
        rows = q.order_by(self.Item.name, self.Item.id).offset(offset).limit(limit).all()
        names = self._contractor_names(rows)
        folder_names = {f.id: f.name for f in self._all_folders()}
        totals = self._work_totals([r.id for r in rows])
        items = [{**self._item(r, names, totals), "folder_name": folder_names.get(r.folder_id)} for r in rows]
        return {"kind": self.kind, "total": total, "limit": limit, "offset": offset, "items": items}

    def get_item(self, item_id: int) -> dict:
        row = self._item_row(item_id)
        out = {**self._item(row, self._contractor_names([row]), self._work_totals([row.id])), "path": self._path(self._folder(row.folder_id)) if row.folder_id else []}
        if self.kind == "works":
            out["resources"] = self._template_view(self.get_template_resources(row.id))
        return out

    def create_item(self, payload: PriceItemCreate, user_id: str) -> dict:
        data = payload.model_dump()
        template_resources = payload.resources
        self._check_item_data(data, creating=True)
        for r in template_resources:
            self._check_contractor(r.contractor_id)
        data = self._clean(data)
        if self.kind == "resources" and data.get("price") is None:
            data["price"] = Decimal(0)
        if self.kind == "works" and data.get("quantity") is None:
            data["quantity"] = Decimal(0)
        row = self.Item(**data, created_by=user_id)
        self.db.add(row)
        self.db.flush()
        row.code = f"{CODE_PREFIX[self.kind]}-{row.id:05d}"
        for position, r in enumerate(template_resources, start=1):
            self.db.add(PriceWorkItemResource(item_id=row.id, position=position, **r.model_dump(exclude={"position"})))
        self.db.commit()
        return self.get_item(row.id)

    def find_duplicate(self, name: str, folder_id: int | None, item_type: str | None = None):
        q = self.db.query(self.Item).filter(self.Item.folder_id == folder_id, func.lower(self.Item.name) == name.strip().lower())
        if self.kind == "resources" and item_type:
            q = q.filter(self.Item.type == item_type)
        return q.first()

    def update_item(self, item_id: int, payload: PriceItemUpdate, user_id: str) -> dict:
        row = self._item_row(item_id)
        data = payload.model_dump(exclude_unset=True)
        self._check_item_data(data, creating=False)
        for key, value in self._clean(data).items():
            if value is None and key not in ("folder_id", "unit_name", "comment", "contractor_id"):
                continue
            setattr(row, key, value)
        row.updated_at, row.updated_by = msk_now(), user_id
        self.db.commit()
        return self.get_item(item_id)

    def delete_item(self, item_id: int) -> None:
        self.db.delete(self._item_row(item_id))
        self.db.commit()

    def _check_item_data(self, data: dict, creating: bool) -> None:
        if data.get("folder_id"):
            self._folder(data["folder_id"])
        if self.kind == "works":
            if any(data.get(k) not in (None, "") for k in ("type", "contractor_id", "price")):
                raise HTTPException(status_code=422, detail="У работы нет своих типа, подрядчика и цены: она складывается из ресурсов (поле resources)")
            return
        if data.get("quantity") is not None:
            raise HTTPException(status_code=422, detail="Количество (quantity) есть только у работ")
        if data.get("resources"):
            raise HTTPException(status_code=422, detail="Состав (resources) есть только у работ")
        if creating and not data.get("type"):
            raise HTTPException(status_code=422, detail="Укажите вид ресурса (type): material, machine, overhead или labor")
        cid = data.get("contractor_id")
        if cid and self.reference_repo and cid not in self.reference_repo.get_counterparty_names([cid]):
            raise HTTPException(status_code=404, detail="Подрядчик (контрагент) не найден")

    def _clean(self, data: dict) -> dict:
        if self.kind == "works":
            return {k: v for k, v in data.items() if k not in ("type", "contractor_id", "price", "resources")}
        return {k: v for k, v in data.items() if k not in ("resources", "quantity")}

    def _check_contractor(self, contractor_id: str | None) -> None:
        if contractor_id and self.reference_repo and contractor_id not in self.reference_repo.get_counterparty_names([contractor_id]):
            raise HTTPException(status_code=404, detail="Подрядчик (контрагент) не найден")

    def _contractor_names(self, items: list) -> dict[str, str]:
        ids = list({i.contractor_id for i in items if getattr(i, "contractor_id", None)})
        return self.reference_repo.get_counterparty_names(ids) if ids and self.reference_repo else {}

    def _item(self, row, names: dict, totals: dict | None = None) -> dict:
        out = {
            "id": row.id, "folder_id": row.folder_id, "code": row.code, "name": row.name, "comment": row.comment,
            "created_at": row.created_at, "created_by": row.created_by, "updated_at": row.updated_at, "updated_by": row.updated_by,
        }
        if self.kind == "resources":
            out.update({
                "unit_name": row.unit_name, "price": float(row.price), "type": row.type, "type_label": RESOURCE_TYPES[row.type],
                "contractor_id": row.contractor_id, "contractor_name": names.get(row.contractor_id),
            })
        else:
            out.update({"unit_name": row.unit_name, "quantity": float(row.quantity)})
            out.update((totals or {}).get(row.id, self._empty_totals()))
        return out

    # ---------- composition of a catalog work ----------
    @staticmethod
    def _empty_totals() -> dict:
        return {"resources_count": 0, "cost": 0.0, "customer_total": 0.0}

    def _work_totals(self, item_ids: list[int]) -> dict:
        totals = {i: self._empty_totals() for i in item_ids}
        if self.kind != "works" or not item_ids:
            return totals
        cent = Decimal("0.01")
        acc = defaultdict(lambda: [0, Decimal(0), Decimal(0)])
        for r in self.db.query(PriceWorkItemResource).filter(PriceWorkItemResource.item_id.in_(item_ids)).all():
            a = acc[r.item_id]
            a[0] += 1
            a[1] += (r.quantity * r.unit_price).quantize(cent, rounding=ROUND_HALF_UP)
            a[2] += (r.quantity * r.unit_price * (1 + r.markup_percent / 100)).quantize(cent, rounding=ROUND_HALF_UP)
        for i, (n, cost, customer) in acc.items():
            totals[i] = {"resources_count": n, "cost": float(cost), "customer_total": float(customer)}
        return totals

    def get_template_resources(self, item_id: int) -> list:
        self._item_row(item_id)
        return self.db.query(PriceWorkItemResource).filter_by(item_id=item_id).order_by(PriceWorkItemResource.position, PriceWorkItemResource.id).all()

    def _template_view(self, rows: list) -> list[dict]:
        names = self.reference_repo.get_counterparty_names(list({r.contractor_id for r in rows if r.contractor_id})) if self.reference_repo and rows else {}
        cent = Decimal("0.01")
        return [{
            "id": r.id, "item_id": r.item_id, "position": r.position, "number": i, "type": r.type, "type_label": RESOURCE_TYPES[r.type],
            "name": r.name, "contractor_id": r.contractor_id, "contractor_name": names.get(r.contractor_id),
            "quantity": float(r.quantity), "unit_name": r.unit_name, "unit_price": float(r.unit_price),
            "cost": float((r.quantity * r.unit_price).quantize(cent, rounding=ROUND_HALF_UP)), "markup_percent": float(r.markup_percent),
            "customer_price": float((r.unit_price * (1 + r.markup_percent / 100)).quantize(cent, rounding=ROUND_HALF_UP)),
            "customer_total": float((r.quantity * r.unit_price * (1 + r.markup_percent / 100)).quantize(cent, rounding=ROUND_HALF_UP)),
        } for i, r in enumerate(rows, start=1)]

    def _require_works(self) -> None:
        if self.kind != "works":
            raise HTTPException(status_code=422, detail="Состав есть только у работ")

    def add_template_resource(self, item_id: int, payload: TemplateResourceCreate) -> dict:
        self._require_works()
        rows = self.get_template_resources(item_id)
        self._check_contractor(payload.contractor_id)
        row = PriceWorkItemResource(item_id=item_id, position=0, **payload.model_dump(exclude={"position"}))
        self.db.add(row)
        ordered = list(rows)
        ordered.insert(min((payload.position or len(rows) + 1) - 1, len(rows)), row)
        for i, r in enumerate(ordered, start=1):
            r.position = i
        self.db.commit()
        return self.get_item(item_id)

    def _template_row(self, resource_id: int) -> PriceWorkItemResource:
        row = self.db.query(PriceWorkItemResource).filter_by(id=resource_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Ресурс работы не найден")
        return row

    def update_template_resource(self, resource_id: int, payload: TemplateResourceUpdate) -> dict:
        self._require_works()
        row = self._template_row(resource_id)
        data = payload.model_dump(exclude_unset=True)
        position = data.pop("position", None)
        if "contractor_id" in data:
            self._check_contractor(data["contractor_id"])
        for key, value in data.items():
            if value is None and key not in ("contractor_id", "unit_name"):
                continue
            setattr(row, key, value)
        if position:
            ordered = [r for r in self.get_template_resources(row.item_id) if r.id != row.id]
            ordered.insert(min(position - 1, len(ordered)), row)
            for i, r in enumerate(ordered, start=1):
                r.position = i
        self.db.commit()
        return self.get_item(row.item_id)

    def delete_template_resource(self, resource_id: int) -> dict:
        self._require_works()
        row = self._template_row(resource_id)
        item_id = row.item_id
        self.db.delete(row)
        self.db.flush()
        for i, r in enumerate(self.get_template_resources(item_id), start=1):
            r.position = i
        self.db.commit()
        return self.get_item(item_id)

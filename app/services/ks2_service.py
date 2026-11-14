import math
import re
from copy import copy
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.estimate import Estimate
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.estimate_act_service import EstimateActService

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "ks2_template.xlsx"
FIRST_ROW, TEMPLATE_ROWS, LAST_COL = 32, 7, 33  # строки таблицы работ в шаблоне: 32..38, колонки A..AG
NAME_CHARS_PER_LINE = 45


def fmt_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


class Ks2Service:
    """Унифицированная форма № КС-2 на основании акта по смете (шаблон: app/templates/ks2_template.xlsx)."""

    def __init__(self, db: Session, reference_repo: ReferenceObjectRepository) -> None:
        self.db = db
        self.reference_repo = reference_repo
        self.acts = EstimateActService(db, reference_repo)

    def build(self, act_id: int, contract_id: int | None = None) -> tuple[bytes, str]:
        act = self.acts.get_act(act_id)
        est = self.db.get(Estimate, act["estimate_id"])
        values = self._values(act, est, contract_id)
        wb = load_workbook(TEMPLATE)
        ws = wb.active
        self._replace_placeholders(ws, values)
        self._fill_items(ws, act["items"], Decimal(str(act["totals"]["amount"])))
        out = BytesIO()
        wb.save(out)
        return out.getvalue(), f"КС-2 №{act['number']} от {fmt_date(act['date'])}.xlsx"

    # ---------- data ----------
    def _values(self, act: dict, est: Estimate, contract_id: int | None) -> dict[str, str]:
        if act["kind"] == "customer":
            investor, customer, supplier = est.investor_id, est.customer_id, est.contractor_id
        else:
            investor, customer, supplier = None, est.contractor_id, act["counterparty_id"]
        reqs = self._requisites([i for i in (investor, customer, supplier) if i])
        contract = self._contract(act, contract_id)
        obj_name, obj_address = self._object(est)
        out = {
            "object": obj_name or "", "num_act": str(act["number"]), "date_act": fmt_date(act["date"]),
            "act_date_start": fmt_date(act["date_from"]), "act_date_end": fmt_date(act["date_to"]),
            "sum_act": f"{Decimal(str(act['totals']['amount'])):,.2f}".replace(",", " ").replace(".", ","),
            "contract_num": (contract.num or contract.internal_num or "") if contract else "",
            "contract_date": fmt_date(contract.date) if contract else "",
        }
        for key, cp in (("investor", investor), ("customer", customer), ("supplier", supplier)):
            r = reqs.get(cp) if cp else None
            out[key] = r["title"] if r else ""
            out[f"{key}_okpo"] = r["okpo"] if r else ""
        if obj_address and obj_name:
            out["object_site"] = f"{obj_name}, {obj_address}"
        return out

    def _contract(self, act: dict, contract_id: int | None) -> Contract | None:
        if contract_id is None and act["kind"] == "contractor":
            contract_id = self.db.get(Estimate, act["estimate_id"]).contract_id
        if contract_id is None:
            return None
        contract = self.db.get(Contract, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Договор не найден в реестре договоров")
        return contract

    def _object(self, est: Estimate) -> tuple[str | None, str | None]:
        if not est.object_id:
            return None, None
        if est.object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([est.object_id])
            if objs:
                return (objs[0].short_name or objs[0].full_name), (objs[0].address or None)
            return None, None
        return self.reference_repo.resolve_object_name(est.object_id), None

    def _requisites(self, ids: list[str]) -> dict[str, dict]:
        db = self.reference_repo.db
        names = {str(r.id): r for r in db.execute(text("SELECT id, short_name, full_name FROM counterparties WHERE id IN :ids").bindparams(ids=tuple(ids))).fetchall()} if ids else {}
        details: dict[str, dict] = {}
        for table, fk in (("details_ip", "counterparty_id"), ("details_llc", "counterparties_id")):
            for r in db.execute(text(f"SELECT {fk} AS cid, inn, okpo, legal_address FROM {table} WHERE {fk} IN :ids").bindparams(ids=tuple(ids))).mappings().all() if ids else []:
                details[str(r["cid"])] = dict(r)
        out = {}
        for cid in ids:
            n, d = names.get(cid), details.get(cid, {})
            parts = [(n.short_name or n.full_name) if n else None, f"ИНН {d['inn']}" if d.get("inn") else None,
                     re.sub(r"\s+", " ", d["legal_address"]).strip() if d.get("legal_address") else None]
            out[cid] = {"title": ", ".join(p for p in parts if p), "okpo": d.get("okpo") or ""}
        return out

    # ---------- workbook ----------
    @staticmethod
    def _replace_placeholders(ws, values: dict[str, str]) -> None:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("$"):
                    key = cell.value[1:]
                    if key == "object" and "object_site" in values and cell.coordinate == "E13":
                        cell.value = values["object_site"]  # «Стройка» - наименование и адрес
                    else:
                        cell.value = values.get(key, "") or None

    def _fill_items(self, ws, items: list[dict], total: Decimal) -> None:
        extra = max(len(items) - TEMPLATE_ROWS, 0)
        if extra:
            self._insert_rows(ws, FIRST_ROW + TEMPLATE_ROWS, extra)
        for index, item in enumerate(items):
            r = FIRST_ROW + index
            ws[f"A{r}"] = str(index + 1)
            ws[f"C{r}"] = item["number"]
            ws[f"F{r}"] = item["name"]
            ws[f"Q{r}"] = item["unit_name"]
            ws[f"U{r}"] = item["quantity"]
            ws[f"Y{r}"] = item["unit_price"]
            ws[f"AD{r}"] = item["amount"]
            ws[f"U{r}"].number_format = "#,##0.00##"
            ws[f"Y{r}"].number_format = ws[f"AD{r}"].number_format = "#,##0.00"
            ws[f"F{r}"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.row_dimensions[r].height = 15 * max(math.ceil(len(item["name"] or "") / NAME_CHARS_PER_LINE), 1)
        totals_row = FIRST_ROW + max(len(items), TEMPLATE_ROWS)
        for r in (totals_row, totals_row + 1):
            ws[f"AD{r}"] = float(total)
            ws[f"AD{r}"].number_format = "#,##0.00"
        ws.print_area = f"A1:AG{51 + extra}"

    @staticmethod
    def _insert_rows(ws, at_row: int, count: int) -> None:
        below = [m for m in ws.merged_cells.ranges if m.min_row >= at_row]
        pattern = [m for m in ws.merged_cells.ranges if m.min_row == m.max_row == at_row - 1]
        heights = {r: ws.row_dimensions[r].height for r in range(at_row, ws.max_row + 1)}
        for m in below:
            ws.unmerge_cells(str(m))
        ws.insert_rows(at_row, count)
        for m in below:
            ws.merge_cells(start_row=m.min_row + count, start_column=m.min_col, end_row=m.max_row + count, end_column=m.max_col)
        for r, h in heights.items():
            ws.row_dimensions[r + count].height = h
        for k in range(count):
            r = at_row + k
            ws.row_dimensions[r].height = 15
            for col in range(1, LAST_COL + 1):
                src, dst = ws.cell(at_row - 1, col), ws.cell(r, col)
                dst._style = copy(src._style)
            for m in pattern:
                ws.merge_cells(start_row=r, start_column=m.min_col, end_row=r, end_column=m.max_col)

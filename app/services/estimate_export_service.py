from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy.orm import Session

from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.models.estimate import RESOURCE_TYPES
from app.services.estimate_service import EstimateService

MONEY = "#,##0.00"
THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="F4F4F4")
LAST_COL = "F"


def fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


class EstimateExportService:
    """Выгрузка сметы для заказчика (xlsx): только цены заказчика, без себестоимости и наценки."""

    def __init__(self, db: Session, reference_repo: ReferenceObjectRepository) -> None:
        self.estimates = EstimateService(db, reference_repo)

    def customer_xlsx(
        self, estimate_id: int, include_works: bool = True, include_resources: bool = True, resource_types: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """resource_types ограничивает и строки, и суммы: в файле всё сходится по выбранным видам ресурсов."""
        est = self._filtered(self.estimates.get_estimate(estimate_id), set(resource_types or RESOURCE_TYPES))
        self.include_works, self.include_resources = include_works, include_resources
        wb = Workbook()
        ws = wb.active
        ws.title = "Смета"
        ws.page_setup.orientation = "landscape"
        for col, width in zip("ABCDEF", (25, 25, 12, 9, 14, 18)):
            ws.column_dimensions[col].width = width

        total = est["totals"]["customer_total"]
        self._head(ws, est, total)
        row = self._table(ws, est, 13)
        self._summary(ws, est, row + 2)
        wb_out = BytesIO()
        wb.save(wb_out)
        return wb_out.getvalue(), f"Смета для заказчика {est['name']} {date.today():%d.%m.%Y}.xlsx"

    @staticmethod
    def _filtered(est: dict, types: set[str]) -> dict:
        by_type = {t: {"label": RESOURCE_TYPES[t], "customer_total": 0.0} for t in RESOURCE_TYPES if t in types}
        for s in est["sections"]:
            s_total = 0.0
            for w in s["works"]:
                w["resources"] = [r for r in w["resources"] if r["type"] in types]
                w_total = sum(r["customer_total"] for r in w["resources"])
                for r in w["resources"]:
                    by_type[r["type"]]["customer_total"] += r["customer_total"]
                w["totals"] = {"customer_total": w_total}
                s_total += w_total
            s["totals"] = {"customer_total": s_total}
        est["totals"] = {"customer_total": sum(s["totals"]["customer_total"] for s in est["sections"]), "by_type": by_type}
        return est

    @staticmethod
    def _head(ws, est: dict, total: float) -> None:
        ws["E2"], ws["E3"], ws["E4"] = "Приложение № _________________", "к Договору № _________________", 'от "_____"____________20____г.'
        ws.merge_cells("E3:F3"), ws.merge_cells("E4:F4")
        ws.merge_cells("A6:F6")
        ws["A6"] = "СМЕТНЫЙ РАСЧЕТ"
        ws["A6"].font, ws["A6"].alignment = Font(name="Calibri", size=14, bold=True), Alignment(horizontal="center")
        ws["A8"], ws["B8"] = "Дата:", f"{date.today():%d.%m.%Y}"
        ws["A9"], ws["B9"] = "Объект:", (est["object"] or {}).get("name") or est["name"]
        ws["A10"], ws["B10"] = "Заказчик:", (est["customer"] or {}).get("name") or ""
        ws["A11"], ws["E11"] = "Сметная стоимость", f"{fmt_money(total)} руб."
        ws.merge_cells("B9:F9"), ws.merge_cells("B10:F10")
        for r in (2, 3, 4, 8, 9, 10, 11):
            for c in ws[r]:
                c.font = Font(name="Calibri", size=11)

    def _table(self, ws, est: dict, row: int) -> int:
        for col, text in zip("ACDEF", ("Наименование работ и ресурсов", "Кол-во", "Ед.изм", "Цена, руб.", "Стоимость, руб.")):
            ws[f"{col}{row}"] = text
        ws.merge_cells(f"A{row}:B{row}")
        for c in ws[row][:6]:
            c.font, c.fill, c.border = Font(name="Calibri", size=11, bold=True), HEADER_FILL, BORDER
            c.alignment = Alignment(horizontal="center" if c.column <= 2 else "right")
        ws.freeze_panes = f"A{row + 1}"
        for s in est["sections"]:
            row += 1
            self._line(ws, row, f"{s['number']}.{s['name']}", None, None, None, s["totals"]["customer_total"], bold=True, size=12)
            for w in s["works"]:
                if self.include_works:
                    row += 1
                    qty = w["quantity"]
                    price = w["totals"]["customer_total"] / qty if qty else 0
                    self._line(ws, row, f"{w['number']} {w['name']}", qty, w["unit_name"], price, w["totals"]["customer_total"], bold=True)
                if self.include_resources:
                    for r in w["resources"]:
                        row += 1
                        self._line(ws, row, r["name"], r["quantity"], r["unit_name"], r["customer_price"], r["customer_total"])
        return row

    @staticmethod
    def _line(ws, row, name, qty, unit, price, amount, bold=False, size=11) -> None:
        ws.merge_cells(f"A{row}:B{row}")
        for col, value in zip("ACDEF", (name, qty, unit, price, amount)):
            ws[f"{col}{row}"] = value
        for c in ws[row][:6]:
            c.font, c.border = Font(name="Calibri", size=size if c.column == 1 else 11, bold=bold), BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top") if c.column <= 2 else Alignment(horizontal="right", vertical="top")
        ws[f"E{row}"].number_format = ws[f"F{row}"].number_format = MONEY
        chars = len(str(name)) / 50
        ws.row_dimensions[row].height = max(15, 15 * (int(chars) + 1))

    @staticmethod
    def _summary(ws, est: dict, row: int) -> None:
        totals = est["totals"]
        rows = [("Итого по смете, руб.:", totals["customer_total"], True), ("В том числе:", None, False)]
        rows += [(t["label"], t["customer_total"], False) for t in totals["by_type"].values()]
        rows.append(("Всего по смете", totals["customer_total"], True))
        for label, value, bold in rows:
            ws[f"A{row}"], ws[f"E{row}"] = label, value
            ws[f"A{row}"].font = ws[f"E{row}"].font = Font(name="Calibri", size=11, bold=bold)
            ws[f"E{row}"].number_format = MONEY
            row += 1
        ws[f"A{row + 1}"], ws[f"A{row + 3}"] = "Заказчик:________________/_________________/", "Подрядчик:________________/_________________/"

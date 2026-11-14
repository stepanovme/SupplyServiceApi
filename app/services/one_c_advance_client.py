"""Creates a draft "Авансовый отчёт" in 1C (1С:Фреш, OData) from receipts.

The report goes into the section "Товары": a line per receipt position, every line carrying its own
receipt's number, date and supplier. The document is created UNPOSTED - the accountant checks and posts it.

Nomenclature and counterparties of a real 1C base are never created behind its owner's back: that is only
allowed for profiles flagged `is_test` in `1c_profiles`.
"""
import logging
from datetime import date
from types import SimpleNamespace

import httpx

from app.services.one_c_service import OneCService

logger = logging.getLogger(__name__)

DOC = "Document_АвансовыйОтчет"
SECTION = "Товары"
# fiscal receipt VAT code -> value of the 1C enum СтавкиНДС (receipts store 11 = 22 %, 2 = 10 %)
VAT_RATES = {1: "НДС20", 2: "НДС10", 3: "НДС20_120", 4: "НДС10_110", 5: "НДС0", 6: "БезНДС", 11: "НДС22", 12: "НДС22_122"}
TEST_PERSON = {"Description": "Тестов Тест Тестович (supply)", "Фамилия": "Тестов", "Имя": "Тест", "Отчество": "Тестович"}


class OneCAdvanceError(Exception):
    """A problem on the 1C side that the user can act on; `status` is the HTTP status the API answers with."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _describe(response: httpx.Response) -> str:
    text = response.text.replace("\n", " ").strip()
    return f"HTTP {response.status_code}: {text[:300]}"


class OneCAdvanceClient:
    def __init__(self, profile) -> None:
        self.profile = profile
        self.is_test = bool(profile.is_test)
        self.base = profile.api_link.rstrip("/") + "/odata/standard.odata"
        password = OneCService._decrypt_with_key(profile.password)
        self.http = httpx.Client(auth=(profile.username, password), timeout=httpx.Timeout(120.0))

    def close(self) -> None:
        self.http.close()

    # ---- low level -----------------------------------------------------------------------
    def _get(self, entity: str, **params) -> list[dict]:
        try:
            r = self.http.get(f"{self.base}/{entity}", params={"$format": "json", **params})
        except httpx.HTTPError as exc:
            raise OneCAdvanceError(f"1С недоступна ({type(exc).__name__})", 502) from exc
        if r.status_code == 401:
            raise OneCAdvanceError("1С отклонила логин или пароль этого профиля", 502)
        if r.status_code == 404:
            raise OneCAdvanceError(f"В 1С не опубликован объект {entity} (стандартный интерфейс OData)", 502)
        if r.status_code != 200:
            raise OneCAdvanceError(f"Ошибка чтения {entity} в 1С: {_describe(r)}", 502)
        return r.json().get("value", [])

    def _create(self, entity: str, body: dict) -> dict:
        try:
            r = self.http.post(f"{self.base}/{entity}", params={"$format": "json"}, json=body)
        except httpx.HTTPError as exc:
            raise OneCAdvanceError(f"1С недоступна ({type(exc).__name__})", 502) from exc
        if r.status_code not in (200, 201):
            raise OneCAdvanceError(f"1С не приняла {entity}: {_describe(r)}", 502)
        return r.json()

    # ---- options for the UI ---------------------------------------------------------------
    def organizations(self) -> list[dict]:
        rows = self._get("Catalog_Организации", **{"$select": "Ref_Key,Description,ИНН", "$top": "200"})
        return [{"ref_key": r["Ref_Key"], "name": r.get("Description"), "inn": r.get("ИНН") or None} for r in rows]

    def persons(self, search: str | None = None) -> list[dict]:
        rows = self._get("Catalog_ФизическиеЛица", **{"$select": "Ref_Key,Description,ИНН", "$top": "1000"})
        if search:
            needle = search.strip().lower()
            rows = [r for r in rows if needle in (r.get("Description") or "").lower()]
        return [{"ref_key": r["Ref_Key"], "name": r.get("Description"), "inn": r.get("ИНН") or None} for r in rows[:200]]

    # ---- the document ---------------------------------------------------------------------
    def _resolve_header(self, organization_ref_key: str | None, person_ref_key: str | None):
        organizations = self.organizations()
        if organization_ref_key:
            org = next((o for o in organizations if o["ref_key"] == organization_ref_key), None)
            if not org:
                raise OneCAdvanceError("Организация не найдена в этой базе 1С", 422)
        elif len(organizations) == 1:
            org = organizations[0]
        else:
            names = ", ".join(o["name"] or "?" for o in organizations[:8])
            raise OneCAdvanceError(f"В базе несколько организаций — укажите organization_ref_key ({names})", 422)

        people = self._get("Catalog_ФизическиеЛица", **{"$select": "Ref_Key,Description", "$top": "1000"})  # 1C accepts no filter here
        if person_ref_key:
            found = next((p for p in people if p["Ref_Key"] == person_ref_key), None)
            if not found:
                raise OneCAdvanceError("Физическое лицо не найдено в этой базе 1С", 422)
            person = {"ref_key": found["Ref_Key"], "name": found.get("Description")}
        else:
            if people or not self.is_test:
                raise OneCAdvanceError("Укажите подотчётное лицо (person_ref_key)", 422)
            created = self._create("Catalog_ФизическиеЛица", TEST_PERSON)  # only an empty TEST base gets a made-up employee
            person = {"ref_key": created["Ref_Key"], "name": TEST_PERSON["Description"]}
        return org, person

    def send(self, report, groups, options) -> dict:
        """groups: [(receipt, [items])]. Returns {ref_key, number, organization, person, created: {...}, warnings: [...]}."""
        mode = options.nomenclature_mode or ("create" if self.is_test else "match")
        if mode == "create" and not self.is_test:
            raise OneCAdvanceError("Автоматическое создание номенклатуры разрешено только в тестовых профилях 1С", 422)
        if mode == "generic" and not options.generic_nomenclature_ref_key:
            raise OneCAdvanceError("Для режима generic укажите generic_nomenclature_ref_key", 422)

        org, person = self._resolve_header(options.organization_ref_key, options.person_ref_key)
        warehouses = self._get("Catalog_Склады", **{"$select": "Ref_Key", "$top": "1"})

        nomenclature = {r["Description"].strip().lower(): r["Ref_Key"] for r in self._get("Catalog_Номенклатура", **{"$select": "Ref_Key,Description", "$top": "5000"})}
        counterparties = {(r.get("ИНН") or "").strip(): r["Ref_Key"] for r in self._get("Catalog_Контрагенты", **{"$select": "Ref_Key,Description,ИНН", "$top": "5000"}) if (r.get("ИНН") or "").strip()}
        kind = unit = None
        if mode == "create":
            kinds = self._get("Catalog_ВидыНоменклатуры", **{"$select": "Ref_Key,Description", "$top": "50"})
            units = self._get("Catalog_КлассификаторЕдиницИзмерения", **{"$select": "Ref_Key,Description", "$top": "50"})
            kind = next((k["Ref_Key"] for k in kinds if k["Description"] == "Товары"), kinds[0]["Ref_Key"] if kinds else None)
            unit = next((u["Ref_Key"] for u in units if u["Description"] == "шт"), units[0]["Ref_Key"] if units else None)

        # 1) positions of every receipt (a receipt without positions becomes one line with its total)
        lines = []
        for receipt, items in groups:
            positions = list(items) or [
                SimpleNamespace(
                    name=f"Покупка по чеку: {receipt.seller_name or 'продавец не указан'}", quantity=1,
                    price=receipt.total_sum, sum=receipt.total_sum, nds_code=None, nds_sum=None,
                )
            ]
            lines.extend((receipt, p) for p in positions)

        # 2) nomenclature: in "match" mode nothing may stay unmatched, so the problem is reported before 1C is touched
        if mode == "match":
            missing = sorted({p.name.strip() for _r, p in lines if p.name.strip()[:100].lower() not in nomenclature})
            if missing:
                sample = "; ".join(m[:60] for m in missing[:15])
                raise OneCAdvanceError(
                    f"В 1С не найдена номенклатура с таким названием для {len(missing)} позиций (например: {sample}). "
                    "Используйте режим generic с общей номенклатурой или создайте позиции в 1С",
                    422,
                )

        created_nomenclature = created_counterparties = 0
        warnings: list[str] = []

        def nomenclature_ref(name: str) -> str:
            nonlocal created_nomenclature
            if mode == "generic":
                return options.generic_nomenclature_ref_key
            key = name.strip()[:100].lower()
            if key not in nomenclature:
                made = self._create("Catalog_Номенклатура", {
                    "Description": name.strip()[:100], "НаименованиеПолное": name.strip()[:1000],
                    "ВидНоменклатуры_Key": kind, "ЕдиницаИзмерения_Key": unit,
                })
                nomenclature[key] = made["Ref_Key"]
                created_nomenclature += 1
            return nomenclature[key]

        def supplier_ref(receipt) -> str | None:
            nonlocal created_counterparties
            inn = (receipt.seller_inn or "").strip()
            if not inn:
                return None
            if inn in counterparties:
                return counterparties[inn]
            if mode == "create":
                try:
                    made = self._create("Catalog_Контрагенты", {"Description": (receipt.seller_name or inn)[:100], "ИНН": inn})
                except OneCAdvanceError as exc:
                    warnings.append(f"Продавец {inn} не создан в 1С ({exc.message[:120]}), поставщик в строках пуст")
                    counterparties[inn] = None
                    return None
                counterparties[inn] = made["Ref_Key"]
                created_counterparties += 1
                return counterparties[inn]
            warnings.append(f"Продавец с ИНН {inn} не найден в 1С — поставщик в строках пуст")
            counterparties[inn] = None
            return None

        rows = []
        for n, (receipt, p) in enumerate(lines, start=1):
            day = (receipt.purchased_at.date() if receipt.purchased_at else date.today()).isoformat()
            row = {
                "LineNumber": n,  # without it this 1C answers with an internal OData error
                "Номенклатура_Key": nomenclature_ref(p.name),
                "Описание": p.name[:250],
                "Количество": float(p.quantity), "Цена": round(float(p.price), 2), "Сумма": round(float(p.sum), 2),
                "ДатаВходящегоДокумента": f"{day}T00:00:00", "НомерВходящегоДокумента": str(receipt.fd or ""),
                "Поставщик_Key": supplier_ref(receipt),
            }
            rate = VAT_RATES.get(p.nds_code)
            if rate:
                row["СтавкаНДС"] = rate
                if p.nds_sum is not None:
                    row["СуммаНДС"] = float(p.nds_sum)
            rows.append({k: v for k, v in row.items() if v not in (None, "")})

        total = round(sum(r["Сумма"] for r in rows), 2)
        title = f" «{report.title}»" if report.title else ""
        body = {
            "Date": f"{report.report_date.isoformat()}T12:00:00",
            "Организация_Key": org["ref_key"],
            "ФизЛицо_Key": person["ref_key"],
            "Posted": False,
            "Комментарий": f"supply: авансовый отчёт №{report.number}{title}" + (f". {report.comment}" if report.comment else ""),
            "СуммаДокумента": total,
            SECTION: rows,
        }
        if warehouses:
            body["Склад_Key"] = warehouses[0]["Ref_Key"]

        doc = self._create(DOC, body)
        return {
            "ref_key": doc.get("Ref_Key"), "number": doc.get("Number"), "total": total, "lines": len(rows),
            "organization": org, "person": person, "mode": mode, "warnings": warnings,
            "created": {"nomenclature": created_nomenclature, "counterparties": created_counterparties},
        }

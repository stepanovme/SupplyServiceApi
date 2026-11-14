"""TEST ONLY: sends one receipt to the 1C "Тестовая база" as a DRAFT advance report (Авансовый отчёт).

Works with profile id 8 "Тестовая база" (1cfresh .../a/ea/4259905/) and refuses to run against
anything else. The document is created UNPOSTED (Posted=false). Nothing is written to our own
database - the receipt is only read.

Run it ON THE SERVER (the 1C password is encrypted with a key that exists only there), or anywhere with the
test base password in the ONE_C_TEST_PASSWORD environment variable:

  cd /var/www/backend.supply
  venv/bin/python -m cmd.one_c_test_advance_report --discover
  venv/bin/python -m cmd.one_c_test_advance_report --dry-run
  venv/bin/python -m cmd.one_c_test_advance_report --create
  venv/bin/python -m cmd.one_c_test_advance_report --delete <Ref_Key>      # remove a test document

Options for --create / --dry-run:
  --receipt-id ID      which receipt (default: the newest one that has positions)
  --org TEXT           part of the organization name (default: the first organization)
  --person TEXT        part of the person's name (Catalog_ФизическиеЛица; default: the first one)
  --header K=V         extra/override header field, V is JSON (e.g. --header 'Комментарий="тест"')
  --row K=V            extra/override field of the first row of the "Прочее" section (V is JSON)

1C answers with the name of any missing required field; add it with --header / --row and run again.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date

import httpx
from sqlalchemy import text

from app.database import supply_engine
from app.services.one_c_service import OneCService

TEST_PROFILE_ID = 8
TEST_PROFILE_NAME = "Тестовая база"
TEST_BASE_MARK = "4259905"
DOC = "Document_АвансовыйОтчет"
# fiscal receipt VAT code -> value of the 1C enum СтавкиНДС (codes of the receipts we store: 11 = 22 %, 2 = 10 %)
VAT_RATES = {1: "НДС20", 2: "НДС10", 3: "НДС20_120", 4: "НДС10_110", 5: "НДС0", 6: "БезНДС", 11: "НДС22", 12: "НДС22_122"}
SECTION_PREFERENCE = ("Прочее", "Товары")


def load_client():
    with supply_engine.connect() as conn:
        profile = conn.execute(
            text("SELECT id, name, username, password, api_link FROM `1c_profiles` WHERE id = :i"), {"i": TEST_PROFILE_ID}
        ).first()
    if not profile or profile.name != TEST_PROFILE_NAME or TEST_BASE_MARK not in profile.api_link:
        sys.exit(f"REFUSED: profile {TEST_PROFILE_ID} is not the test base ('{TEST_PROFILE_NAME}', .../{TEST_BASE_MARK}/)")
    # The password can be given in ONE_C_TEST_PASSWORD (when the encryption key is not available, e.g. off the
    # server); otherwise the stored one is decrypted. Either way only the test base is ever contacted.
    password = os.getenv("ONE_C_TEST_PASSWORD") or OneCService._decrypt_with_key(profile.password)
    base = profile.api_link.rstrip("/") + "/odata/standard.odata"
    return httpx.Client(auth=(profile.username, password), timeout=httpx.Timeout(120.0)), base


def odata_get(client, base, entity, **params):
    params = {"$format": "json", **params}
    r = client.get(f"{base}/{entity}", params=params)
    if r.status_code != 200:
        sys.exit(f"GET {entity} -> HTTP {r.status_code}: {r.text[:600]}")
    return r.json().get("value", [])


def load_metadata(client, base) -> dict[str, dict[str, str]]:
    """type name -> {property: edm type} for every EntityType / ComplexType in $metadata."""
    r = client.get(f"{base}/$metadata")
    if r.status_code != 200:
        sys.exit(f"GET $metadata -> HTTP {r.status_code}: {r.text[:300]}")
    types: dict[str, dict[str, str]] = {}
    for el in ET.fromstring(r.content).iter():
        if el.tag.endswith("}EntityType") or el.tag.endswith("}ComplexType"):
            types[el.get("Name")] = {p.get("Name"): p.get("Type") for p in el if p.tag.endswith("}Property")}
    return types


def document_shape(types):
    header = types.get(DOC)
    if header is None:
        sys.exit(f"{DOC} is not published in this base's OData (check Администрирование -> Интеграция -> OData)")
    sections = {}
    for name, typ in header.items():
        m = re.match(r"Collection\((?:.*\.)?(.+)\)$", typ or "")
        if m and m.group(1) in types:
            sections[name] = types[m.group(1)]
    return header, sections


def print_shape(types):
    header, sections = document_shape(types)
    print(f"\n{DOC} header fields ({len(header)}):")
    for k, v in header.items():
        if k not in sections:
            print(f"   {k}: {v}")
    for name, fields in sections.items():
        print(f"\n   section {name} row fields:")
        for k, v in fields.items():
            print(f"      {k}: {v}")


def newest_receipt_ids(n):
    with supply_engine.connect() as conn:
        return [r[0] for r in conn.execute(
            text("SELECT r.id FROM purchase_receipts r WHERE EXISTS (SELECT 1 FROM purchase_receipt_items i WHERE i.receipt_id = r.id) ORDER BY r.created_at DESC LIMIT :n"),
            {"n": n},
        )]


def load_receipt(receipt_id):
    with supply_engine.connect() as conn:
        if receipt_id is None:
            receipt_id = conn.execute(
                text(
                    "SELECT r.id FROM purchase_receipts r WHERE EXISTS (SELECT 1 FROM purchase_receipt_items i WHERE i.receipt_id = r.id) "
                    "ORDER BY r.created_at DESC LIMIT 1"
                )
            ).scalar()
        r = conn.execute(
            text(
                "SELECT id, purchased_at, total_sum, seller_name, seller_inn, retail_place, fd, fn, fp, payment_method FROM purchase_receipts WHERE id = :i"
            ),
            {"i": receipt_id},
        ).first()
        if not r:
            sys.exit("receipt not found")
        items = conn.execute(
            text("SELECT position, name, quantity, price, sum, nds_code, nds_sum FROM purchase_receipt_items WHERE receipt_id = :i ORDER BY position"),
            {"i": receipt_id},
        ).fetchall()
    return r, items


def ensure_person(client, base, needle, create):
    rows = odata_get(client, base, "Catalog_ФизическиеЛица", **{"$select": "Ref_Key,Description", "$top": "200"})
    if rows:
        return pick(rows, needle, "person")
    if not create:
        sys.exit("the test base has no persons (Catalog_ФизическиеЛица); run with --create-person to add a test employee there")
    body = {"Description": "Тестов Тест Тестович (supply)", "Фамилия": "Тестов", "Имя": "Тест", "Отчество": "Тестович"}
    r = client.post(f"{base}/Catalog_ФизическиеЛица", params={"$format": "json"}, json=body)
    print("created test person in the TEST base -> HTTP", r.status_code)
    if r.status_code not in (200, 201):
        sys.exit(r.text[:1200])
    return {"Ref_Key": r.json()["Ref_Key"], "Description": body["Description"]}


def _create(client, base, entity, body):
    r = client.post(f"{base}/{entity}", params={"$format": "json"}, json=body)
    if r.status_code not in (200, 201):
        return None, f"HTTP {r.status_code}: {r.text.replace(chr(10), ' ')[:300]}"
    return r.json()["Ref_Key"], None


class Catalogs:
    """Finds (or, in the TEST base, creates) the 1C nomenclature and counterparties a receipt refers to."""

    def __init__(self, client, base):
        self.client, self.base = client, base
        self.nomenclature = {r["Description"].strip().lower(): r["Ref_Key"] for r in odata_get(client, base, "Catalog_Номенклатура", **{"$select": "Ref_Key,Description", "$top": "5000"})}
        self.counterparties = {(r.get("ИНН") or "").strip(): r["Ref_Key"] for r in odata_get(client, base, "Catalog_Контрагенты", **{"$select": "Ref_Key,Description,ИНН", "$top": "5000"}) if (r.get("ИНН") or "").strip()}
        kinds = odata_get(client, base, "Catalog_ВидыНоменклатуры", **{"$select": "Ref_Key,Description", "$top": "50"})
        units = odata_get(client, base, "Catalog_КлассификаторЕдиницИзмерения", **{"$select": "Ref_Key,Description", "$top": "50"})
        self.kind = next((k["Ref_Key"] for k in kinds if k["Description"] == "Товары"), kinds[0]["Ref_Key"] if kinds else None)
        self.unit = next((u["Ref_Key"] for u in units if u["Description"] == "шт"), units[0]["Ref_Key"] if units else None)
        self.created_nomenclature = self.created_counterparties = 0
        self.warnings: list[str] = []

    def item(self, name: str):
        key = name.strip()[:100].lower()
        if key in self.nomenclature:
            return self.nomenclature[key]
        body = {"Description": name.strip()[:100], "НаименованиеПолное": name.strip()[:1000], "ВидНоменклатуры_Key": self.kind, "ЕдиницаИзмерения_Key": self.unit}
        ref, err = _create(self.client, self.base, "Catalog_Номенклатура", body)
        if err:
            sys.exit(f"cannot create nomenclature '{name[:40]}': {err}")
        self.nomenclature[key] = ref
        self.created_nomenclature += 1
        return ref

    def seller(self, receipt):
        inn = (receipt.seller_inn or "").strip()
        if not inn:
            return None
        if inn in self.counterparties:
            return self.counterparties[inn]
        body = {"Description": (receipt.seller_name or inn)[:100], "ИНН": inn}
        ref, err = _create(self.client, self.base, "Catalog_Контрагенты", body)
        if err:
            self.warnings.append(f"seller {inn} not created in 1C ({err[:160]}); the line's supplier is left empty")
            self.counterparties[inn] = None
            return None
        self.counterparties[inn] = ref
        self.created_counterparties += 1
        return ref


def build_goods_payload(types, groups, org, person, warehouse, catalogs, header_over, row_over):
    """One advance report for SEVERAL receipts: the section "Товары", a line per receipt position.
    Every line carries its own receipt's number, date and supplier, so the receipts stay distinguishable."""
    header, sections = document_shape(types)
    row_fields = sections.get("Товары")
    if row_fields is None:
        sys.exit(f"no 'Товары' section in {DOC}; sections: {list(sections)}")
    rows, n = [], 0
    for receipt, items in groups:
        day = (receipt.purchased_at.date() if receipt.purchased_at else date.today()).isoformat()
        supplier = catalogs.seller(receipt)
        for i in items:
            n += 1
            qty, price = float(i.quantity), round(float(i.price), 2)
            line = {
                "LineNumber": n,
                "Номенклатура_Key": catalogs.item(i.name),
                "Описание": i.name[:250],
                "Количество": qty, "Цена": price, "Сумма": round(float(i.sum), 2),
                "ДатаВходящегоДокумента": f"{day}T00:00:00", "НомерВходящегоДокумента": str(receipt.fd or ""),
                "Поставщик_Key": supplier,
            }
            rate = VAT_RATES.get(i.nds_code)
            if rate:
                line["СтавкаНДС"] = rate
                if i.nds_sum is not None:
                    line["СуммаНДС"] = float(i.nds_sum)
            line = {k: v for k, v in line.items() if k in row_fields and v not in (None, "")}
            line.update(row_over)
            rows.append(line)
    total = round(sum(r["Сумма"] for r in rows), 2)
    person_field = next((f for f in ("ФизЛицо_Key", "ФизическоеЛицо_Key") if f in header), "ФизЛицо_Key")
    refs = ", ".join(r.id[:8] for r, _ in groups)
    body = {
        "Date": date.today().isoformat() + "T12:00:00", "Организация_Key": org["Ref_Key"], person_field: person["Ref_Key"],
        "Posted": False, "Комментарий": f"ТЕСТ из supply: чеков {len(groups)} ({refs})", "СуммаДокумента": total, "Товары": rows,
    }
    if warehouse and "Склад_Key" in header:
        body["Склад_Key"] = warehouse["Ref_Key"]
    body = {k: v for k, v in body.items() if k in header or k in ("Date", "Posted")}
    body.update(header_over)
    return body, "Товары"


def parse_kv(pairs):
    out = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def pick(rows, needle, label):
    if not rows:
        sys.exit(f"no {label} found in the test base")
    if needle:
        for row in rows:
            if needle.lower() in (row.get("Description") or "").lower():
                return row
        sys.exit(f"{label} containing '{needle}' not found")
    return rows[0]


def build_payload(types, receipt, items, org, person, counterparty, header_over, row_over, warehouse=None, per_position=False):
    header, sections = document_shape(types)
    section = next((s for s in SECTION_PREFERENCE if s in sections), None)
    if section is None:
        sys.exit(f"no '{'/'.join(SECTION_PREFERENCE)}' section in {DOC}; sections: {list(sections)}")
    row_fields = sections[section]
    day = (receipt.purchased_at.date() if receipt.purchased_at else date.today()).isoformat()
    total = float(receipt.total_sum)
    vat = round(sum(float(i.nds_sum or 0) for i in items), 2)
    content = f"Чек {receipt.seller_name or ''} от {day}".strip()

    candidates = {  # our value for a row field, whatever it is called in this configuration
        "Содержание": content, "Сумма": total, "Количество": 1,
        "ДатаДокумента": f"{day}T00:00:00", "НомерДокумента": str(receipt.fd or ""),
        "ДатаВходящегоДокумента": f"{day}T00:00:00", "НомерВходящегоДокумента": str(receipt.fd or ""),
        "ДатаРасхода": f"{day}T00:00:00", "Контрагент_Key": counterparty, "Поставщик_Key": counterparty,
    }
    if vat:  # only when the receipt shows VAT; the rate itself (СтавкаНДС) is configuration specific: use --row
        candidates["СуммаНДС"] = vat
    row = {k: v for k, v in candidates.items() if k in row_fields and v not in (None, "")}
    if "LineNumber" in row_fields:
        row["LineNumber"] = 1  # without it this 1C answers with an internal OData error
    row.update(row_over)

    rows = [row]
    if per_position:  # one line per position of the receipt instead of one line for the whole receipt
        rows = []
        for i in items:
            line = {k: v for k, v in candidates.items() if k in row_fields and k not in ("Содержание", "Сумма", "СуммаНДС") and v not in (None, "")}
            qty = float(i.quantity)
            line["Содержание"] = f"{i.name} ({qty:g} x {float(i.price):.2f})"[:250]
            line["Сумма"] = float(i.sum)
            rate = VAT_RATES.get(i.nds_code)
            if rate and "СтавкаНДС" in row_fields:
                line["СтавкаНДС"] = rate
                if i.nds_sum is not None and "СуммаНДС" in row_fields:
                    line["СуммаНДС"] = float(i.nds_sum)
            line["LineNumber"] = i.position
            line.update(row_over)
            rows.append(line)
        total = round(sum(r["Сумма"] for r in rows), 2)

    person_field = next((f for f in ("ФизЛицо_Key", "ФизическоеЛицо_Key") if f in header), None)
    body = {
        "Date": date.today().isoformat() + "T12:00:00",
        "Организация_Key": org["Ref_Key"],
        person_field or "ФизЛицо_Key": person["Ref_Key"],
        "Posted": False,  # a draft: the accountant checks and posts it
        "Комментарий": f"ТЕСТ из supply: чек {receipt.id}",
        "СуммаДокумента": total,
        section: rows,
    }
    if warehouse and "Склад_Key" in header:
        body["Склад_Key"] = warehouse["Ref_Key"]
    body = {k: v for k, v in body.items() if k in header or k in ("Date", "Posted")}
    body.update(header_over)
    return body, section


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--delete", metavar="REF_KEY")
    ap.add_argument("--receipt-id", action="append", help="repeat to put SEVERAL receipts into one advance report")
    ap.add_argument("--last", type=int, help="the newest N receipts that have positions")
    ap.add_argument("--section", choices=("Товары", "Прочее"), default="Товары")
    ap.add_argument("--org")
    ap.add_argument("--person")
    ap.add_argument("--per-position", action="store_true", help="one 1C line per receipt position (with VAT) instead of one line per receipt")
    ap.add_argument("--create-person", action="store_true", help="create a test employee in the TEST base if it has none")
    ap.add_argument("--header", action="append")
    ap.add_argument("--row", action="append")
    args = ap.parse_args()
    if not (args.discover or args.dry_run or args.create or args.delete):
        ap.print_help()
        return 1

    client, base = load_client()
    print("TEST base:", base)

    if args.delete:
        r = client.delete(f"{base}/{DOC}(guid'{args.delete}')")
        print("DELETE ->", r.status_code, r.text[:300])
        return 0 if r.status_code in (200, 204) else 1

    types = load_metadata(client, base)
    if args.discover:
        print_shape(types)
        print("\norganizations:", [(o["Description"], o.get("ИНН")) for o in odata_get(client, base, "Catalog_Организации", **{"$select": "Ref_Key,Description,ИНН", "$top": "10"})])
        print("persons (first 10):", [p["Description"] for p in odata_get(client, base, "Catalog_ФизическиеЛица", **{"$select": "Ref_Key,Description", "$top": "10"})])
        return 0

    ids = args.receipt_id or (newest_receipt_ids(args.last) if args.last else [None])
    groups = [load_receipt(i) for i in ids]
    for receipt, items in groups:
        print(f"receipt {receipt.id}: {receipt.seller_name} (ИНН {receipt.seller_inn}) on {receipt.purchased_at}, {receipt.total_sum} RUB, {len(items)} positions")
    org = pick(odata_get(client, base, "Catalog_Организации", **{"$select": "Ref_Key,Description", "$top": "50"}), args.org, "organization")
    person = ensure_person(client, base, args.person, args.create_person)
    warehouses = odata_get(client, base, "Catalog_Склады", **{"$select": "Ref_Key,Description", "$top": "5"})
    warehouse = warehouses[0] if warehouses else None
    print(f"organization: {org['Description']} | person: {person['Description']} | section: {args.section}")

    if args.section == "Товары":
        class _DryCatalogs(Catalogs):  # a dry run must not create anything in 1C
            def item(self, name):
                return self.nomenclature.get(name.strip()[:100].lower()) or "<new nomenclature will be created>"

            def seller(self, receipt):
                inn = (receipt.seller_inn or "").strip()
                return self.counterparties.get(inn) or ("<new counterparty will be created>" if inn else None)

        catalogs = (Catalogs if args.create else _DryCatalogs)(client, base)
        body, section = build_goods_payload(types, groups, org, person, warehouse, catalogs, parse_kv(args.header), parse_kv(args.row))
        if args.create:
            print(f"nomenclature created: {catalogs.created_nomenclature} | counterparties created: {catalogs.created_counterparties}")
            for w in catalogs.warnings:
                print("warning:", w)
    else:
        receipt, items = groups[0]
        counterparty = None
        if receipt.seller_inn:
            all_cp = odata_get(client, base, "Catalog_Контрагенты", **{"$select": "Ref_Key,Description,ИНН", "$top": "1000"})
            found = [c for c in all_cp if (c.get("ИНН") or "").strip() == receipt.seller_inn.strip()]
            counterparty = found[0]["Ref_Key"] if found else None
        body, section = build_payload(types, receipt, items, org, person, counterparty, parse_kv(args.header), parse_kv(args.row), warehouse, args.per_position)
    print("\nPOST body sections:", {k: (f"{len(v)} rows" if isinstance(v, list) else v) for k, v in body.items() if k not in ("Организация_Key", "ФизЛицо_Key", "Склад_Key")})
    shown = dict(body)
    if len(shown.get(section, [])) > 3:
        shown[section] = shown[section][:2] + [f"... {len(body[section]) - 2} more rows ..."]
    print("\npayload:\n" + json.dumps(shown, ensure_ascii=False, indent=2))
    if not args.create:
        print("\ndry run: nothing sent")
        return 0

    r = client.post(f"{base}/{DOC}", params={"$format": "json"}, json=body)
    print(f"\nPOST {DOC} -> HTTP {r.status_code}")
    if r.status_code not in (200, 201):
        print(r.text[:1500])
        print("\nAdd the missing field with --header / --row (see --discover) and run again.")
        return 1
    doc = r.json()
    print("created:", {"Ref_Key": doc.get("Ref_Key"), "Number": doc.get("Number"), "Date": doc.get("Date"), "Posted": doc.get("Posted")})
    back = client.get(f"{base}/{DOC}(guid'{doc.get('Ref_Key')}')", params={"$format": "json"})
    print("read back:", back.status_code, "| rows in", section, ":", len(back.json().get(section, [])) if back.status_code == 200 else "?")
    print(f"\nTo remove it again: --delete {doc.get('Ref_Key')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

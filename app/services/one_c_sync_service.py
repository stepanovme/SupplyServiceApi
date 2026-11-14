import logging
import os
import uuid
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.reference_object import CounterpartyRef, DetailsIP, DetailsLLC, Person
from app.repositories.invoice_outgoing_repository import InvoiceOutgoingRepository
from app.repositories.one_c_repository import OneCRepository
from app.services.one_c_service import OneCService

logger = logging.getLogger(__name__)

CHECKO_API_KEY = os.getenv("CHECKO_API_KEY", "")
REF_API_BASE = os.getenv("REF_API_BASE", "https://supply.st29.ru/apiref")


class OneCSyncService:
    def __init__(
        self,
        one_c_repo: OneCRepository,
        outgoing_repo: InvoiceOutgoingRepository,
        reference_db: Session,
        session_token: str | None = None,
        ref_api_base: str | None = None,
    ) -> None:
        self.one_c_repo = one_c_repo
        self.outgoing_repo = outgoing_repo
        self.ref_db = reference_db
        self.session_token = session_token
        self.ref_api_base = ref_api_base or REF_API_BASE

    def sync(
        self,
        profile_ids: list[int] | None = None,
        organization_ref_keys: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        result = {
            "units_created": 0,
            "units_updated": 0,
            "nomenclatures_created": 0,
            "nomenclatures_updated": 0,
            "invoices_created": 0,
            "invoices_updated": 0,
            "counterparties_created": 0,
            "errors": [],
        }

        profiles = self.one_c_repo.get_profiles()
        if profile_ids:
            profiles = [p for p in profiles if p.id in profile_ids]

        logger.info(f"Sync started: {len(profiles)} profile(s) to process")

        for profile in profiles:
            profile_label = f"Profile {profile.id} ({profile.name})"
            profile_password = profile.password
            profile_api_link = profile.api_link

            decrypted_password = OneCService._decrypt_with_key(profile_password)
            base_url = profile_api_link.rstrip("/")
            odata_url = f"{base_url}/odata/standard.odata"

            try:
                logger.info(f"{profile_label}: starting sync")

                client = httpx.Client(
                    auth=(profile.username, decrypted_password),
                    timeout=httpx.Timeout(120.0),
                )

                unit_map = self._sync_units(client, odata_url)
                result["units_created"] += unit_map["created"]
                result["units_updated"] += unit_map["updated"]
                logger.info(f"{profile_label}: units done ({unit_map['created']} created, {unit_map['updated']} updated)")

                nomen_map = self._sync_nomenclatures(client, odata_url)
                result["nomenclatures_created"] += nomen_map["created"]
                result["nomenclatures_updated"] += nomen_map["updated"]
                logger.info(f"{profile_label}: nomenclatures done ({nomen_map['created']} created, {nomen_map['updated']} updated)")

                inv_result = self._sync_invoices(
                    client, odata_url, organization_ref_keys, date_from, date_to,
                )
                result["invoices_created"] += inv_result["created"]
                result["invoices_updated"] += inv_result["updated"]
                result["counterparties_created"] += inv_result["counterparties_created"]
                result["errors"].extend(inv_result["errors"])
                logger.info(f"{profile_label}: invoices done ({inv_result['created']} created, {inv_result['updated']} updated, {len(inv_result['errors'])} errors)")

                client.close()
            except Exception as e:
                self.outgoing_repo.db.rollback()
                logger.exception(f"{profile_label}: sync failed")
                result["errors"].append(f"{profile_label}: {str(e)}")

        return result

    def _sync_units(self, client: httpx.Client, odata_url: str) -> dict:
        created = 0
        updated = 0
        resp = client.get(
            f"{odata_url}/Catalog_КлассификаторЕдиницИзмерения",
            params={"$format": "json", "$select": "Ref_Key,Description"},
        )
        resp.raise_for_status()
        data = resp.json()
        existing = {u.ref_key: u for u in self.outgoing_repo.get_units()}

        for item in data.get("value", []):
            ref_key = item.get("Ref_Key")
            name = item.get("Description", "")
            if ref_key in existing:
                if existing[ref_key].name != name:
                    row = existing[ref_key]
                    row.name = name
                    self.outgoing_repo.save_unit(row)
                    updated += 1
            else:
                payload = {
                    "id": ref_key,
                    "ref_key": ref_key,
                    "name": name,
                }
                self.outgoing_repo.create_unit(payload)
                created += 1

        return {"created": created, "updated": updated}

    def _sync_nomenclatures(self, client: httpx.Client, odata_url: str) -> dict:
        created = 0
        updated = 0
        resp = client.get(
            f"{odata_url}/Catalog_Номенклатура",
            params={"$format": "json", "$select": "Ref_Key,Description,ЕдиницаИзмерения"},
        )
        resp.raise_for_status()
        data = resp.json()
        existing = {n.id: n for n in self.outgoing_repo.get_nomenclatures()}
        units = {u.ref_key: u for u in self.outgoing_repo.get_units()}

        for item in data.get("value", []):
            ref_key = item.get("Ref_Key")
            name = item.get("Description", "")
            unit_ref = item.get("ЕдиницаИзмерения")
            unit_id = None
            if isinstance(unit_ref, dict):
                unit_id = unit_ref.get("Ref_Key")
            elif isinstance(unit_ref, str):
                unit_id = unit_ref

            if unit_id and unit_id not in units:
                pass

            nomen_unit_id = units[unit_id].id if unit_id and unit_id in units else None

            if ref_key in existing:
                row = existing[ref_key]
                changed = False
                if row.name != name:
                    row.name = name
                    changed = True
                if nomen_unit_id and row.invoice_outgoing_unit_id != nomen_unit_id:
                    row.invoice_outgoing_unit_id = nomen_unit_id
                    changed = True
                if changed:
                    self.outgoing_repo.save_nomenclature(row)
                    updated += 1
            else:
                payload = {
                    "id": ref_key,
                    "ref_key": ref_key,
                    "name": name,
                    "invoice_outgoing_unit_id": nomen_unit_id,
                }
                self.outgoing_repo.create_nomenclature(payload)
                created += 1

        return {"created": created, "updated": updated}

    def _sync_invoices(
        self,
        client: httpx.Client,
        odata_url: str,
        organization_ref_keys: list[str] | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> dict:
        created = 0
        updated = 0
        counterparties_created = 0
        errors = []

        params: dict[str, str] = {
            "$format": "json",
            "$expand": "Организация,Контрагент",
            "$select": "Ref_Key,Number,Date,СуммаДокумента,Организация/Description,Организация/ИНН,Контрагент/Description,Контрагент/ИНН,Товары",
        }

        filters = []
        if organization_ref_keys:
            org_filter = " or ".join(
                f"Организация_Key eq guid'{k}'" for k in organization_ref_keys
            )
            filters.append(f"({org_filter})")
        if date_from:
            filters.append(f"Date ge datetime'{date_from.strftime('%Y-%m-%dT00:00:00')}'")
        if date_to:
            filters.append(f"Date le datetime'{date_to.strftime('%Y-%m-%dT23:59:59')}'")
        if filters:
            params["$filter"] = " and ".join(filters)

        logger.info(f"Fetching invoices from {odata_url}/Document_СчетНаОплатуПокупателю, filters: {filters}")
        try:
            resp = client.get(
                f"{odata_url}/Document_СчетНаОплатуПокупателю",
                params=params,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500 and "Организация" in str(params.get("$expand", "")):
                logger.warning(f"Got 500 with $expand, retrying without expand")
                params.pop("$expand", None)
                params["$select"] = "Ref_Key,Number,Date,СуммаДокумента,Товары"
                resp = client.get(
                    f"{odata_url}/Document_СчетНаОплатуПокупателю",
                    params=params,
                )
                resp.raise_for_status()
            else:
                raise
        data = resp.json()
        logger.info(f"Invoices response: {len(data.get('value', []))} documents")

        for doc in data.get("value", []):
            try:
                ref_key = doc.get("Ref_Key")
                if not ref_key:
                    continue

                existing = self.outgoing_repo.get_outgoing_by_ref_key(ref_key)

                org = doc.get("Организация")
                provider_inn = org.get("ИНН") if isinstance(org, dict) else None
                provider_name = org.get("Description") if isinstance(org, dict) else None
                contragent = doc.get("Контрагент")
                payer_inn = contragent.get("ИНН") if isinstance(contragent, dict) else None
                payer_name = contragent.get("Description") if isinstance(contragent, dict) else None

                if provider_inn:
                    provider_id = self._resolve_counterparty(provider_inn, provider_name)
                    if isinstance(provider_id, str):
                        counterparties_created += 1
                else:
                    provider_id = None

                if payer_inn:
                    payer_id = self._resolve_counterparty(payer_inn, payer_name)
                    if isinstance(payer_id, str):
                        counterparties_created += 1
                else:
                    payer_id = provider_id

                doc_date = None
                raw_date = doc.get("Date")
                if raw_date:
                    try:
                        doc_date = datetime.fromisoformat(raw_date.replace("Z", ""))
                    except (ValueError, AttributeError):
                        pass

                doc_sum = doc.get("СуммаДокумента")

                if existing:
                    row = existing
                    changed = False
                    if row.num != str(doc.get("Number", "")):
                        row.num = str(doc.get("Number", ""))
                        changed = True
                    if row.date != doc_date:
                        row.date = doc_date
                        changed = True
                    if row.sum != doc_sum:
                        row.sum = doc_sum
                        changed = True
                    if row.provider_id != provider_id:
                        row.provider_id = provider_id
                        changed = True
                    if row.payer_id != payer_id:
                        row.payer_id = payer_id
                        changed = True
                    if changed:
                        self.outgoing_repo.save_outgoing(row)
                        updated += 1
                    outgoing_id = row.id
                else:
                    payload = {
                        "Ref_Key": ref_key,
                        "num": str(doc.get("Number", "")),
                        "date": doc_date,
                        "sum": doc_sum,
                        "provider_id": provider_id,
                        "payer_id": payer_id,
                    }
                    row = self.outgoing_repo.create_outgoing(payload)
                    created += 1
                    outgoing_id = row.id

                self._sync_items(outgoing_id, doc.get("Товары", []))

            except Exception as e:
                if not self.outgoing_repo.db.is_active:
                    self.outgoing_repo.db.rollback()
                if not self.ref_db.is_active:
                    self.ref_db.rollback()
                errors.append(f"Document {doc.get('Ref_Key', 'unknown')}: {str(e)}")

        return {
            "created": created,
            "updated": updated,
            "counterparties_created": counterparties_created,
            "errors": errors,
        }

    def _sync_items(self, outgoing_id: int, товары: list):
        existing_items = {
            item.invoice_outgoing_nomenclature_id: item
            for item in self.outgoing_repo.get_outgoing_items_by_outgoing_id(outgoing_id)
        }
        processed_nomen_ids = set()

        for товар in товары:
            nomen_id = товар.get("Номенклатура")
            if not nomen_id:
                continue
            processed_nomen_ids.add(nomen_id)

            content = товар.get("Содержание", "") or ""

            if nomen_id in existing_items:
                item = existing_items[nomen_id]
                changed = False
                if item.name != content:
                    item.name = content
                    changed = True
                if item.quantity != товар.get("Количество"):
                    item.quantity = товар.get("Количество")
                    changed = True
                if item.price != товар.get("Цена"):
                    item.price = товар.get("Цена")
                    changed = True
                if item.sum != товар.get("Сумма"):
                    item.sum = товар.get("Сумма")
                    changed = True
                nds_val = товар.get("СтавкаНДС") or ""
                if item.nds != nds_val:
                    item.nds = nds_val
                    changed = True
                if item.nds_sum != товар.get("СуммаНДС"):
                    item.nds_sum = товар.get("СуммаНДС")
                    changed = True
                if changed:
                    self.outgoing_repo.save_outgoing_item(item)
            else:
                payload = {
                    "invoice_outgoing_nomenclature_id": nomen_id,
                    "name": content or None,
                    "quantity": товар.get("Количество"),
                    "price": товар.get("Цена"),
                    "sum": товар.get("Сумма"),
                    "nds": товар.get("СтавкаНДС") or "",
                    "nds_sum": товар.get("СуммаНДС"),
                }
                self.outgoing_repo.create_outgoing_item(outgoing_id, payload)

        for nomen_id, item in existing_items.items():
            if nomen_id not in processed_nomen_ids:
                self.outgoing_repo.delete_outgoing_item(item)

    def _resolve_counterparty(self, inn: str, name: str | None) -> str | None:
        existing = self._find_by_inn(inn)
        if existing:
            return existing

        return self._create_counterparty_from_checko(inn, name)

    def _find_by_inn(self, inn: str) -> str | None:
        llc = (
            self.ref_db.query(DetailsLLC)
            .filter(DetailsLLC.inn == inn)
            .first()
        )
        if llc:
            return llc.counterparties_id

        ip = (
            self.ref_db.query(DetailsIP)
            .filter(DetailsIP.inn == inn)
            .first()
        )
        if ip:
            return ip.counterparty_id

        return None

    def _create_counterparty_from_checko(self, inn: str, name: str | None) -> str | None:
        try:
            llc_resp = httpx.get(
                f"https://api.checko.ru/v2/company",
                params={"key": CHECKO_API_KEY, "inn": inn},
                timeout=30.0,
            )
            if llc_resp.status_code == 200 and llc_resp.json().get("data", {}).get("ОГРН"):
                return self._create_llc_from_checko(llc_resp.json()["data"], inn)

            ip_resp = httpx.get(
                f"https://api.checko.ru/v2/entrepreneur",
                params={"key": CHECKO_API_KEY, "inn": inn},
                timeout=30.0,
            )
            if ip_resp.status_code == 200 and ip_resp.json().get("data", {}).get("ОГРНИП"):
                return self._create_ip_from_checko(ip_resp.json()["data"], inn)

        except Exception:
            pass

        if name:
            return self._create_minimal_counterparty(inn, name)

        return None

    def _create_minimal_counterparty(self, inn: str, name: str) -> str:
        cp_id = str(uuid.uuid4())
        short_name = name if len(name) <= 300 else name[:300]
        ref = CounterpartyRef(
            id=cp_id,
            short_name=short_name,
            full_name=name,
            type="LLC",
            is_internal=False,
        )
        self.ref_db.add(ref)
        self.ref_db.flush()

        llc = DetailsLLC(
            counterparties_id=cp_id,
            inn=inn,
            kpp="",
            ogrn="",
            legal_address="",
        )
        self.ref_db.add(llc)
        self.ref_db.commit()
        return cp_id

    def _create_llc_from_checko(self, data: dict, inn: str) -> str:
        cp_id = str(uuid.uuid4())
        short_name = (data.get("НаимСокр") or data.get("НаимПолн") or "")[:300]
        full_name = (data.get("НаимПолн") or "")[:500]

        ref = CounterpartyRef(
            id=cp_id,
            short_name=short_name or None,
            full_name=full_name or None,
            type="LLC",
            is_internal=False,
        )
        self.ref_db.add(ref)
        self.ref_db.flush()

        person_id = None
        directors = data.get("Руковод", []) or []
        if directors:
            director = directors[0]
            fio = director.get("ФИО", "").strip()
            if fio:
                parts = fio.split(" ", 2)
                person = Person(
                    id=str(uuid.uuid4()),
                    last_naem=parts[0] if len(parts) > 0 else "",
                    name=parts[1] if len(parts) > 1 else "",
                    middle_name=parts[2] if len(parts) > 2 else "",
                )
                self.ref_db.add(person)
                self.ref_db.flush()
                person_id = person.id

        legal_address = data.get("ЮрАдрес", {}).get("АдресРФ") if isinstance(data.get("ЮрАдрес"), dict) else ""
        ogrn = data.get("ОГРН") or ""
        kpp = data.get("КПП") or ""

        llc = DetailsLLC(
            counterparties_id=cp_id,
            inn=inn,
            kpp=kpp,
            ogrn=ogrn,
            legal_address=legal_address,
            director_person_id=person_id,
        )
        self.ref_db.add(llc)
        self.ref_db.commit()
        return cp_id

    def _create_ip_from_checko(self, data: dict, inn: str) -> str:
        cp_id = str(uuid.uuid4())
        fio = (data.get("ФИО") or "").strip()
        short_name = f"ИП {fio}"[:300]
        full_name = f"{data.get('Тип', '')} {fio}"[:500]

        ref = CounterpartyRef(
            id=cp_id,
            short_name=short_name,
            full_name=full_name,
            type="IP",
            is_internal=False,
        )
        self.ref_db.add(ref)
        self.ref_db.flush()

        parts = fio.split(" ", 2)
        person = Person(
            id=str(uuid.uuid4()),
            last_naem=parts[0] if len(parts) > 0 else "",
            name=parts[1] if len(parts) > 1 else "",
            middle_name=parts[2] if len(parts) > 2 else "",
        )
        self.ref_db.add(person)
        self.ref_db.flush()

        ip = DetailsIP(
            counterparty_id=cp_id,
            inn=inn,
            ogrnip=data.get("ОГРНИП"),
            person_id=person.id,
        )
        self.ref_db.add(ip)
        self.ref_db.commit()
        return cp_id

    @staticmethod
    def _get_nested(obj: dict, *keys):
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

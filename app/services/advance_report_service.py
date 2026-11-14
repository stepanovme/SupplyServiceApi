import logging
import threading
import uuid
from decimal import Decimal

from fastapi import HTTPException, status

from app.models.advance_report import (
    AdvanceReport,
    AdvanceReportCreate,
    AdvanceReportReceipt,
    AdvanceReportReceiptsAdd,
    AdvanceReportUpdate,
    OneCSendOptions,
    msk_now,
)
from app.repositories.advance_report_repository import AdvanceReportRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.purchase_receipt_repository import PurchaseReceiptRepository
from app.services.one_c_advance_client import OneCAdvanceClient, OneCAdvanceError
from app.services.receipt_category_service import ADMIN_ROLE_ID

logger = logging.getLogger(__name__)

_sending_lock = threading.Lock()
_sending: set[str] = set()  # reports being sent right now: a double click must not create two documents in 1C


class AdvanceReportService:
    def __init__(
        self,
        repo: AdvanceReportRepository,
        receipt_repo: PurchaseReceiptRepository,
        auth_user_repo: AuthUserRepository,
    ) -> None:
        self.repo = repo
        self.receipt_repo = receipt_repo
        self.auth_user_repo = auth_user_repo

    # ---- helpers -------------------------------------------------------------------------
    def _is_admin(self, user_id: str) -> bool:
        return self.auth_user_repo.has_role(user_id, ADMIN_ROLE_ID)

    def _require_admin(self, user_id: str) -> None:
        if not self._is_admin(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Отправлять авансовые отчёты в 1С может только администратор"
            )

    def _get_report(self, report_id: str, user_id: str) -> AdvanceReport:
        report = self.repo.get_by_id(report_id)
        if not report or report.created_by != user_id:  # somebody else's report looks like a missing one
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Авансовый отчёт не найден")
        return report

    @staticmethod
    def _require_draft(report: AdvanceReport) -> None:
        if report.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Отчёт уже отправлен в 1С — состав и реквизиты больше не меняются",
            )

    def _check_users(self, user_ids: list[str | None]) -> None:
        ids = [u for u in dict.fromkeys(user_ids) if u]
        if ids:
            found = {u.id for u in self.auth_user_repo.get_by_ids(ids)}
            missing = [u for u in ids if u not in found]
            if missing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пользователи не найдены: {', '.join(missing)}")

    def _validate_receipts(self, receipt_ids: list[str], user_id: str, this_report_id: str | None = None) -> list:
        """Receipts the user may put into a report: visible to them, purchases (not returns), and not in another report."""
        ids = list(dict.fromkeys(receipt_ids))
        receipts = {r.id: r for r in self.repo.get_receipts(ids)}
        shared = self.receipt_repo.get_access_for_user(list(receipts), user_id)
        taken = self.repo.get_links_by_receipts(ids)
        problems = []
        for rid in ids:
            receipt = receipts.get(rid)
            if receipt is None or (receipt.created_by != user_id and rid not in shared):
                problems.append({"receipt_id": rid, "problem": "not_found"})
            elif receipt.receipt_type != 1:
                problems.append({"receipt_id": rid, "problem": "not_a_purchase"})
            elif rid in taken and taken[rid][0] != this_report_id:
                problems.append({"receipt_id": rid, "problem": "already_in_report", "report_number": taken[rid][2]})
        if problems:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Часть чеков нельзя включить в авансовый отчёт (not_found — нет или недоступен, "
                    "not_a_purchase — это возврат, already_in_report — уже в другом отчёте)",
                    "problems": problems,
                },
            )
        return [receipts[i] for i in ids]

    def _recalculate(self, report: AdvanceReport) -> None:
        links = self.repo.get_links([report.id])
        receipts = self.repo.get_receipts([l.receipt_id for l in links])
        report.total_sum = sum((Decimal(r.total_sum) for r in receipts), Decimal("0"))
        report.updated_at = msk_now()

    # ---- serialization -------------------------------------------------------------------
    @staticmethod
    def _short_fio(user) -> dict | None:
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        fio = " ".join(p for p in [user.surname, name_initial, patronymic_initial] if p).strip()
        return {"id": user.id, "short_fio": fio or None}

    def _serialize_many(self, reports: list[AdvanceReport], with_receipts: bool) -> list[dict]:
        links = self.repo.get_links([r.id for r in reports])
        by_report: dict[str, list] = {}
        for l in links:
            by_report.setdefault(l.report_id, []).append(l)

        receipts = {r.id: r for r in self.repo.get_receipts([l.receipt_id for l in links])} if with_receipts else {}
        counts: dict[str, int] = {}
        if with_receipts:
            for item in self.repo.get_items(list(receipts)):
                counts[item.receipt_id] = counts.get(item.receipt_id, 0) + 1

        users = {
            u.id: u
            for u in self.auth_user_repo.get_by_ids(
                list({r.created_by for r in reports} | {r.person_user_id for r in reports if r.person_user_id} | {r.one_c_sent_by for r in reports if r.one_c_sent_by})
            )
        }
        profiles = {p.id: p for p in self.repo.get_profiles()}

        result = []
        for r in reports:
            profile = profiles.get(r.one_c_profile_id) if r.one_c_profile_id else None
            data = {
                "id": r.id,
                "number": r.number,
                "title": r.title,
                "report_date": r.report_date,
                "comment": r.comment,
                "status": r.status,
                "total_sum": float(r.total_sum),
                "receipts_count": len(by_report.get(r.id, [])),
                "person_user_id": r.person_user_id,
                "person_user": self._short_fio(users.get(r.person_user_id)) if r.person_user_id else None,
                "created_by": self._short_fio(users.get(r.created_by)) or {"id": r.created_by, "short_fio": None},
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "one_c": {
                    "profile_id": r.one_c_profile_id,
                    "profile_name": profile.name if profile else None,
                    "organization": {"ref_key": r.one_c_organization_ref_key, "name": r.one_c_organization_name} if r.one_c_organization_ref_key else None,
                    "person": {"ref_key": r.one_c_person_ref_key, "name": r.one_c_person_name} if r.one_c_person_ref_key else None,
                    "document": {"ref_key": r.one_c_ref_key, "number": r.one_c_number} if r.one_c_ref_key else None,
                    "sent_at": r.one_c_sent_at,
                    "sent_by": self._short_fio(users.get(r.one_c_sent_by)) if r.one_c_sent_by else None,
                    "error": r.one_c_error,
                },
            }
            if with_receipts:
                data["receipts"] = [
                    {
                        "id": rc.id,
                        "purchased_at": rc.purchased_at,
                        "seller_name": rc.seller_name,
                        "seller_inn": rc.seller_inn,
                        "total_sum": float(rc.total_sum),
                        "payment_method": rc.payment_method,
                        "items_count": counts.get(rc.id, 0),
                    }
                    for rc in (receipts.get(l.receipt_id) for l in by_report.get(r.id, []))
                    if rc is not None
                ]
            result.append(data)
        return result

    # ---- reports -------------------------------------------------------------------------
    def create(self, payload: AdvanceReportCreate, user_id: str) -> dict:
        self._check_users([payload.person_user_id])
        receipts = self._validate_receipts(payload.receipt_ids, user_id)
        report = AdvanceReport(
            id=str(uuid.uuid4()),
            title=(payload.title or "").strip() or None,
            report_date=payload.report_date or msk_now().date(),
            comment=payload.comment,
            person_user_id=payload.person_user_id,
            created_by=user_id,
            total_sum=sum((Decimal(r.total_sum) for r in receipts), Decimal("0")),
        )
        if payload.one_c:
            self._require_admin(user_id)  # fail before anything is saved
            if not self.repo.get_profile(payload.one_c.profile_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль 1С не найден")
        try:
            self.repo.add(report)
            self.repo.flush()  # the report row must exist before the receipts reference it
            for receipt in receipts:
                self.repo.add(AdvanceReportReceipt(report_id=report.id, receipt_id=receipt.id, added_by=user_id))
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.refresh(report)

        send_result = self._try_send(report, payload.one_c, user_id) if payload.one_c else None
        out = self._serialize_many([report], True)[0]
        if send_result is not None:
            out["one_c_send"] = send_result
        return out

    def get_list(self, user_id: str, status_filter: str | None, limit: int, offset: int) -> list[dict]:
        return self._serialize_many(self.repo.get_list(user_id, status_filter, limit, offset), with_receipts=False)

    def get_by_id(self, report_id: str, user_id: str) -> dict:
        return self._serialize_many([self._get_report(report_id, user_id)], True)[0]

    def update(self, report_id: str, payload: AdvanceReportUpdate, user_id: str) -> dict:
        report = self._get_report(report_id, user_id)
        self._require_draft(report)
        data = payload.model_dump(exclude_unset=True)
        if "person_user_id" in data:
            self._check_users([data["person_user_id"]])
            report.person_user_id = data["person_user_id"]
        if "title" in data:
            report.title = (data["title"] or "").strip() or None
        if data.get("report_date"):
            report.report_date = data["report_date"]
        if "comment" in data:
            report.comment = data["comment"]
        report.updated_at = msk_now()
        self.repo.commit()
        self.repo.refresh(report)
        return self._serialize_many([report], True)[0]

    def add_receipts(self, report_id: str, payload: AdvanceReportReceiptsAdd, user_id: str) -> dict:
        report = self._get_report(report_id, user_id)
        self._require_draft(report)
        receipts = self._validate_receipts(payload.receipt_ids, user_id, this_report_id=report.id)
        existing = {l.receipt_id for l in self.repo.get_links([report.id])}
        try:
            for receipt in receipts:
                if receipt.id not in existing:
                    self.repo.add(AdvanceReportReceipt(report_id=report.id, receipt_id=receipt.id, added_by=user_id))
            self.repo.flush()
            self._recalculate(report)
            report.one_c_error = None
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        self.repo.refresh(report)
        return self._serialize_many([report], True)[0]

    def remove_receipt(self, report_id: str, receipt_id: str, user_id: str) -> dict:
        report = self._get_report(report_id, user_id)
        self._require_draft(report)
        link = next((l for l in self.repo.get_links([report.id]) if l.receipt_id == receipt_id), None)
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Этого чека нет в отчёте")
        self.repo.delete(link)
        self.repo.flush()
        self._recalculate(report)
        self.repo.commit()
        self.repo.refresh(report)
        return self._serialize_many([report], True)[0]

    def delete(self, report_id: str, user_id: str) -> None:
        report = self._get_report(report_id, user_id)
        self._require_draft(report)  # a report that exists in 1C is not deleted from here
        self.repo.delete(report)  # the links go with it; the receipts themselves are untouched
        self.repo.commit()

    # ---- 1C ------------------------------------------------------------------------------
    def get_profiles(self, user_id: str) -> list[dict]:
        self._require_admin(user_id)
        return [{"id": p.id, "name": p.name, "is_test": bool(p.is_test)} for p in self.repo.get_profiles()]

    def get_options(self, profile_id: int, user_id: str, search: str | None) -> dict:
        """Organizations and accountable persons of the chosen 1C base - what the UI offers for selection."""
        self._require_admin(user_id)
        profile = self.repo.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль 1С не найден")
        client = OneCAdvanceClient(profile)
        try:
            return {
                "profile": {"id": profile.id, "name": profile.name, "is_test": bool(profile.is_test)},
                "organizations": client.organizations(),
                "persons": client.persons(search),
            }
        except OneCAdvanceError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.message)
        finally:
            client.close()

    def _try_send(self, report: AdvanceReport, options: OneCSendOptions, user_id: str) -> dict:
        """Used by create(): the report is already saved, so a 1C problem is reported, not raised."""
        try:
            return {"status": "sent", "error": None, **self._send(report, options, user_id)}
        except HTTPException as exc:
            return {"status": "failed", "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail)}

    def send_to_1c(self, report_id: str, options: OneCSendOptions, user_id: str) -> dict:
        self._require_admin(user_id)
        report = self._get_report(report_id, user_id)
        send_result = self._send(report, options, user_id)
        return {**self._serialize_many([report], True)[0], "one_c_send": {"status": "sent", "error": None, **send_result}}

    def _send(self, report: AdvanceReport, options: OneCSendOptions, user_id: str) -> dict:
        self._require_draft(report)
        links = self.repo.get_links([report.id])
        if not links:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="В отчёте нет чеков")
        profile = self.repo.get_profile(options.profile_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль 1С не найден")

        with _sending_lock:
            if report.id in _sending:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот отчёт уже отправляется в 1С")
            _sending.add(report.id)
        client = None
        try:
            receipts = {r.id: r for r in self.repo.get_receipts([l.receipt_id for l in links])}
            items: dict[str, list] = {}
            for item in self.repo.get_items(list(receipts)):
                items.setdefault(item.receipt_id, []).append(item)
            groups = [(receipts[l.receipt_id], items.get(l.receipt_id, [])) for l in links if l.receipt_id in receipts]

            client = OneCAdvanceClient(profile)
            result = client.send(report, groups, options)
        except OneCAdvanceError as exc:
            report.one_c_profile_id = options.profile_id
            report.one_c_error = exc.message
            report.updated_at = msk_now()
            self.repo.commit()
            raise HTTPException(status_code=exc.status, detail=exc.message)
        finally:
            if client:
                client.close()
            with _sending_lock:
                _sending.discard(report.id)

        report.status = "sent"
        report.one_c_profile_id = options.profile_id
        report.one_c_organization_ref_key = result["organization"]["ref_key"]
        report.one_c_organization_name = result["organization"]["name"]
        report.one_c_person_ref_key = result["person"]["ref_key"]
        report.one_c_person_name = result["person"]["name"]
        report.one_c_ref_key = result["ref_key"]
        report.one_c_number = result["number"]
        report.one_c_sent_at = msk_now()
        report.one_c_sent_by = user_id
        report.one_c_error = None
        report.updated_at = msk_now()
        self.repo.commit()
        self.repo.refresh(report)
        logger.info(
            "advance report %s sent to 1C profile %s as %s (%d lines, created %s, warnings %s)",
            report.id, options.profile_id, result["number"], result["lines"], result["created"], result["warnings"],
        )
        return {"lines": result["lines"], "mode": result["mode"], "created": result["created"], "warnings": result["warnings"]}

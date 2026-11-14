import threading
from contextvars import copy_context
import uuid
from datetime import date

from fastapi import HTTPException, status

from app.database import ReferenceSessionLocal, SupplySessionLocal
from app.models.extract_item import FetchSberbankStatementRequest
from app.models.extract_statement_job import ExtractStatementJob, msk_now
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.extract_statement_job_repository import ExtractStatementJobRepository
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.extract_item_service import ExtractItemService


class ExtractStatementJobService:
    def __init__(self, repo: ExtractStatementJobRepository, bank_settings_repo: SettingsApiBankRepository) -> None:
        self.repo = repo
        self.bank_settings_repo = bank_settings_repo

    @staticmethod
    def _serialize(row: ExtractStatementJob) -> dict:
        return {
            "id": row.id,
            "settings_api_bank_id": row.settings_api_bank_id,
            "account_number": row.account_number,
            "statement_date_from": row.statement_date_from,
            "statement_date_to": row.statement_date_to,
            "status": row.status,
            "days_requested": row.days_requested,
            "days_processed": row.days_processed,
            "days_succeeded": row.days_succeeded,
            "days_failed": row.days_failed,
            "current_date_processing": row.current_date_processing,
            "fetched": row.fetched,
            "created_count": row.created_count,
            "skipped_duplicates": row.skipped_duplicates,
            "errors": row.errors or [],
            "error_message": row.error_message,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "created_by": row.created_by,
        }

    def create_job(self, payload: FetchSberbankStatementRequest, user_id: str) -> dict:
        bank_setting = self.bank_settings_repo.get_by_id(payload.settings_api_bank_id)
        if not bank_setting:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        if bank_setting.bank_type != "sberbank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Эта интеграция не относится к bank_type=sberbank",
            )
        if not bank_setting.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Интеграция отключена (is_active=false)")

        dates = payload.iter_dates()

        row = ExtractStatementJob(
            id=str(uuid.uuid4()),
            settings_api_bank_id=payload.settings_api_bank_id,
            account_number=payload.account_number,
            statement_date_from=date.fromisoformat(dates[0]),
            statement_date_to=date.fromisoformat(dates[-1]),
            status="pending",
            days_requested=len(dates),
            errors=[],
            created_by=user_id,
        )
        created = self.repo.create(row)

        thread = threading.Thread(
            target=copy_context().run,
            args=(_run_job_in_background, created.id, dates, payload.account_number, payload.settings_api_bank_id),
            daemon=True,
        )
        thread.start()

        return self._serialize(created)

    def get_job(self, job_id: str) -> dict:
        row = self.repo.get_by_id(job_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return self._serialize(row)

    def get_jobs(self, settings_api_bank_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.repo.get_list(settings_api_bank_id, limit, offset)
        return [self._serialize(row) for row in rows]


def _run_job_in_background(job_id: str, dates: list[str], account_number: str, settings_api_bank_id: str) -> None:
    """Runs on its own thread with its own DB sessions - fully independent of the
    HTTP request/response cycle that created it. Closing the browser tab, an nginx
    timeout, or any other client disconnect has no effect on this loop; it only
    stops early if the whole Python process dies.
    """
    supply_db = SupplySessionLocal()
    reference_db = ReferenceSessionLocal()
    job_repo = ExtractStatementJobRepository(supply_db)
    try:
        job = job_repo.get_by_id(job_id)
        if not job:
            return

        bank_settings_repo = SettingsApiBankRepository(supply_db)
        bank_setting = bank_settings_repo.get_by_id(settings_api_bank_id)
        if not bank_setting:
            job.status = "failed"
            job.error_message = "Bank API setting not found"
            job.finished_at = msk_now()
            job_repo.save(job)
            return

        config = bank_setting.config or {}
        api_host = config.get("api_host")
        api_token = config.get("api_token")
        pfx_path = config.get("pfx_path")
        pfx_passphrase = config.get("pfx_passphrase")
        ca_bundle_path = config.get("ca_bundle_path")
        ssl_verify = config.get("ssl_verify", True)

        if not api_host or not api_token:
            job.status = "failed"
            job.error_message = "У интеграции не заполнены api_host/api_token"
            job.finished_at = msk_now()
            job_repo.save(job)
            return

        job.status = "running"
        job.started_at = msk_now()
        job_repo.save(job)

        item_service = ExtractItemService(
            ExtractItemRepository(supply_db),
            bank_settings_repo,
            CounterpartyRepository(reference_db),
        )

        errors: list[dict] = []

        for statement_date in dates:
            job.current_date_processing = date.fromisoformat(statement_date)
            job_repo.save(job)

            try:
                day_result = item_service._fetch_and_store_one_day(
                    account_number=account_number,
                    statement_date=statement_date,
                    api_host=api_host,
                    api_token=api_token,
                    pfx_path=pfx_path,
                    pfx_passphrase=pfx_passphrase,
                    ca_bundle_path=ca_bundle_path,
                    ssl_verify=ssl_verify,
                )
                job.days_succeeded += 1
                job.fetched += day_result["fetched"]
                job.created_count += day_result["created"]
                job.skipped_duplicates += day_result["skipped_duplicates"]
            except Exception as exc:
                job.days_failed += 1
                detail = getattr(exc, "detail", None) or str(exc)
                errors.append({"statement_date": statement_date, "detail": detail})
                job.errors = errors

            job.days_processed += 1
            job_repo.save(job)

        job.status = "completed"
        job.current_date_processing = None
        job.finished_at = msk_now()
        job_repo.save(job)
    except Exception as exc:
        try:
            job = job_repo.get_by_id(job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = msk_now()
                job_repo.save(job)
        except Exception:
            pass
    finally:
        supply_db.close()
        reference_db.close()

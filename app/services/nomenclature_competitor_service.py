import hashlib
import os
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.supply_request import NomenclatureCompetitorCreate, NomenclatureCompetitorFile, NomenclatureCompetitorUpdate
from app.repositories.nomenclature_competitor_repository import NomenclatureCompetitorRepository

BASE_COMPETITOR_FILES_DIR = os.getenv(
    "SUPPLY_NOMENCLATURE_COMPETITOR_FILES_DIR",
    "/home/webserver/models/supply/nomenclature-competitor",
)
COMPETITOR_ATTACHMENT_FILE_TYPE_CODE = "request_attachment"


class NomenclatureCompetitorService:
    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def __init__(self, repo: NomenclatureCompetitorRepository) -> None:
        self.repo = repo

    def create(self, payload: NomenclatureCompetitorCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, competitor_id: str) -> dict | None:
        row = self.repo.get_by_id(competitor_id)
        if not row:
            return None
        result = self._serialize(row)
        result["files"] = self._serialize_files(self.repo.get_competitor_files(competitor_id))
        return result

    def get_by_nomenclature(self, nomenclature_id: str) -> list[dict]:
        rows = self.repo.get_by_nomenclature(nomenclature_id)
        if not rows:
            return []
        competitor_ids = [r.id for r in rows]
        files = self.repo.get_files_by_competitor_ids(competitor_ids)
        files_by_competitor: dict[str, list[dict]] = {}
        for f in files:
            cid = f.nomenclature_competitor_id
            if cid not in files_by_competitor:
                files_by_competitor[cid] = []
            files_by_competitor[cid].append(self._serialize_file(f))
        return [{**self._serialize(r), "files": files_by_competitor.get(r.id, [])} for r in rows]

    def update(self, competitor_id: str, payload: NomenclatureCompetitorUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(competitor_id, data)
        return self._serialize(row) if row else None

    def delete(self, competitor_id: str) -> bool:
        return self.repo.delete(competitor_id)

    def get_files(self, competitor_id: str) -> list[dict]:
        if not self.repo.get_by_id(competitor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
        rows = self.repo.get_competitor_files(competitor_id)
        return [
            {
                "id": row.id,
                "nomenclature_competitor_id": row.nomenclature_competitor_id,
                "original_name": row.original_name,
                "extension": row.extension,
                "uploaded_by": row.uploaded_by,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "download_url": f"/api/supply/nomenclature-competitors/{competitor_id}/files/{row.id}/download",
            }
            for row in rows
        ]

    def upload_file(self, competitor_id: str, original_name: str, mime_type: str, file_bytes: bytes, user_id: str) -> dict:
        if not self.repo.get_by_id(competitor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is required")

        storage_name = f"{uuid.uuid4().hex}.{extension}"
        competitor_dir = os.path.join(BASE_COMPETITOR_FILES_DIR, competitor_id)
        self._ensure_directory(competitor_dir)
        file_path = os.path.join(competitor_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        try:
            row = self.repo.create_file(
                {
                    "id": str(uuid.uuid4()),
                    "nomenclature_competitor_id": competitor_id,
                    "original_name": original_name,
                    "storage_name": storage_name,
                    "extension": extension,
                    "file_path": file_path,
                    "uploaded_by": user_id,
                }
            )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        return {
            "id": row.id,
            "nomenclature_competitor_id": competitor_id,
            "original_name": row.original_name,
            "extension": row.extension,
            "file_path": row.file_path,
        }

    def get_download_file_payload(self, competitor_id: str, file_id: str) -> dict:
        if not self.repo.get_by_id(competitor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
        row = self.repo.get_competitor_file(competitor_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        media_type = self._get_mime_type(row.extension)
        return {
            "path": row.file_path,
            "filename": row.original_name or f"file.{row.extension}",
            "media_type": media_type,
        }

    def get_preview(self, file_id: str) -> str:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        ext = Path(row.file_path).suffix.lower()
        if ext == ".pdf":
            return row.file_path

        if ext not in self.PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")

        cached = Path(row.file_path).parent / f"{Path(row.file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), row.file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(row.file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversion produced no output")

        return str(cached)

    def delete_file(self, competitor_id: str, file_id: str) -> None:
        if not self.repo.get_by_id(competitor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
        row = self.repo.get_competitor_file(competitor_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "nomenclature_id": row.nomenclature_id,
            "name": row.name,
            "price": row.price,
            "source_name": row.source_name,
            "source_site": row.source_site,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }

    def _serialize_file(self, row) -> dict:
        return {
            "id": row.id,
            "original_name": row.original_name,
            "extension": row.extension,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
            "download_url": f"/api/supply/nomenclature-competitors/{row.nomenclature_competitor_id}/files/{row.id}/download",
        }

    def _serialize_files(self, rows: list) -> list[dict]:
        return [self._serialize_file(r) for r in rows]

    @staticmethod
    def _get_mime_type(extension: str | None) -> str:
        if not extension:
            return "application/octet-stream"
        mime_map = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "txt": "text/plain",
            "csv": "text/csv",
        }
        return mime_map.get(extension.lower(), "application/octet-stream")

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Cannot create directory '{path}'. Set SUPPLY_NOMENCLATURE_COMPETITOR_FILES_DIR to a writable path.",
            ) from exc

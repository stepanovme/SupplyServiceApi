import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB, NomenclatureFile, RequestFile
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.request_repository import RequestRepository
from app.services.ws_manager import ws_manager

BASE_REQUEST_FILES_DIR = os.getenv(
    "SUPPLY_REQUEST_FILES_DIR",
    os.path.join(os.getcwd(), "storage", "request"),
)
INVOICE_FILE_TYPE_ID = "4594a94b-140f-11f1-aa8c-bc241127d0bd"
BASE_NOMENCLATURE_FILES_DIR = os.getenv(
    "SUPPLY_NOMENCLATURE_FILES_DIR",
    "/home/webserver/models/supply/nomenclature",
)


class RequestFileService:
    def __init__(
        self,
        repo: RequestFileRepository,
        request_repo: RequestRepository | None = None,
        project_user_role_repo: ProjectUserRoleRepository | None = None,
    ) -> None:
        self.repo = repo
        self.request_repo = request_repo
        self.project_user_role_repo = project_user_role_repo

    def upload_request_attachment(
        self,
        request_id: int,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        user_id: str,
    ):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        attachment_type = self.repo.get_request_attachment_type()
        if not attachment_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active file type 'request_attachment' not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = attachment_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = attachment_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        request_dir = os.path.join(BASE_REQUEST_FILES_DIR, str(request_id))
        self._ensure_directory(request_dir)
        file_path = os.path.join(request_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        md5_hash = hashlib.md5(file_bytes).hexdigest()

        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=attachment_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=md5_hash,
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )
        request_file_row = RequestFile(
            id=str(uuid.uuid4()),
            request_id=request_id,
            file_id=file_id,
            link_type="attachment",
            created_by=user_id,
            is_main=False,
            sort_order=0,
        )

        try:
            created = self.repo.create_file_and_link(file_row, request_file_row)
            self.repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=file_id,
                    action="upload",
                    user_id=user_id,
                )
            )
            if self.request_repo:
                self.request_repo.create_event_log(
                    request_id=request_id,
                    user_id=user_id,
                    event_type="file_attached",
                    description=f"Прикреплён файл: {original_name}",
                )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        return {
            "id": created.id,
            "request_id": request_id,
            "original_name": created.original_name,
            "mime_type": created.mime_type,
            "extension": created.extension,
            "file_size": created.file_size,
            "file_path": created.file_path,
        }

    def upload_nomenclature_photo(
        self,
        nomenclature_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        user_id: str,
    ):
        if not self.repo.nomenclature_exists(nomenclature_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        attachment_type = self.repo.get_request_attachment_type()
        if not attachment_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active file type 'request_attachment' not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = attachment_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = attachment_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        nomenclature_dir = os.path.join(BASE_NOMENCLATURE_FILES_DIR, nomenclature_id)
        self._ensure_directory(nomenclature_dir)
        file_path = os.path.join(nomenclature_dir, storage_name)

        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        md5_hash = hashlib.md5(file_bytes).hexdigest()

        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=attachment_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=md5_hash,
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )
        nomenclature_file_row = NomenclatureFile(
            id=str(uuid.uuid4()),
            nomenclature_id=nomenclature_id,
            file_id=file_id,
        )

        try:
            created = self.repo.create_file_and_nomenclature_link(file_row, nomenclature_file_row)
            self.repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=file_id,
                    action="upload",
                    user_id=user_id,
                )
            )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        return {
            "id": created.id,
            "nomenclature_id": nomenclature_id,
            "original_name": created.original_name,
            "mime_type": created.mime_type,
            "extension": created.extension,
            "file_size": created.file_size,
            "file_path": created.file_path,
        }

    def get_nomenclature_photos(self, nomenclature_id: str):
        if not self.repo.nomenclature_exists(nomenclature_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        rows = self.repo.get_nomenclature_files(nomenclature_id)
        return [
            {
                "id": file_row.id,
                "nomenclature_file_id": nomenclature_file.id,
                "nomenclature_id": nomenclature_file.nomenclature_id,
                "created_at": nomenclature_file.created_at,
                "original_name": file_row.original_name,
                "mime_type": file_row.mime_type,
                "extension": file_row.extension,
                "file_size": file_row.file_size,
                "uploaded_by": file_row.uploaded_by,
                "uploaded_at": file_row.uploaded_at,
                "file_type": {
                    "id": file_type.id,
                    "code": file_type.code,
                    "name": file_type.name,
                },
                "download_url": f"/api/supply/nomenclature/{nomenclature_id}/photos/{file_row.id}/download",
            }
            for nomenclature_file, file_row, file_type in rows
        ]

    def get_nomenclature_download_file_payload(self, nomenclature_id: str, file_id: str, user_id: str):
        if not self.repo.nomenclature_exists(nomenclature_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        row = self.repo.get_nomenclature_file(nomenclature_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        if not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="download",
                user_id=user_id,
            )
        )

        return {
            "path": file_row.file_path,
            "filename": file_row.original_name,
            "media_type": file_row.mime_type,
        }

    def delete_nomenclature_photo(self, nomenclature_id: str, file_id: str, user_id: str):
        if not self.repo.nomenclature_exists(nomenclature_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        row = self.repo.get_nomenclature_file(nomenclature_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        self.repo.mark_file_deleted(file_row)
        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="delete",
                user_id=user_id,
            )
        )

        if os.path.exists(file_row.file_path):
            os.remove(file_row.file_path)

        return None

    def get_request_files(self, request_id: int):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        rows = self.repo.get_request_files(request_id)
        return [
            {
                "id": file_row.id,
                "request_file_id": request_file.id,
                "request_id": request_file.request_id,
                "link_type": request_file.link_type,
                "description": request_file.description,
                "is_main": request_file.is_main,
                "sort_order": request_file.sort_order,
                "original_name": file_row.original_name,
                "mime_type": file_row.mime_type,
                "extension": file_row.extension,
                "file_size": file_row.file_size,
                "uploaded_by": file_row.uploaded_by,
                "uploaded_at": file_row.uploaded_at,
                "file_type": {
                    "id": file_type.id,
                    "code": file_type.code,
                    "name": file_type.name,
                },
                "download_url": f"/api/supply/requests/{request_id}/attachments/{file_row.id}/download",
            }
            for request_file, file_row, file_type in rows
        ]

    def upload_request_invoice_file(
        self,
        request_id: int,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        user_id: str,
    ):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        invoice_type = self.repo.get_file_type_by_id(INVOICE_FILE_TYPE_ID)
        if not invoice_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active file type for invoice not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = invoice_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = invoice_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        request_dir = os.path.join(BASE_REQUEST_FILES_DIR, str(request_id))
        self._ensure_directory(request_dir)
        file_path = os.path.join(request_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        md5_hash = hashlib.md5(file_bytes).hexdigest()

        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=invoice_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=md5_hash,
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )
        request_file_row = RequestFile(
            id=str(uuid.uuid4()),
            request_id=request_id,
            file_id=file_id,
            link_type="invoice",
            created_by=user_id,
            is_main=False,
            sort_order=0,
        )

        try:
            created = self.repo.create_file_and_link(file_row, request_file_row)
            self.repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=file_id,
                    action="upload",
                    user_id=user_id,
                )
            )
            if self.request_repo:
                self.request_repo.create_event_log(
                    request_id=request_id,
                    user_id=user_id,
                    event_type="file_attached",
                    description=f"Прикреплён файл счёта: {original_name}",
                )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        self._notify_invoice_attached(request_id, user_id, created.original_name)

        return {
            "id": created.id,
            "request_id": request_id,
            "original_name": created.original_name,
            "mime_type": created.mime_type,
            "extension": created.extension,
            "file_size": created.file_size,
            "file_path": created.file_path,
            "link_type": "invoice",
        }

    def _notify_invoice_attached(self, request_id: int, attached_by: str, original_name: str) -> None:
        if not self.request_repo or not self.project_user_role_repo:
            return
        request_row = self.request_repo.get_model_by_id(request_id)
        if not request_row or not request_row.object_levels_id:
            return
        role_rows = self.project_user_role_repo.get_by_object_levels_id(request_row.object_levels_id)
        user_ids = {
            role_row.user_id for role_row in role_rows if role_row.user_id and role_row.user_id != attached_by
        }
        if not user_ids:
            return
        request_payload = {
            "id": request_row.id,
            "name": request_row.name,
            "status": None,
        }
        ws_manager.send_request_invoice_attached(
            list(user_ids),
            request_payload,
            {"file_name": original_name, "attached_by": attached_by},
        )

    def get_request_invoice_files(self, request_id: int):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        rows = self.repo.get_request_files(request_id, link_type="invoice")
        return [
            {
                "id": file_row.id,
                "request_file_id": request_file.id,
                "request_id": request_file.request_id,
                "link_type": request_file.link_type,
                "description": request_file.description,
                "is_main": request_file.is_main,
                "sort_order": request_file.sort_order,
                "original_name": file_row.original_name,
                "mime_type": file_row.mime_type,
                "extension": file_row.extension,
                "file_size": file_row.file_size,
                "uploaded_by": file_row.uploaded_by,
                "uploaded_at": file_row.uploaded_at,
                "file_type": {
                    "id": file_type.id,
                    "code": file_type.code,
                    "name": file_type.name,
                },
                "download_url": f"/api/supply/requests/{request_id}/attachments/{file_row.id}/download",
            }
            for request_file, file_row, file_type in rows
        ]

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Cannot create directory '{path}'. "
                    "Set SUPPLY_REQUEST_FILES_DIR to a writable path."
                ),
            ) from exc

    def get_download_file_payload(self, request_id: int, file_id: str, user_id: str):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        row = self.repo.get_request_file(request_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        if not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="download",
                user_id=user_id,
            )
        )

        return {
            "path": file_row.file_path,
            "filename": file_row.original_name,
            "media_type": file_row.mime_type,
        }

    def delete_request_file(self, request_id: int, file_id: str, user_id: str):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        row = self.repo.get_request_file(request_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        original_name = file_row.original_name
        self.repo.mark_file_deleted(file_row)
        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="delete",
                user_id=user_id,
            )
        )

        if self.request_repo:
            self.request_repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="file_detached",
                description=f"Удалён файл: {original_name}",
            )

        if os.path.exists(file_row.file_path):
            os.remove(file_row.file_path)

        return None

    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def get_preview(self, file_id: str) -> str:
        import subprocess

        file_row = self.repo.get_file_by_id(file_id)
        if not file_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not file_row.file_path or not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        ext = Path(file_row.file_path).suffix.lower()
        if ext == ".pdf":
            return file_row.file_path

        if ext not in self.PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")

        cached = Path(file_row.file_path).parent / f"{Path(file_row.file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), file_row.file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(file_row.file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversion produced no output")

        return str(cached)

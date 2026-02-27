import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB, RequestFile
from app.repositories.request_file_repository import RequestFileRepository

BASE_REQUEST_FILES_DIR = "/home/webserver/models/supply/request"


class RequestFileService:
    def __init__(self, repo: RequestFileRepository) -> None:
        self.repo = repo

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
        os.makedirs(request_dir, exist_ok=True)
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

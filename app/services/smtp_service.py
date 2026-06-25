from __future__ import annotations

from fastapi import HTTPException, status

from app.models.smtp import (
    SmtpCreate,
    SmtpResponse,
    SmtpSecretResponse,
    SmtpUpdate,
    decrypt_password,
    encrypt_password,
)
from app.repositories.smtp_repository import SmtpRepository


class SmtpService:
    def __init__(self, repo: SmtpRepository) -> None:
        self.repo = repo

    def get_by_user_id(self, user_id: str):
        rows = self.repo.get_by_user_id(user_id)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")
        return [self._serialize(row) for row in rows]

    def get_secret_by_user_id(self, user_id: str):
        rows = self.repo.get_by_user_id(user_id)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")
        return [self._serialize_secret(row) for row in rows]

    def get_secret_by_id(self, smtp_id: str):
        row = self.repo.get_by_id(smtp_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")
        return self._serialize_secret(row)

    def create(self, payload: SmtpCreate):
        data = payload.model_dump()
        data["password_hash"] = encrypt_password(data.pop("password"))
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, smtp_id: str, payload: SmtpUpdate):
        row = self.repo.get_by_id(smtp_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")

        data = payload.model_dump(exclude_unset=True)
        password = data.pop("password", None)
        if password:
            data["password_hash"] = encrypt_password(password)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, smtp_id: str):
        row = self.repo.get_by_id(smtp_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP settings not found")
        self.repo.delete(row)
        return None

    @staticmethod
    def _serialize(row) -> SmtpResponse:
        return SmtpResponse(
            id=row.id,
            user_id=row.user_id,
            email=row.email,
            smtp_server=row.smtp_server,
            port=row.port,
            security=row.security,
            created_at=row.created_at,
        )

    @staticmethod
    def _serialize_secret(row) -> SmtpSecretResponse:
        return SmtpSecretResponse(
            id=row.id,
            user_id=row.user_id,
            smtp_server=row.smtp_server,
            email=row.email,
            password=decrypt_password(row.password_hash),
            port=row.port,
            security=row.security,
            created_at=row.created_at,
        )

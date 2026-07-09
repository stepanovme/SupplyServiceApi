from __future__ import annotations
from app.database import msk_now

import base64
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Integer, String

from app.database import SupplyBase


class Smtp(SupplyBase):
    __tablename__ = "smtp"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    smtp_server = Column(String(200), nullable=True)
    email = Column(String(300), nullable=False)
    password_hash = Column(String(1000), nullable=False)
    port = Column(Integer, nullable=False)
    security = Column(String(10), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class SmtpCreate(BaseModel):
    user_id: str
    smtp_server: str | None = Field(default=None)
    email: str
    password: str = Field(min_length=1)
    port: int
    security: Literal["none", "ssl", "tls"]


class SmtpUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    smtp_server: str | None = Field(default=None)
    email: str | None = Field(default=None)
    password: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None)
    security: Literal["none", "ssl", "tls"] | None = Field(default=None)


class SmtpResponse(BaseModel):
    id: str
    user_id: str
    smtp_server: str | None = None
    email: str
    port: int
    security: Literal["none", "ssl", "tls"]
    created_at: datetime


class SmtpSecretResponse(SmtpResponse):
    password: str


def encrypt_password(password: str) -> str:
    fernet = _get_fernet()
    token = fernet.encrypt(password.encode("utf-8")).decode("utf-8")
    return f"fernet:{token}"


def decrypt_password(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    token = ciphertext
    if token.startswith("fernet:"):
        token = token.removeprefix("fernet:")
    fernet = _get_fernet()
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt SMTP password with current key") from exc


def _get_fernet() -> Fernet:
    key = os.getenv("SMTP_ENCRYPTION_KEY")
    project_root = Path(__file__).resolve().parents[2]
    key_path = project_root / ".smtp_encryption.key"

    if not key:
        load_dotenv(project_root / ".env", override=True)
        key = os.getenv("SMTP_ENCRYPTION_KEY")

    if not key and key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()

    if not key:
        secret = os.getenv("SMTP_ENCRYPTION_SECRET")
        if secret:
            key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
            key = base64.urlsafe_b64encode(key_bytes).decode("utf-8")
        else:
            key = Fernet.generate_key().decode("utf-8")

        key_path.write_text(key, encoding="utf-8")

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise ValueError("SMTP_ENCRYPTION_KEY is invalid") from exc

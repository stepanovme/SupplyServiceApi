import os
import tempfile
import warnings

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import HTTPException, status

warnings.filterwarnings(
    "ignore",
    message="PKCS#12 bundle could not be parsed as DER",
    category=UserWarning,
)


class SberbankClientError(HTTPException):
    pass


def _load_pfx_cert_and_key(pfx_path: str, passphrase: str | None) -> tuple[bytes, bytes]:
    if not pfx_path or not os.path.exists(pfx_path):
        raise SberbankClientError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для этой интеграции не загружен PFX-сертификат (см. POST .../pfx)",
        )

    with open(pfx_path, "rb") as f:
        pfx_bytes = f.read()

    password = passphrase.encode() if passphrase else None
    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(pfx_bytes, password)
    except Exception as exc:
        raise SberbankClientError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать PFX-сертификат (неверный файл или пароль)",
        ) from exc

    if not private_key or not certificate:
        raise SberbankClientError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PFX-файл не содержит сертификат или приватный ключ",
        )

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    for extra_cert in additional_certs or []:
        cert_pem += extra_cert.public_bytes(serialization.Encoding.PEM)

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def fetch_sberbank_statement(
    api_host: str,
    api_token: str,
    pfx_path: str,
    pfx_passphrase: str | None,
    account_number: str,
    statement_date: str,
    ca_bundle_path: str | None = None,
    ssl_verify: bool = True,
) -> list[dict]:
    cert_pem, key_pem = _load_pfx_cert_and_key(pfx_path, pfx_passphrase)

    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    try:
        cert_file.write(cert_pem)
        cert_file.flush()
        key_file.write(key_pem)
        key_file.flush()
        os.chmod(cert_file.name, 0o600)
        os.chmod(key_file.name, 0o600)

        if not ssl_verify:
            verify: bool | str = False
        elif ca_bundle_path:
            if not os.path.exists(ca_bundle_path):
                raise SberbankClientError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ca_bundle_path не найден на диске: {ca_bundle_path}",
                )
            verify = ca_bundle_path
        else:
            verify = True

        url = f"{api_host.rstrip('/')}/fintech/api/v2/statement/transactions"
        try:
            with httpx.Client(cert=(cert_file.name, key_file.name), verify=verify, timeout=60.0) as client:
                response = client.get(
                    url,
                    params={"accountNumber": account_number, "statementDate": statement_date},
                    headers={"Authorization": f"Bearer {api_token}"},
                )
        except httpx.HTTPError as exc:
            hint = ""
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                hint = (
                    " — сервер отдаёт цепочку с самоподписанным/неизвестным сертификатом. "
                    "Либо укажите в config интеграции корневой сертификат Сбербанка "
                    "('ca_bundle_path': путь к PEM-файлу), либо на время теста выставьте "
                    "'ssl_verify': false (только для песочницы, небезопасно для прода)."
                )
            raise SberbankClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ошибка соединения с API Сбербанка: {exc}{hint}",
            ) from exc

        if response.status_code >= 400:
            raise SberbankClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"API Сбербанка вернул ошибку {response.status_code}: {response.text[:500]}",
            )

        data = response.json()
        return data.get("transactions") or []
    finally:
        cert_file.close()
        key_file.close()
        os.unlink(cert_file.name)
        os.unlink(key_file.name)


def fetch_sberbank_corporate_cards(
    api_host: str,
    api_token: str,
    pfx_path: str,
    pfx_passphrase: str | None,
    ca_bundle_path: str | None = None,
    ssl_verify: bool = True,
    page_size: int = 100,
) -> list[dict]:
    cert_pem, key_pem = _load_pfx_cert_and_key(pfx_path, pfx_passphrase)

    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    try:
        cert_file.write(cert_pem)
        cert_file.flush()
        key_file.write(key_pem)
        key_file.flush()
        os.chmod(cert_file.name, 0o600)
        os.chmod(key_file.name, 0o600)

        if not ssl_verify:
            verify: bool | str = False
        elif ca_bundle_path:
            if not os.path.exists(ca_bundle_path):
                raise SberbankClientError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ca_bundle_path не найден на диске: {ca_bundle_path}",
                )
            verify = ca_bundle_path
        else:
            verify = True

        url = f"{api_host.rstrip('/')}/fintech/api/v2/corporate-cards/list"
        all_cards: list[dict] = []
        offset = 0

        try:
            with httpx.Client(cert=(cert_file.name, key_file.name), verify=verify, timeout=60.0) as client:
                while True:
                    response = client.post(
                        url,
                        json={"pagination": {"offset": offset, "count": page_size}},
                        headers={"Authorization": f"Bearer {api_token}"},
                    )
                    if response.status_code >= 400:
                        raise SberbankClientError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"API Сбербанка вернул ошибку {response.status_code}: {response.text[:500]}",
                        )

                    data = response.json()
                    cards = data.get("cards") or []
                    all_cards.extend(cards)

                    pagination = data.get("pagination") or {}
                    if not pagination.get("hasNextPage") or not cards:
                        break
                    offset += page_size
        except httpx.HTTPError as exc:
            hint = ""
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                hint = (
                    " — сервер отдаёт цепочку с самоподписанным/неизвестным сертификатом. "
                    "Либо укажите в config интеграции корневой сертификат Сбербанка "
                    "('ca_bundle_path': путь к PEM-файлу), либо на время теста выставьте "
                    "'ssl_verify': false (только для песочницы, небезопасно для прода)."
                )
            raise SberbankClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ошибка соединения с API Сбербанка: {exc}{hint}",
            ) from exc

        return all_cards
    finally:
        cert_file.close()
        key_file.close()
        os.unlink(cert_file.name)
        os.unlink(key_file.name)

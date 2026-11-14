import os
from datetime import datetime

import httpx
from fastapi import HTTPException, status

from app.models.settings_api_bank import DEFAULT_TBANK_API_HOST


class TbankClientError(HTTPException):
    pass


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_direction(op: dict) -> str | None:
    raw = op.get("typeOfOperation") or op.get("operationType") or op.get("direction") or op.get("type")
    if not raw:
        return None
    raw_lower = str(raw).strip().lower()
    if raw_lower.startswith("cred") or raw_lower in ("in", "incoming"):
        return "CREDIT"
    if raw_lower.startswith("deb") or raw_lower in ("out", "outgoing"):
        return "DEBIT"
    return str(raw).upper()


def _as_amount(op: dict) -> float | None:
    raw = op.get("operationAmount")
    if raw is None:
        raw = op.get("rubleAmount")
    if raw is None:
        raw = op.get("amount")
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("amount"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _party_info(op: dict, key_options: list[str]) -> dict:
    for key in key_options:
        value = op.get(key)
        if isinstance(value, dict):
            return value
    return {}


def parse_tbank_operation(op: dict) -> dict:
    """Maps a single T-Bank (Tinkoff Business OpenAPI) statement operation to the common
    parsed-row shape shared with the Sberbank/Excel ingestion paths (see
    ExtractItemService._store_parsed_row). Verified against a real `/v1/statement`
    response: amount is `operationAmount`, parties are `payer`/`receiver` with account
    number under `acct` (not `accountNumber`).
    """
    payer_info = _party_info(op, ["payer", "payerInfo"])
    receiver_info = _party_info(op, ["receiver", "receiverInfo", "payeeInfo", "payee"])

    return {
        "operation_date": _parse_datetime(op.get("operationDate") or op.get("docDate") or op.get("date")),
        "amount": _as_amount(op),
        "direction": _as_direction(op),
        "payment_purpose": op.get("payPurpose") or op.get("paymentPurpose") or op.get("purpose"),
        "payee_inn": receiver_info.get("inn"),
        "payee_kpp": receiver_info.get("kpp"),
        "payee_name": receiver_info.get("name") or receiver_info.get("shortName"),
        "payer_inn": payer_info.get("inn"),
        "payer_kpp": payer_info.get("kpp"),
        "payer_name": payer_info.get("name") or payer_info.get("shortName"),
        "payee_bank_name": receiver_info.get("bankName"),
        "payee_account": receiver_info.get("acct") or receiver_info.get("accountNumber") or receiver_info.get("account"),
        "external_id": op.get("operationId"),
    }


def fetch_tbank_statement(
    api_token: str,
    account_number: str,
    date_from: str,
    date_to: str | None = None,
    api_host: str | None = None,
    cert_path: str | None = None,
    key_path: str | None = None,
    ca_bundle_path: str | None = None,
    ssl_verify: bool = True,
) -> list[dict]:
    """GET {api_host}/openapi/api/v1/statement?accountNumber=...&from=...&to=...

    T-Bank (Tinkoff Business) OpenAPI needs a Bearer token *and* a client TLS certificate
    (mTLS) - `cert_path`/`key_path` (plain PEM files, uploaded via
    POST /settings-api-bank/{id}/tbank-cert). `date_from`/`date_to` are ISO-8601
    datetimes, e.g. "2026-09-23T21:00:00Z".
    """
    host = (api_host or DEFAULT_TBANK_API_HOST).rstrip("/")

    if not ssl_verify:
        verify: bool | str = False
    elif ca_bundle_path:
        if not os.path.exists(ca_bundle_path):
            raise TbankClientError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ca_bundle_path не найден на диске: {ca_bundle_path}",
            )
        verify = ca_bundle_path
    else:
        verify = True

    cert: tuple[str, str] | None = None
    if cert_path and key_path:
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            raise TbankClientError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cert_path/key_path указаны, но файлы не найдены на диске",
            )
        cert = (cert_path, key_path)

    params = {"accountNumber": account_number, "from": date_from}
    if date_to:
        params["to"] = date_to

    url = f"{host}/openapi/api/v1/statement"
    try:
        with httpx.Client(cert=cert, verify=verify, timeout=60.0) as client:
            response = client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        hint = ""
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            hint = (
                " — сервер отдаёт цепочку с самоподписанным/неизвестным сертификатом. "
                "Укажите в config интеграции 'ca_bundle_path' (путь к PEM с корневым "
                "сертификатом) либо на время теста 'ssl_verify': false (небезопасно для прода)."
            )
        elif not cert:
            hint = " — похоже, T-Bank требует клиентский сертификат: загрузите его через POST /settings-api-bank/{id}/tbank-cert."
        raise TbankClientError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка соединения с API Т-Банка: {exc}{hint}",
        ) from exc

    if response.status_code >= 400:
        raise TbankClientError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"API Т-Банка вернул ошибку {response.status_code}: {response.text[:500]}",
        )

    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("operations") or data.get("Operations") or data.get("items") or []

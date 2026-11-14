import logging
import os
import re
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values, load_dotenv
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

API_URL = "https://proverkacheka.com/api/v1/check/get"
# The service asks the tax authority (FNS) and may take up to ~60 s to answer for a receipt it doesn't know yet.
TIMEOUT_SECONDS = 75.0

# Top-level `code` of the service's answer: 1 - receipt found, data returned.
CODE_OK = 1
# Both of these concern the RECEIPT, not the key - every key gets the same answer for the same receipt,
# so they neither put a key to rest nor make the next key worth trying (extra calls would only count
# against the receipt again):
#   3: "Превышено количество обращений по чеку." - this receipt was requested too many times;
#   4: "Не вышло время ожидания перед повторным запросом." - the same receipt again too soon (~a minute).
CODE_RECEIPT_CALLS_EXCEEDED = 3
CODE_REPEAT_TOO_SOON = 4
RECEIPT_CODES = {CODE_RECEIPT_CALLS_EXCEEDED, CODE_REPEAT_TOO_SOON}
# The service has no public documentation, so a key running out of quota is recognised by HTTP 429 or
# by the wording of the message (never for the receipt codes above).
LIMIT_WORDS = re.compile(r"лимит|limit|quota|квот|исчерп|too many|balance|баланс", re.IGNORECASE)

# A refused receipt is not asked about again for a while: repeating the call is exactly what the
# service punishes. code -> seconds.
REFUSAL_TTL_SECONDS = {CODE_RECEIPT_CALLS_EXCEEDED: 10 * 60, CODE_REPEAT_TOO_SOON: 70, 5: 60}
_refusals: dict[str, tuple[float, HTTPException]] = {}

# After a key hits its limit it is not used for a while (a per-minute limit comes back sooner than a daily one).
COOLDOWN_SECONDS = 10 * 60

TOKEN_ENV_NAMES = ("PROVERKACHEKA_TOKEN", "PROVERKACHEKA_TOKEN_2", "PROVERKACHEKA_TOKEN_3")

_blocked_until: dict[str, float] = {}


def _env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        value = os.getenv(name)
    return (value or "").strip()


def _env_file_value(name: str) -> str:
    try:
        return (dotenv_values(Path(__file__).resolve().parents[2] / ".env").get(name) or "").strip()
    except Exception:
        return ""


def get_tokens() -> list[str]:
    """Main key first, then the reserve ones; empty and repeated values are dropped.

    A key that is empty in the process environment (e.g. the server started when the line in .env
    was still blank) is read from the .env file, so adding a key doesn't require a restart."""
    tokens: list[str] = []
    for name in TOKEN_ENV_NAMES:
        value = _env(name) or _env_file_value(name)
        if value and value not in tokens:
            tokens.append(value)
    return tokens


def _message(payload: dict) -> str | None:
    data = payload.get("data")
    if isinstance(data, str) and data.strip():
        return data.strip()
    for key in ("message", "error"):
        if isinstance(payload.get(key), str) and payload[key].strip():
            return payload[key].strip()
    return None


def _is_limit(http_status: int | None, payload: dict) -> bool:
    """True when the answer says this KEY has used up its limit."""
    if http_status == 429:
        return True
    code = payload.get("code")
    if code in RECEIPT_CODES:
        return False
    message = _message(payload) or ""
    return code != CODE_OK and bool(LIMIT_WORDS.search(message))


def _failure(payload: dict) -> HTTPException:
    code = payload.get("code")
    message = _message(payload)
    if code == CODE_RECEIPT_CALLS_EXCEEDED:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Сервис проверки чеков отказал: превышено количество обращений по этому чеку"
            + (f" (ответ сервиса: «{message}»)" if message else "")
            + ". Повторные попытки только ухудшают ситуацию — этот чек можно добавить вручную.",
        )
    if code == CODE_REPEAT_TOO_SOON:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Этот чек уже запрашивался минуту назад — сервис проверки чеков просит подождать "
            "около минуты перед повторным запросом того же чека и повторить",
        )
    if code == 0:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message or "Чек не найден или QR-код некорректен",
        )
    # not ready yet / upstream problems - worth trying again later
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Сервис проверки чеков не вернул данные (code={code}). "
        + (message or "Данные чека ещё не получены от ФНС, повторите запрос позже."),
    )


def _request(token: str, qrraw: str | None, file_bytes: bytes | None, filename: str, content_type: str):
    form = {"token": token}
    files = None
    if file_bytes is not None:
        files = {"qrfile": (filename, file_bytes, content_type)}
    else:
        form["qrraw"] = qrraw or ""
    return httpx.post(API_URL, data=form, files=files, timeout=TIMEOUT_SECONDS)


def fetch_receipt(
    *,
    qrraw: str | None = None,
    file_bytes: bytes | None = None,
    filename: str = "receipt.jpg",
    content_type: str = "image/jpeg",
) -> dict:
    """Asks proverkacheka.com for a receipt, either by the QR string or by a photo of the QR
    (the service decodes the picture itself). Returns the receipt JSON (`data.json`).

    Several keys can be configured (PROVERKACHEKA_TOKEN, _2, _3). When one of them reports that its
    limit is used up, the next key is tried, and the exhausted one is skipped for a while."""
    tokens = get_tokens()
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Токен proverkacheka.com не настроен (PROVERKACHEKA_TOKEN в .env)",
        )

    refusal_key = (qrraw or "").strip().lower() if file_bytes is None else None
    if refusal_key:
        remembered = _refusals.get(refusal_key)
        if remembered and remembered[0] > time.monotonic():
            raise remembered[1]  # the same answer, without asking the service again

    now = time.monotonic()
    usable = [(i, t) for i, t in enumerate(tokens, start=1) if _blocked_until.get(t, 0.0) <= now]
    if not usable:
        # Every key is resting after an earlier refusal. Refusing outright would lock receipts out for
        # the whole rest period even if the limit has already been lifted (or was misread), so one
        # request is still made with the key that frees up first.
        soonest = min(enumerate(tokens, start=1), key=lambda item: _blocked_until.get(item[1], 0.0))
        usable = [soonest]
        logger.info("all %d proverkacheka keys are resting, retrying key #%d", len(tokens), soonest[0])

    limited = 0
    replies: list[str] = []
    for number, token in usable:
        try:
            response = _request(token, qrraw, file_bytes, filename, content_type)
            payload = response.json() if response.status_code != 429 else {}
            if response.status_code != 429:
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Сервис проверки чеков недоступен: {type(exc).__name__}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Сервис проверки чеков вернул не JSON"
            ) from exc

        payload = payload if isinstance(payload, dict) else {}
        if _is_limit(response.status_code, payload):
            limited += 1
            replies.append(f"#{number}: code={payload.get('code', response.status_code)} {_message(payload) or ''}".strip())
            _blocked_until[token] = time.monotonic() + COOLDOWN_SECONDS
            logger.warning(
                "proverkacheka key #%d is out of limit (http=%s code=%s message=%r), %s",
                number, response.status_code, payload.get("code"), _message(payload),
                "trying the next key" if number != usable[-1][0] else "no keys left",
            )
            continue

        if payload.get("code") != CODE_OK:
            logger.info("proverkacheka answered code=%s message=%r (key #%d)", payload.get("code"), _message(payload), number)
            failure = _failure(payload)
            ttl = REFUSAL_TTL_SECONDS.get(payload.get("code"))
            if ttl and refusal_key:
                _refusals[refusal_key] = (time.monotonic() + ttl, failure)
            raise failure

        receipt = (payload.get("data") or {}).get("json") if isinstance(payload.get("data"), dict) else None
        if not isinstance(receipt, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="В ответе сервиса проверки чеков нет данных чека"
            )
        if number != 1:
            logger.info("receipt fetched with reserve key #%d", number)
        return receipt

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            f"Лимиты ключей proverkacheka.com исчерпаны (проверено ключей: {limited} из {len(tokens)} настроенных), "
            f"повторите позже. Ответ сервиса: {'; '.join(replies)}"
        ),
    )

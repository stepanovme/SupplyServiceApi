import json
import logging
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from app.services.invoice_reference_parser import _DATE, _to_date
from app.services.mistral_retry import is_mistral_rate_limit, mistral_retry

logger = logging.getLogger(__name__)

API_KEY_ENV = "MISTRAL_INVOICE_EXTRACT_API_KEY"
MODEL = "ministral-8b-2512"
THROTTLE_KEY = "invoice_extract"
MAX_TEXT_CHARS = 1500

# "счёт" as a standalone word - NOT "Расчеты через ТУ ..." (card purchases), which contains it too.
_INVOICE_WORD_RE = re.compile(r"(?<![А-Яа-яЁё])сч[её]т(?!\w*-фактур)", re.IGNORECASE)
# Texts that mention an account/"счёт" without being a payment of an invoice.
_NOISE_RE = re.compile(
    r"со\s+сч[её]та|на\s+сч[её]т|сч[её]т[ае]?\s+(?:ЮЛ|ФЛ)|расч[её]тн\w*\s+сч|по\s+карте|комисси|"
    r"между\s+(?:своими|сч[её]тами)|зарплат|заработн|отпуск|командиров",
    re.IGNORECASE,
)
_ANY_DATE_RE = re.compile(_DATE)

_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
# "14 июля 2023 г", "04 сентября 2026г.", "9 июля 2026"
_WORD_DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})", re.IGNORECASE
)

PROMPT = (
    "Из назначения банковского платежа извлеки СЧЕТА НА ОПЛАТУ, которые этим платежом оплачиваются.\n"
    "Правила:\n"
    "- Нужны только номер и дата именно СЧЁТА («по счету №104 от 23.09.2026»). Номера и даты "
    "договоров, актов, УПД, платёжных поручений, реестров, счетов-фактур, заказов НЕ нужны.\n"
    "- Номер верни ТОЧНО так, как он написан в тексте (без знака «№»), ничего не достраивай и не исправляй.\n"
    "- Дату верни как YYYY-MM-DD. Если у счёта в тексте нет даты, поставь null. Дату не выдумывай.\n"
    "- Если в тексте нет счёта на оплату - верни пустой список.\n"
    'Верни ТОЛЬКО JSON: {{"invoices": [{{"num": "...", "date": "YYYY-MM-DD"|null}}]}}\n\n'
    "Назначение платежа: {text}"
)


def should_try_ai(payment_purpose: str | None) -> bool:
    """Cheap gate so we don't spend a model call on card purchases, fees, salaries, etc."""
    if not payment_purpose:
        return False
    if not _INVOICE_WORD_RE.search(payment_purpose):
        return False
    if _NOISE_RE.search(payment_purpose):
        return False
    return any(ch.isdigit() for ch in payment_purpose)


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def validate_ai_references(raw: object, payment_purpose: str) -> tuple[list[tuple[str, date]], str | None]:
    """Keeps only what the text itself backs up, so the model can't invent a number or date:
    the number has to appear in the text verbatim, and the date has to appear in the text as
    dd.mm.yy(yy) and equal the date returned. Returns (refs, note)."""
    if not isinstance(raw, dict):
        return [], "ai_bad_response"
    items = raw.get("invoices")
    if not isinstance(items, list):
        return [], "ai_bad_response"

    haystack = _norm(payment_purpose)
    dates_in_text = {
        d for m in _ANY_DATE_RE.finditer(payment_purpose)
        if (d := _to_date(m.group(1), m.group(2), m.group(3))) is not None
    }
    for m in _WORD_DATE_RE.finditer(payment_purpose):
        d = _to_date(m.group(1), str(_MONTHS[m.group(2).lower()]), m.group(3))
        if d is not None:
            dates_in_text.add(d)

    refs: list[tuple[str, date]] = []
    note: str | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        num = str(item.get("num") or "").strip().lstrip("№").strip()
        raw_date = item.get("date")
        if not num or _norm(num) not in haystack:
            note = note or "ai_number_not_in_text"
            continue
        if not raw_date:
            note = note or "ai_found_number_without_date"
            continue
        try:
            ref_date = date.fromisoformat(str(raw_date))
        except ValueError:
            note = note or "ai_bad_date"
            continue
        if ref_date not in dates_in_text:
            note = note or "ai_date_not_in_text"
            continue
        ref = (num, ref_date)
        if ref not in refs:
            refs.append(ref)
    return refs, note


def _get_api_key() -> str | None:
    key = os.getenv(API_KEY_ENV)
    if not key:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
        key = os.getenv(API_KEY_ENV)
    return key or None


def extract_invoice_references_ai(payment_purpose: str) -> tuple[list[tuple[str, date]], str | None]:
    """Fallback for texts the regex parser couldn't read. Never raises: returns ([], note) when
    the AI is unavailable, so the matcher just reports 'no_invoice_reference' as before."""
    api_key = _get_api_key()
    if not api_key:
        return [], "ai_disabled_no_api_key"

    try:
        from mistralai import Mistral
    except Exception:
        return [], "ai_unavailable"

    try:
        client = Mistral(api_key=api_key)
        response = mistral_retry(
            client.chat.complete,
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT.format(text=payment_purpose[:MAX_TEXT_CHARS])}],
            response_format={"type": "json_object"},
            temperature=0.0,
            throttle_key=THROTTLE_KEY,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return [], "ai_bad_response"
    except Exception as exc:
        logger.warning("invoice AI extraction failed: %s", exc)
        return [], "ai_rate_limited" if is_mistral_rate_limit(exc) else "ai_error"

    return validate_ai_references(parsed, payment_purpose)

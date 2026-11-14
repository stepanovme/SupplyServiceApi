import logging
import os
import re
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Mistral rate limits are per-model/per-endpoint, not account-wide (see console.mistral.ai
# limits page). The OCR endpoint (mistral-ocr-latest) isn't listed alongside the chat/embedding
# models there, which in practice means it has its own - often stricter - quota, so it needs its
# own pacing instead of sharing one lock with chat/file calls.
_MIN_CALL_INTERVALS = {
    "ocr": 3.0,
    "pixtral": 3.0,
    "vision": 0.3,
    "object_name": 1.1,
    "contract_extract": 1.1,
    "invoice_extract": 1.1,
    "default": 1.1,
}

_throttle_lock = threading.Lock()
_last_call_at: dict[str, float] = {}


def _throttle(key: str):
    interval = _MIN_CALL_INTERVALS.get(key, _MIN_CALL_INTERVALS["default"])
    with _throttle_lock:
        now = time.monotonic()
        wait = interval - (now - _last_call_at.get(key, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call_at[key] = time.monotonic()


def mistral_retry(func, *args, max_retries=5, base_delay=2.0, throttle_key="default", **kwargs):
    for attempt in range(max_retries):
        try:
            _throttle(throttle_key)
            return func(*args, **kwargs)
        except Exception as exc:
            status_code = getattr(exc, "raw_response", None)
            if status_code is not None:
                status_code = getattr(status_code, "status_code", None)
            is_rate_limit = (
                status_code == 429
                or "429" in str(exc)
                or "rate_limited" in str(exc)
                or "Rate limit" in str(exc)
            )
            if is_rate_limit and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            raise


def is_mistral_rate_limit(exc: Exception) -> bool:
    status_code = getattr(exc, "raw_response", None)
    if status_code is not None:
        status_code = getattr(status_code, "status_code", None)
    return (
        status_code == 429
        or "429" in str(exc)
        or "rate_limited" in str(exc)
        or "Rate limit" in str(exc)
    )


# --- document recognition -------------------------------------------------------------------

# Dedicated OCR model. `mistral-ocr-4-1` is what `mistral-ocr-latest` points to today. Override
# with MISTRAL_OCR_MODEL in .env; set it to "off" to skip OCR entirely.
DEFAULT_OCR_MODEL = "mistral-ocr-4-1"
# Fast vision model used as the main recognizer. On a real 2-page invoice ministral-3b with the
# FULL prompt matched every checked field in 8 of 8 runs at ~13-20s; pixtral needed 42-52s.
# Override with DOCUMENT_VISION_MODEL.
DEFAULT_VISION_MODEL = "ministral-3b-2512"
# Last-resort vision model. Not in the account's model list but works; kept as a safety net.
VISION_FALLBACK_MODEL = "pixtral-12b-latest"
# After a provider answers 429 (e.g. this account's Mistral OCR quota is exhausted/zero), don't
# try it again for a while - otherwise every document would pay for one more failed call.
PROVIDER_COOLDOWN_SECONDS = 600

# Providers that exist. mistral_ocr is opt-in: this account's quota for the OCR endpoint is zero
# (every call answers 429), so it's left out until that changes - list it in DOCUMENT_OCR_ORDER
# to use it, e.g. "mistral_ocr,vision,pixtral".
ALL_PROVIDERS = ("mistral_ocr", "vision", "pixtral")
DEFAULT_PROVIDER_ORDER = ("vision", "pixtral")
# "pixtral" is always kept as the last resort.

# Transcription prompts. FULL (default) copies the whole document. LEAN skips standard
# terms-and-conditions boilerplate and is ~2x faster, but it is NOT reliable: over repeated runs
# on a real invoice ministral-3b silently dropped prices/totals/VAT in 2 of 8 runs, pixtral lost the
# whole invoice page in 1 of 4 and ministral-14b in 3 of 4. A silently missing total is worse than a
# few extra seconds, so LEAN is opt-in only (DOCUMENT_OCR_PROMPT=lean).
FULL_PROMPT = (
    "Transcribe the full text content of this document exactly as written, "
    "preserving structure, tables and line breaks. "
    "Return only the extracted text, no commentary."
)
LEAN_PROMPT = (
    "Transcribe this document to markdown exactly as written, keeping ALL: document title, number and "
    "date; every party with name, INN, KPP, address and phone; bank details; every table (all rows and "
    "columns, numbers copied exactly); totals, VAT, amount in words; signer names. "
    "SKIP long standard terms-and-conditions / legal boilerplate paragraphs and warnings - replace each "
    "such paragraph with the single word [...]. Return only the text, no commentary."
)

_blocked_until: dict[str, float] = {}


def _env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        value = os.getenv(name)
    return (value or "").strip()


def _ocr_model() -> str | None:
    value = _env("MISTRAL_OCR_MODEL")
    if value.lower() in ("off", "none", "false", "0"):
        return None
    return value or DEFAULT_OCR_MODEL


def _vision_model() -> str | None:
    value = _env("DOCUMENT_VISION_MODEL")
    if value.lower() in ("off", "none", "false", "0"):
        return None
    return value or DEFAULT_VISION_MODEL


def _prompt() -> str:
    return LEAN_PROMPT if _env("DOCUMENT_OCR_PROMPT").lower() == "lean" else FULL_PROMPT


_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*\n|\n?```\s*$")
_DOC_MARKER_RE = re.compile(r"\s*<(?:START|END) OF DOCUMENT>\s*", re.IGNORECASE)


def _clean_model_text(text: str) -> str:
    """Small chat models like to wrap the transcription in ```markdown fences and/or
    <START OF DOCUMENT> markers; neither belongs to the document."""
    text = _DOC_MARKER_RE.sub("\n", text or "")
    return _FENCE_RE.sub("", text).strip()


def _recognize_with_ocr(client, document_url: str, model: str) -> str:
    # max_retries=1: a 429 must fail fast so we can fall back, not sleep through backoff.
    response = mistral_retry(
        client.ocr.process,
        model=model,
        document={"type": "document_url", "document_url": document_url},
        throttle_key="ocr",
        max_retries=1,
    )
    return "\n\n".join(page.markdown for page in response.pages)


def _recognize_with_vision(client, document_url: str, model: str, *, last_resort: bool = False) -> str:
    response = mistral_retry(
        client.chat.complete,
        model=model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "document_url", "document_url": document_url},
                    {"type": "text", "text": _prompt()},
                ],
            }
        ],
        throttle_key="pixtral" if last_resort else "vision",
        # The last resort has nobody to fall back to, so it's allowed to wait out rate limits;
        # everything earlier fails fast and lets the next provider take over.
        max_retries=8 if last_resort else 2,
        base_delay=3.0 if last_resort else 2.0,
    )
    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return _clean_model_text(content)


def _provider_order() -> list[str]:
    raw = _env("DOCUMENT_OCR_ORDER")
    names = [n.strip().lower() for n in (raw or ",".join(DEFAULT_PROVIDER_ORDER)).split(",")]
    order: list[str] = []
    for name in names:
        if name in ALL_PROVIDERS and name not in order:
            order.append(name)
    if "pixtral" not in order:
        order.append("pixtral")
    return order


def _try_provider(name: str, client, document_url: str, is_last: bool) -> str | None:
    """Text from one provider, or None if it's unavailable/failed (so the next one is tried).
    Only the LAST provider in the chain is allowed to raise."""
    if not is_last and time.monotonic() < _blocked_until.get(name, 0.0):
        return None

    try:
        if name == "mistral_ocr":
            model = _ocr_model()
            if not model:
                return None
            text = _recognize_with_ocr(client, document_url, model)
        elif name == "vision":
            model = _vision_model()
            if not model:
                return None
            text = _recognize_with_vision(client, document_url, model, last_resort=is_last)
        else:  # pixtral
            text = _recognize_with_vision(client, document_url, VISION_FALLBACK_MODEL, last_resort=is_last)

        if text and text.strip():
            return text
        logger.warning("%s returned empty text, trying the next provider", name)
    except Exception as exc:
        if is_last:
            raise
        if is_mistral_rate_limit(exc):
            _blocked_until[name] = time.monotonic() + PROVIDER_COOLDOWN_SECONDS
            logger.warning("%s is rate-limited, skipping it for the next %ss", name, PROVIDER_COOLDOWN_SECONDS)
        else:
            logger.warning("%s failed (%s), trying the next provider", name, exc)
    return None


def recognize_document_text(client, document_url: str) -> str:
    """Document -> text. Walks the provider chain (DOCUMENT_OCR_ORDER, default
    vision -> pixtral) and returns the first non-empty result:
      - vision:      fast vision chat model (DOCUMENT_VISION_MODEL, default ministral-3b-2512);
      - pixtral:     slower vision model, the final fallback;
      - mistral_ocr: opt-in; the dedicated OCR model (MISTRAL_OCR_MODEL, default mistral-ocr-4-1).
    A provider that answers 429 is skipped for PROVIDER_COOLDOWN_SECONDS. The prompt is the
    verbatim FULL one unless DOCUMENT_OCR_PROMPT=lean (faster, but may drop data - see above)."""
    order = _provider_order()
    for index, name in enumerate(order):
        text = _try_provider(name, client, document_url, is_last=index == len(order) - 1)
        if text is not None:
            logger.info("document recognized via %s (%d chars)", name, len(text))
            return text
    raise RuntimeError("no document recognition provider returned text")

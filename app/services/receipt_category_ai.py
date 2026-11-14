import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from app.services.mistral_retry import is_mistral_rate_limit, mistral_retry

logger = logging.getLogger(__name__)

API_KEY_ENV = "MISTRAL_RECEIPT_CATEGORY_API_KEY"  # its own key, like every other AI feature
MODEL_ENV = "RECEIPT_CATEGORY_MODEL"
DEFAULT_MODEL = "ministral-8b-2512"
MAX_CATEGORIES = 3
MAX_ITEMS = 60

PROMPT = (
    "Ты бухгалтер строительной компании и относишь кассовые чеки к категориям расходов.\n"
    "По позициям чека выбери от 1 до {max_categories} подходящих категорий ИЗ СПИСКА НИЖЕ (только из него, "
    "ничего не придумывай). Выбирай категории, к которым относятся покупки в чеке; главная по сумме идёт первой. "
    "Категорию «Прочее» выбирай, только если ничего другого не подходит. "
    "Если ни одна категория не подходит, верни пустой список.\n\n"
    "Категории:\n{categories}\n\n"
    "Продавец: {seller}\n"
    "Позиции чека (название; количество; сумма в рублях):\n{items}\n\n"
    'Верни ТОЛЬКО валидный JSON с НОМЕРАМИ категорий из списка: {{"categories": [1, 3]}}'
)


def _api_key() -> str:
    value = os.getenv(API_KEY_ENV)
    if value is None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        value = os.getenv(API_KEY_ENV)
    return (value or "").strip()


def is_configured() -> bool:
    return bool(_api_key())


def _parse_numbers(content: str) -> list[int]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
    data = json.loads(cleaned)
    numbers = data.get("categories") if isinstance(data, dict) else data
    if not isinstance(numbers, list):
        raise ValueError("no categories list in the answer")
    result: list[int] = []
    for n in numbers:
        try:
            value = int(n)
        except (TypeError, ValueError):
            continue
        if value not in result:
            result.append(value)
    return result


def suggest_category_ids(seller: str | None, items: list[dict], categories: list[dict]) -> tuple[list[str], str | None]:
    """Picks categories for a receipt by its positions with Mistral.

    items: [{name, quantity, sum}], categories: [{id, name}] (only the ones the user may use).
    Returns (category ids, note). It never raises: on any problem the ids are empty and the note
    says why, because a failed suggestion must not break adding the receipt. The model answers with
    list numbers, not ids, and anything outside the list is dropped, so it can't invent a category."""
    if not categories:
        return [], "no_categories"
    if not items:
        return [], "no_items"
    key = _api_key()
    if not key:
        return [], "api_key_not_set"

    try:
        from mistralai import Mistral
    except Exception:
        return [], "mistralai_not_installed"

    category_lines = "\n".join(f"{i}. {c['name']}" for i, c in enumerate(categories, start=1))
    item_lines = "\n".join(
        f"- {str(it['name'])[:120]}; {it['quantity']:g}; {it['sum']:.2f}" for it in items[:MAX_ITEMS]
    )
    prompt = PROMPT.format(
        max_categories=MAX_CATEGORIES, categories=category_lines, seller=seller or "не указан", items=item_lines
    )

    try:
        client = Mistral(api_key=key)
        response = mistral_retry(
            client.chat.complete,
            model=(os.getenv(MODEL_ENV) or DEFAULT_MODEL).strip(),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            throttle_key="receipt_category",
            max_retries=3,
            base_delay=2.0,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        numbers = _parse_numbers(content)
    except Exception as exc:
        logger.warning("receipt category suggestion failed: %s", exc)
        return [], "rate_limited" if is_mistral_rate_limit(exc) else "ai_error"

    chosen: list[str] = []
    for n in numbers:
        if 1 <= n <= len(categories) and categories[n - 1]["id"] not in chosen:
            chosen.append(categories[n - 1]["id"])
    return chosen[:MAX_CATEGORIES], None if chosen else "no_match"

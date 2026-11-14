import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.services.mistral_retry import is_mistral_rate_limit, mistral_retry

API_KEY_ENV = "MISTRAL_CONTRACT_EXTRACT_API_KEY"
MODEL = "ministral-8b-2512"
THROTTLE_KEY = "contract_extract"

PROMPT = (
    "Ты анализируешь назначение банковского платежа (paymentPurpose) и определяешь, "
    "относится ли платёж к оплате ДОГОВОРА (не счёта, не акта, не аренды без договора и т.п.), "
    "и если относится - извлекаешь номер и дату договора.\n\n"
    "Считай платёж оплатой договора, только если в тексте явно указано что-то вроде "
    "«по договору №X от DD.MM.YYYY» или «согласно договору №X от DD.MM.YYYY» - то есть есть "
    "ссылка именно на ДОГОВОР с номером и датой. Если в тексте упомянут только счёт "
    "(«по счёту №...», «счёт-фактура №...») без явной ссылки на договор с номером и датой - "
    "это НЕ оплата договора, даже если по смыслу это оплата за товары/услуги.\n"
    "Если в тексте есть ссылка и на договор, и на счёт одновременно (например счёт выставлен "
    "в рамках договора) - это оплата договора, извлекай именно реквизиты договора.\n\n"
    "Дату договора верни строго в формате YYYY-MM-DD (день.месяц.год из текста -> год-месяц-день).\n"
    "Номер договора верни ровно так, как написан в тексте (без слова «№»).\n\n"
    'Верни ТОЛЬКО валидный JSON: {{"is_contract_payment": true|false, "contract_num": "..."|null, "contract_date": "YYYY-MM-DD"|null}}\n\n'
    "Назначение платежа: {payment_purpose}"
)


def _get_api_key() -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
        api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{API_KEY_ENV} is not set",
        )
    return api_key


def extract_contract_reference(payment_purpose: str) -> dict:
    """Returns {"is_contract_payment": bool, "contract_num": str|None, "contract_date": str|None}."""
    if not payment_purpose or not payment_purpose.strip():
        return {"is_contract_payment": False, "contract_num": None, "contract_date": None}

    try:
        from mistralai import Mistral
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="mistralai package is not installed",
        ) from exc

    client = Mistral(api_key=_get_api_key())
    try:
        response = mistral_retry(
            client.chat.complete,
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT.format(payment_purpose=payment_purpose)}],
            response_format={"type": "json_object"},
            temperature=0.0,
            throttle_key=THROTTLE_KEY,
        )
    except Exception as exc:
        if is_mistral_rate_limit(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис распознавания договоров временно перегружен. Попробуйте ещё раз через минуту.",
            ) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось распознать назначение платежа") from exc

    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)

    cleaned = (content or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось разобрать ответ модели") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось разобрать ответ модели")

    return {
        "is_contract_payment": bool(data.get("is_contract_payment")),
        "contract_num": (data.get("contract_num") or None),
        "contract_date": (data.get("contract_date") or None),
    }

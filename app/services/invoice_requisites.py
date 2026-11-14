"""Recipient requisites of an invoice (ИНН, КПП, банк, Р/С, К/С, БИК, назначение платежа).

One place that knows what a valid value looks like. Typed by a person (strict=True) a wrong value is
rejected with a clear message; read from a document by the model (strict=False) a wrong value is simply
dropped, because a half-recognised account number is worse than an empty field.
"""
import re

from fastapi import HTTPException, status

REQUISITE_FIELDS = (
    "recipient_inn",
    "recipient_kpp",
    "recipient_bank_name",
    "recipient_account",
    "recipient_corr_account",
    "recipient_bik",
    "payment_purpose",
)

_SEPARATORS = re.compile(r"[\s.\-_/]")
_RULES = {
    # field: (what it is, allowed lengths, digits only)
    "recipient_inn": ("ИНН получателя", (10, 12), True),
    "recipient_kpp": ("КПП получателя", (9,), False),
    "recipient_account": ("расчётный счёт получателя (Р/С)", (20,), False),
    "recipient_corr_account": ("корреспондентский счёт банка (К/С)", (20,), False),
    "recipient_bik": ("БИК банка получателя", (9,), True),
}
_TEXT_LIMITS = {"recipient_bank_name": 255, "payment_purpose": 2000}


def clean_requisite(field: str, value, strict: bool = True) -> str | None:
    """Normalised value, None for empty. Invalid: HTTP 422 when strict, None otherwise."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if field in _TEXT_LIMITS:
        text = re.sub(r"\s+", " ", text)
        if len(text) > _TEXT_LIMITS[field]:
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Поле {field}: не больше {_TEXT_LIMITS[field]} символов",
                )
            return text[: _TEXT_LIMITS[field]]
        return text

    label, lengths, digits_only = _RULES[field]
    compact = _SEPARATORS.sub("", text).upper()
    valid = len(compact) in lengths and (compact.isdigit() if digits_only else compact.isalnum())
    if valid:
        return compact
    if strict:
        wanted = " или ".join(str(n) for n in lengths)
        kind = "цифр" if digits_only else "символов"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Поле {field}: {label} должен состоять из {wanted} {kind}",
        )
    return None


def normalize_requisites(data: dict, strict: bool = True) -> dict:
    """Cleans only the requisite keys present in `data` (so a PATCH without them leaves them alone)."""
    return {field: clean_requisite(field, data[field], strict) for field in REQUISITE_FIELDS if field in data}


# ---- who is who: Р/С or К/С -------------------------------------------------------------
# On a payment order both numbers are labelled just "Сч. №", and models often swap them. Two facts settle it:
# a bank's correspondent account starts with 301 (a bank's own account at the Central Bank), an
# organization's settlement account starts with 40 (406-408 for companies, 407 mostly); and both numbers
# carry a check digit computed with the bank's BIK.
_WEIGHTS = (7, 1, 3)


def _checksum_ok(bik: str, account: str, corr: bool) -> bool:
    """Bank-account control sum (Central Bank rule): the BIK part + the account, weights 7-1-3, sum % 10 == 0."""
    if not (bik and account and len(bik) == 9 and bik.isdigit() and len(account) == 20 and account.isdigit()):
        return False
    prefix = "0" + bik[4:6] if corr else bik[6:9]
    digits = prefix + account
    return sum(int(d) * _WEIGHTS[i % 3] % 10 for i, d in enumerate(digits)) % 10 == 0


def _is_corr(value: str | None) -> bool:
    return bool(value) and value.startswith("301")


def _is_settlement(value: str | None) -> bool:
    return bool(value) and value.startswith("40")


def fix_account_roles(account: str | None, corr: str | None, bik: str | None) -> tuple[str | None, str | None]:
    """Returns (settlement account, correspondent account) with the two put in the right fields."""
    # a 301... number is a correspondent account whatever field it came in
    if _is_corr(account) and not _is_corr(corr):
        account, corr = (corr if corr and not _is_corr(corr) else None), account
        return account, corr
    # a 40... number sits in the correspondent field: it is the settlement account
    if _is_settlement(corr) and not _is_settlement(account):
        corr, account = (account if account and _is_corr(account) else None), corr
        return account, corr
    # numbers that tell nothing by prefix: let the check digits decide
    if account and corr and bik:
        as_is = _checksum_ok(bik, account, corr=False) and _checksum_ok(bik, corr, corr=True)
        swapped = _checksum_ok(bik, corr, corr=False) and _checksum_ok(bik, account, corr=True)
        if swapped and not as_is:
            return corr, account
    return account, corr

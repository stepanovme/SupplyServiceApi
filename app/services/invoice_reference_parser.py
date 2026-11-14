import re
from datetime import date

_TOKEN = r"[0-9A-Za-zА-Яа-я/][0-9A-Za-zА-Яа-я\-/.]*"
_DATE = r"(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})"

# Explicit invoice mention followed by "<number> от <date>":
#   "по счету №104 от 23.09.2026", "Оплата счета № 970 от 06.06.2024", "СЧЕТУ №42 ОТ 07.08.2026",
#   "по счёту на оплату №5 от 01.02.26", "по счету 55 от 01.02.2026г.", "счету-договору №12623 от ..."
# "счёт-фактура" is deliberately NOT accepted - its number is the tax document's, not our invoice's.
INVOICE_REF_RE = re.compile(
    r"сч[её]т\w*(?:-(?:договор|спецификаци|оферт|контракт)\w*)?"
    r"(?:\s+на\s+оплату)?"
    r"\s*(?:№|N|No\.?)?\s*"
    rf"({_TOKEN})"
    rf"\s+от\s+{_DATE}",
    re.IGNORECASE,
)

# Any "№<number> от <date>" - used to notice additional documents in the same text
# ("по счетам №1 от 01.02.2026 и №2 от 02.02.2026") and to tell invoices from contracts.
GENERIC_REF_RE = re.compile(rf"(?:№|N|No\.?)\s*({_TOKEN})\s+от\s+{_DATE}", re.IGNORECASE)

_INVOICE_WORD_RE = re.compile(r"сч[её]т(?!\w*-фактур)", re.IGNORECASE)
_OTHER_DOC_WORD_RE = re.compile(
    r"договор|контракт|соглашени|спецификаци|поручени|заказ|накладн|\bакт\b|реестр|письм|упд|универсальн",
    re.IGNORECASE,
)


def _to_date(day: str, month: str, year: str) -> date | None:
    y = int(year)
    if y < 100:
        y += 2000
    try:
        return date(y, int(month), int(day))
    except ValueError:
        return None


def _clean_num(raw: str) -> str:
    return raw.strip().rstrip(".-/").lstrip("№")


def extract_invoice_references(payment_purpose: str | None) -> list[tuple[str, date]]:
    """Returns the distinct (invoice_num, invoice_date) pairs a payment purpose refers to,
    in order of appearance. Usually exactly one; more than one means the payment covers
    several invoices, which can't be split automatically (the caller must not guess)."""
    if not payment_purpose:
        return []

    text = payment_purpose

    # (start, end, num, date, kind) with kind in {"invoice", "other", None=unknown}
    candidates: list[tuple[int, int, str, date | None, str | None]] = []

    for m in INVOICE_REF_RE.finditer(text):
        candidates.append((m.start(), m.end(), _clean_num(m.group(1)), _to_date(m.group(2), m.group(3), m.group(4)), "invoice"))

    taken = [(c[0], c[1]) for c in candidates]
    for m in GENERIC_REF_RE.finditer(text):
        if any(s <= m.start() < e or s < m.end() <= e for s, e in taken):
            continue
        candidates.append((m.start(), m.end(), _clean_num(m.group(1)), _to_date(m.group(2), m.group(3), m.group(4)), None))

    candidates.sort(key=lambda c: c[0])

    refs: list[tuple[str, date]] = []
    previous_kind: str | None = None
    previous_end = 0
    for start, end, num, ref_date, kind in candidates:
        if kind is None:
            context = text[max(previous_end, start - 60):start]
            invoice_hits = list(_INVOICE_WORD_RE.finditer(context))
            other_hits = list(_OTHER_DOC_WORD_RE.finditer(context))
            last_invoice = invoice_hits[-1].start() if invoice_hits else -1
            last_other = other_hits[-1].start() if other_hits else -1
            if last_invoice == -1 and last_other == -1:
                kind = previous_kind  # list continuation: "... №1 от X и №2 от Y"
            else:
                kind = "invoice" if last_invoice > last_other else "other"

        previous_kind = kind
        previous_end = end

        if kind != "invoice" or not num or ref_date is None:
            continue
        ref = (num, ref_date)
        if ref not in refs:
            refs.append(ref)

    return refs


def invoice_num_variants(num: str) -> list[str]:
    """Spellings to try when looking the number up in `invoice.num` ("/ЦБ-529" may be stored
    as "ЦБ-529", and the other way round)."""
    variants = [num]
    stripped = num.lstrip("/")
    if stripped and stripped != num:
        variants.append(stripped)
    return variants

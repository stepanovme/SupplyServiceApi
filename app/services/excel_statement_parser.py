import hashlib
import io
import re
from datetime import datetime

import openpyxl
from fastapi import HTTPException, status


def _parse_ru_date(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "isoformat") and not isinstance(value, str):
        # a plain `date` object (openpyxl can hand back either depending on the cell format)
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _clean_account_number(value) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\s+", "", str(value))
    return digits or None


def _load_workbook(file_bytes: bytes):
    try:
        return openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось прочитать Excel-файл") from exc


def build_alfabank_external_id(
    account_number: str | None,
    document_number,
    operation_date,
    direction: str,
    amount: float,
    payment_purpose: str | None,
    occurrence: int = 1,
) -> str:
    """Stable per-operation key for statements that have no bank-native transaction id.

    "Номер документа" alone is NOT unique - the bank reuses it across months and between
    unrelated operations (e.g. a 242.78 card fee and a 330 000 refund shared one), so it can
    only be one ingredient. The rest pins the operation down: date, direction, amount in
    kopecks and a hash of the purpose. `occurrence` (1, 2, ...) separates rows that are
    identical in every one of those fields - they are interchangeable, so numbering them in
    file order is safe and stays consistent when overlapping statements are loaded.

    The DB migration (cmd/migrate_alfabank_external_ids.py) builds the same key from stored
    columns, so any change here must be mirrored there.
    """
    day = operation_date.strftime("%Y%m%d") if operation_date else "nodate"
    kind = "D" if direction == "DEBIT" else "C"
    kopecks = int(round(float(amount) * 100))
    purpose_hash = hashlib.sha1((payment_purpose or "").strip().encode("utf-8")).hexdigest()[:8]
    doc = str(document_number).strip() if document_number not in (None, "") else "-"
    return f"{account_number}:{doc}:{day}:{kind}:{kopecks}:{purpose_hash}#{occurrence}"


def _parse_alfabank_excel(file_bytes: bytes) -> tuple[list[dict], str | None]:
    """Layout (Альфа-Банк, «Выписка по счёту.xlsx»):

    row0: "Выписка по счёту", "<номер счёта>"
    row2: "Владелец счёта", "<название>"
    row3: "ИНН владельца", "<инн>"
    header spans two rows ("Дата"/... on one, "Наименование"/"ИНН"/... under "Контрагент" on the next)
    data rows: Дата | Номер документа | Дебет | Кредит | Наименование | ИНН | КПП | Счёт | БИК |
               Наименование банка | Назначение платежа | Код дебитора | Тип документа
    """
    wb = _load_workbook(file_bytes)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if len(rows) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не похож на выписку Альфа-Банка (слишком мало строк)",
        )

    account_number = _clean_account_number(rows[0][1]) if len(rows[0]) > 1 else None
    owner_name = rows[2][1] if len(rows) > 2 and len(rows[2]) > 1 else None
    owner_inn = rows[3][1] if len(rows) > 3 and len(rows[3]) > 1 else None

    header_idx = None
    for i, row in enumerate(rows[:20]):
        if row and row[0] == "Дата":
            header_idx = i
            break
    if header_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось найти заголовок таблицы операций в файле",
        )

    data_start = header_idx + 2  # шапка "Контрагент" занимает две строки

    parsed: list[dict] = []
    occurrences: dict[str, int] = {}
    for row in rows[data_start:]:
        if not row or row[0] is None:
            continue

        operation_date = _parse_ru_date(row[0])
        document_number = row[1] if len(row) > 1 else None
        debit = row[2] if len(row) > 2 else None
        credit = row[3] if len(row) > 3 else None
        counterparty_name = row[4] if len(row) > 4 else None
        counterparty_inn = row[5] if len(row) > 5 else None
        counterparty_kpp = row[6] if len(row) > 6 else None
        counterparty_account = row[7] if len(row) > 7 else None
        counterparty_bank_name = row[9] if len(row) > 9 else None
        payment_purpose = row[10] if len(row) > 10 else None

        if debit:
            direction = "DEBIT"
            amount = float(debit)
            payee_name, payee_inn, payee_kpp = counterparty_name, counterparty_inn, counterparty_kpp
            payee_account, payee_bank_name = counterparty_account, counterparty_bank_name
            payer_name, payer_inn, payer_kpp = owner_name, owner_inn, None
        elif credit:
            direction = "CREDIT"
            amount = float(credit)
            payer_name, payer_inn, payer_kpp = counterparty_name, counterparty_inn, counterparty_kpp
            # The owner's own KPP / bank name aren't in this statement format. Assign them
            # explicitly: relying on the previous loop iteration leaked a stale value into this
            # row, and crashed outright when the very first operation was a credit.
            payee_name, payee_inn, payee_kpp, payee_bank_name = owner_name, owner_inn, None, None
            payee_account = account_number
        else:
            continue

        base = build_alfabank_external_id(account_number, document_number, operation_date, direction, amount, payment_purpose, 0)
        base = base[: base.rindex("#")]
        occurrences[base] = occurrences.get(base, 0) + 1
        external_id = f"{base}#{occurrences[base]}"
        if len(external_id) > 100:  # extract_items.external_id is VARCHAR(100)
            external_id = f"{account_number}:{hashlib.sha1(base.encode()).hexdigest()}#{occurrences[base]}"

        parsed.append(
            {
                "operation_date": operation_date,
                "amount": amount,
                "direction": direction,
                "payment_purpose": payment_purpose,
                "payee_inn": payee_inn,
                "payee_kpp": payee_kpp,
                "payee_name": payee_name,
                "payer_inn": payer_inn,
                "payer_kpp": payer_kpp,
                "payer_name": payer_name,
                "payee_bank_name": payee_bank_name,
                "payee_account": payee_account,
                "external_id": external_id,
            }
        )

    return parsed, account_number


def parse_bank_excel(bank_type: str, file_bytes: bytes) -> tuple[list[dict], str | None]:
    """Returns (rows, account_number_detected_in_file). Each row has the same shape as a
    parsed Sberbank statement transaction (see ExtractItemService._fetch_and_store_one_day):
    operation_date, amount, direction, payment_purpose, payee_inn, payee_kpp, payee_name,
    payer_inn, payer_kpp, payer_name, payee_bank_name, payee_account.
    """
    if bank_type == "alfabank":
        return _parse_alfabank_excel(file_bytes)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            f"Разбор Excel-выписки для bank_type={bank_type} пока не реализован "
            "(сейчас поддержан только alfabank). Пришлите пример файла, чтобы добавить парсер."
        ),
    )

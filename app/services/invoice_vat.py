"""НДС в счетах 2026 года: ставка бывает только 0, 5, 7, 10 или 22 % (20 % давно нет).

Mistral иногда возвращает устаревшую ставку (20, 18) или путает её, поэтому ставку сверяют с суммой НДС и общей суммой счёта.
"""
VAT_RATES_2026 = (0, 5, 7, 10, 22)
_TOLERANCE = 1.0  # рубль: округление построчно в счетах даёт расхождения копеек


def _fits(rate: int, vat_amount: float, total: float) -> bool:
    if rate == 0:
        return vat_amount == 0
    included = total * rate / (100 + rate)  # НДС внутри общей суммы
    on_top = total * rate / 100             # общая сумма указана без НДС
    return min(abs(included - vat_amount), abs(on_top - vat_amount)) <= max(_TOLERANCE, total * 0.0005)


def normalize_vat_rate(rate: int | None, vat_amount: float | None, total_amount: float | None) -> int | None:
    """Допустимая ставка или None. Подтверждённая суммами ставка важнее названной моделью."""
    has_amounts = vat_amount is not None and vat_amount > 0 and total_amount is not None and total_amount > 0
    if has_amounts:
        if rate in VAT_RATES_2026 and rate != 0 and _fits(rate, vat_amount, total_amount):
            return rate
        matches = [r for r in VAT_RATES_2026 if r and _fits(r, vat_amount, total_amount)]
        if len(matches) == 1:
            return matches[0]
        if matches:  # 5/7 и т.п. могут совпасть в допуске: берём ближайшую к названной
            return min(matches, key=lambda r: abs(r - (rate or 0)))
    if rate in VAT_RATES_2026:
        return rate
    return None

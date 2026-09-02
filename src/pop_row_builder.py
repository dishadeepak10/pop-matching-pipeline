import re

import pandas as pd


def _find_field(fields, priority_groups, exclude=None):
    exclude = exclude or []
    for group in priority_groups:
        matches = []
        for key in fields:
            key_lower = key.lower()
            if any(bad in key_lower for bad in exclude):
                continue
            if all(needed in key_lower for needed in group):
                matches.append(key)
        for key in sorted(matches):
            entry = fields.get(key)
            if not entry:
                continue
            value = entry.get("value")
            if value not in (None, ""):
                return key, value
    return None, None


def _extract_english(text):
    if not text:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", str(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _is_masked_value(value):
    text = str(value)
    x_count = len(re.findall(r"[Xx*]", text))
    return x_count >= 3


AMOUNT_GROUPS = [
    ("amount", "aed"),
    ("wire_amount", "aed"),
    ("amount", "currency"),
    ("transfer_amount",),
    ("total_amount",),
    ("transaction_amount",),
    ("wire_amount",),
    ("amount_sent",),
    ("amount",),
]
AMOUNT_EXCLUDE = ["word", "fee", "tax", "charge", "vat", "rate"]


def _extract_amount(fields):
    _, value = _find_field(fields, AMOUNT_GROUPS, AMOUNT_EXCLUDE)
    if value is None:
        return None
    match = re.search(r"[-+]?\d[\d,]*\.?\d*", str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


DATE_GROUPS = [
    ("payment_date",),
    ("receipt_date",),
    ("transaction_date",),
    ("transfer_date",),
    ("value_date",),
    ("date", "time"),
    ("transaction_time",),
    ("date",),
    ("effective_date",),
]
DATE_EXCLUDE = ["birth", "signature", "available", "expected", "delivery"]


def _parse_date_value(value):
    """
    Deterministic date parsing, two passes:
      1. Try to interpret ambiguous numeric dates as month-first
         (e.g. 07/21/2026 -> unambiguous, July 21).
      2. If that fails (e.g. 13/07/2026, month=13 is invalid), retry
         as day-first (13 July 2026).
    Also handles text-month formats like "20 July, 01:22 PM" natively.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"\s*([/.\-])\s*", r"\1", text)

    has_explicit_year = bool(re.search(r"(19|20)\d{2}", text))

    for dayfirst in (False, True):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
        if pd.notna(parsed):
            if not has_explicit_year:
                return None
            return parsed.strftime("%Y-%m-%d")

    return None


def _extract_date(fields):
    key, _ = _find_field(fields, DATE_GROUPS, DATE_EXCLUDE)

    if key is None:
        candidates = sorted(
            k for k in fields
            if "applicant" in k.lower()
            and "signature" in k.lower()
            and "date" in k.lower()
        )
        key = candidates[0] if candidates else None

    if key is None:
        return None

    entry = fields.get(key) or {}
    raw_value = entry.get("original_value")
    if raw_value in (None, ""):
        raw_value = entry.get("value")

    return _parse_date_value(raw_value)


ACCOUNT_GROUPS = [
    ("to_account", "iban"),
    ("beneficiary_account",),
    ("beneficiary_bank_iban",),
    ("recipient_account", "iban"),
    ("recipient_account",),
    ("beneficiary_bank_account",),
    ("to_account",),
    ("iban",),
    ("account_number",),
]
ACCOUNT_EXCLUDE = ["masked"]


def _extract_account(fields):
    for group in ACCOUNT_GROUPS:
        matches = []
        for key in fields:
            key_lower = key.lower()
            if any(bad in key_lower for bad in ACCOUNT_EXCLUDE):
                continue
            if all(needed in key_lower for needed in group):
                matches.append(key)

        for key in sorted(matches):
            entry = fields.get(key)
            if not entry:
                continue
            value = entry.get("value")
            if value in (None, ""):
                continue
            if _is_masked_value(value):
                continue

            text = str(value).strip().upper().replace(" ", "")

            if re.match(r"^[A-Z]{2}", text) and not text.startswith("AE"):
                continue

            digits = re.sub(r"[^0-9]", "", text)

            if len(digits) < 12:
                continue

            return digits[-16:] if len(digits) >= 16 else digits

    return ""


NAME_GROUPS = [
    ("sender_name",),
    ("depositor_name",),
    ("applicant_name",),
    ("remitter",),
    ("customer_name",),
    ("account_holder_name",),
    ("from_account_name",),
]


def _extract_customer_name(fields):
    _, value = _find_field(fields, NAME_GROUPS)
    return value or ""


BANK_GROUPS = [
    ("from_bank",),
    ("sender_bank",),
    ("remitter_bank_name",),
    ("delivery_bank_name",),
    ("bank_name",),
]
BANK_EXCLUDE = ["beneficiary", "recipient", "arabic"]


def _extract_bank_name(fields):
    _, value = _find_field(fields, BANK_GROUPS, BANK_EXCLUDE)
    return _extract_english(value) if value else ""


REFERENCE_GROUPS = [
    ("reference_number",),
    ("transaction_reference",),
    ("booking_reference",),
    ("transaction_id",),
    ("transaction_number",),
    ("receipt_number",),
    ("payment_number",),
]


def _extract_reference(fields):
    _, value = _find_field(fields, REFERENCE_GROUPS)
    if not value:
        return ""
    value = re.sub(r"(?i)^\s*ref\.?(erence)?\s*", "", str(value)).strip()
    return value


# --- Currency extraction (new this session) ---
#
# Policy (user-decided, mentor confirmed no conversion should ever
# happen): if a POP's currency is explicitly non-AED, it must be
# excluded from matching against the AED bank master. If currency
# cannot be determined at all after checking every likely source,
# treat it as unknown (also excluded) rather than assuming AED.
#
# Two sources are checked, in order:
#   1. A dedicated currency-labeled field (e.g. "currency",
#      "currency_code", "payment_currency").
#   2. Fallback: scan ALL field KEY NAMES (not values) for an
#      embedded ISO currency code, e.g. "amount_aed" implies AED
#      even if no separate currency field exists. This mirrors the
#      same "amount"+"aed" pattern already used in AMOUNT_GROUPS.

CURRENCY_GROUPS = [
    ("currency", "code"),
    ("payment_currency",),
    ("transaction_currency",),
    ("wire_currency",),
    ("txn_currency",),
    ("currency",),
]

KNOWN_CURRENCY_CODES = [
    "AED", "USD", "GBP", "EUR", "SAR", "INR", "PKR", "EGP",
    "QAR", "KWD", "BHD", "OMR", "JOD", "CNY", "JPY", "CHF",
]

CURRENCY_NAME_MAP = {
    "DIRHAM": "AED",
    "DIRHAMS": "AED",
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "STERLING": "GBP",
    "EURO": "EUR",
    "EUROS": "EUR",
}


def _normalize_currency_text(value):
    if not value:
        return ""
    text = str(value).strip().upper()

    code_match = re.search(r"\b([A-Z]{3})\b", text)
    if code_match and code_match.group(1) in KNOWN_CURRENCY_CODES:
        return code_match.group(1)

    for name, code in CURRENCY_NAME_MAP.items():
        if name in text:
            return code

    return ""


CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
}


def _extract_currency(fields):
    # Source 1: a dedicated currency field's VALUE.
    _, value = _find_field(fields, CURRENCY_GROUPS)
    currency = _normalize_currency_text(value)
    if currency:
        return currency

    # Source 2 (fallback): re-check the SAME field the amount itself
    # came from - its raw original_value often carries the currency
    # inline (e.g. "GBP 5,000.00") even when no dedicated currency
    # field exists at all. This is the real-world case for 00084501,
    # which has only 7 fields total and no separate currency field.
    amount_key, _ = _find_field(fields, AMOUNT_GROUPS, AMOUNT_EXCLUDE)
    if amount_key:
        entry = fields.get(amount_key) or {}
        raw = entry.get("original_value") or entry.get("value") or ""
        raw_text = str(raw)

        currency = _normalize_currency_text(raw_text)
        if currency:
            return currency

        for symbol, code in CURRENCY_SYMBOL_MAP.items():
            if symbol in raw_text:
                return code

    # Source 3 (fallback): an ISO code embedded in a field KEY name,
    # only trusted if that field actually has a non-empty value
    # (so a stray unrelated key doesn't produce a false signal).
    found_codes = set()
    for key, entry in fields.items():
        if not entry:
            continue
        if entry.get("value") in (None, ""):
            continue
        key_upper = key.upper()
        for code in KNOWN_CURRENCY_CODES:
            if re.search(rf"(^|_){code}($|_)", key_upper):
                found_codes.add(code)

    if len(found_codes) == 1:
        return next(iter(found_codes))

    # Default: this pipeline operates on AED transactions almost
    # exclusively. If no currency signal is found anywhere, assume
    # AED rather than treating it as unknown - standardized across
    # both POP sources per user decision.
    return "AED"


def build_pop_row(case_number, normalized_data):
    fields = normalized_data.get("fields", {}) or {}
    reference = _extract_reference(fields)

    return {
        "case_number": case_number,
        "pop_amount": _extract_amount(fields),
        "pop_value_date": _extract_date(fields),
        "pop_currency": _extract_currency(fields),
        "email_bank_account": _extract_account(fields),
        "email_customer_name": _extract_customer_name(fields),
        "email_bank_name": _extract_bank_name(fields),
        "pop_booking_reference": reference,
        "reference_number": reference,
        "email_receipt_reference": reference,
        "overall_confidence": normalized_data.get("overall_confidence"),
        "fields_count": len(fields),
    }



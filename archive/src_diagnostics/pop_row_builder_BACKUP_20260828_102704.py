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
# CHANGED PRIOR SESSION: "figure" removed from this list. Evidence from
# cases 84772 and 84851 showed real GPT-extracted amount fields are
# literally named "amount_in_figures" / "amount_in_figure" - excluding
# anything containing "figure" was blocking the correct field, not just
# the intended target (amount_in_words). "word" alone correctly filters
# the spelled-out amount field; "figure" was never needed for that and
# was actively wrong.
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


# CHANGED THIS SESSION (two fixes, both evidence-based, case 84379):
#
#   1. ARCHITECTURE FIX: dates now parse from each field's RAW extracted
#      text (original_value), not GPT's own pre-normalized "value". GPT
#      extraction in src/main.py already normalizes dates before we ever
#      see them (e.g. value="2026-07-20", original_value="20-07-2026") -
#      parsing "value" meant the LLM was making the actual standardization
#      decision, and our deterministic parser was just re-confirming it.
#      Per mentor's explicit instruction (extract raw, then standardize
#      deterministically - never LLM as the primary mechanism), we now
#      parse original_value ourselves. This is the field-lookup source
#      change; the two-pass deterministic pandas parsing logic itself
#      (below, in _parse_date_value) is unchanged from before.
#
#   2. Case 84379's only date field is "applicant_signature_date" -
#      DATE_EXCLUDE blocks any key containing "signature" outright, so
#      this case fell through to None even though a real date exists on
#      the document. A blanket "signature" exclusion is still correct in
#      general (e.g. a branch manager's or bank official's signature date
#      is not a reliable proxy for the transaction date), so instead of
#      loosening the exclude list broadly, added a narrow last-resort
#      fallback that only allows a key matching "applicant" + "signature"
#      + "date" together - the applicant's own signing date specifically,
#      nothing broader.
#
# (Prior session's fixes, still in place below: effective_date as a
# low-priority fallback rather than an exclusion; explicit _time groups;
# two-pass dayfirst pandas parsing for text-month/ambiguous dates; no
# fabricated year when the raw text has no 4-digit year.)
DATE_GROUPS = [
    ("payment_date",),
    ("receipt_date",),
    ("transaction_date",),
    ("transfer_date",),
    ("value_date",),
    ("date", "time"),
    ("transaction_time",),
    ("date",),
    ("effective_date",),  # last resort: sometimes a future value date,
                           # but sometimes the only date on the document
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

    SAFETY CHECK: testing found pandas silently defaulting to year 0001
    when the source text had no year at all (e.g. "20 July, 01:22 PM").
    If the raw text does not contain an actual 4-digit year, we do NOT
    trust any year the parser fills in - we return None instead, so
    the case surfaces for manual review rather than silently carrying
    a fabricated year into matching. No LLM involved - pure
    deterministic parsing.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

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
        # Narrow last resort: the applicant's OWN signature date only -
        # not any signature date. See comment above DATE_GROUPS.
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
    # Use the RAW extracted text (original_value), not GPT's own
    # normalization (value) - see architecture-fix comment above.
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


def build_pop_row(case_number, normalized_data):
    fields = normalized_data.get("fields", {}) or {}
    reference = _extract_reference(fields)

    return {
        "case_number": case_number,
        "pop_amount": _extract_amount(fields),
        "pop_value_date": _extract_date(fields),
        "email_bank_account": _extract_account(fields),
        "email_customer_name": _extract_customer_name(fields),
        "email_bank_name": _extract_bank_name(fields),
        "pop_booking_reference": reference,
        "reference_number": reference,
        "email_receipt_reference": reference,
        "overall_confidence": normalized_data.get("overall_confidence"),
    }

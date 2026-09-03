"""
Parses POP data from Salesforce case-notification emails
(_POP_EmailsLog.xlsx), for cases where no raw POP document/image
is available - only the email body containing a structured
RECEIPT INFORMATION block.

IMPORTANT: the email body is word-wrapped plain text, so line
breaks can fall in the middle of a label (e.g. "Bank\nAccount
Number:"). All whitespace/newlines are flattened to single spaces
before label extraction to handle this.

Outputs the SAME row shape as pop_row_builder.build_pop_row(),
so matching.py and storage.py never need to know which source
a row came from.
"""

import re
import pandas as pd
# --- Currency extraction ---
#
# Same policy/approach as pop_row_builder.py's _extract_currency:
# no conversion is ever performed; a POP's currency must be either
# confirmed AED (proceeds normally) or confirmed non-AED / unknown
# (excluded from matching by matching.py's gate). Constants are
# shared from config.py (Phase 3 cleanup - completed).

from config import KNOWN_CURRENCY_CODES, CURRENCY_NAME_MAP, CURRENCY_SYMBOL_MAP


def _extract_field(flat_body, label, stop_labels):
    stop_pattern = "|".join(re.escape(s) for s in stop_labels)
    pattern = rf"{re.escape(label)}\s*(.*?)(?=(?:{stop_pattern})|$)"
    match = re.search(pattern, flat_body)
    if not match:
        return ""
    return match.group(1).strip()


RECEIPT_LABELS = [
    "Receipt Acknowledgement:",
    "Receipt Amount:",
    "Bank Name:",
    "Payment Method:",
    "Customer Last Name:",
    "Bank Account Number:",
    "Remarks:",
]



def _extract_currency_from_text(text):
    if not text:
        return ""
    upper = str(text).strip().upper()

    code_match = re.search(r"\b([A-Z]{3})\b", upper)
    if code_match and code_match.group(1) in KNOWN_CURRENCY_CODES:
        return code_match.group(1)

    for name, code in CURRENCY_NAME_MAP.items():
        if name in upper:
            return code

    for symbol, code in CURRENCY_SYMBOL_MAP.items():
        if symbol in text:
            return code

    return ""


def parse_email_row(case_number, email_body, created_date):
    body = email_body or ""
    flat = re.sub(r"\s+", " ", body)

    amount_text = _extract_field(flat, "Receipt Amount:", RECEIPT_LABELS)
    amount = None
    match = re.search(r"[\d,]+\.?\d*", amount_text)
    if match:
        try:
            amount = float(match.group(0).replace(",", ""))
        except ValueError:
            pass

        # Default to AED when not stated - standardized across both POP
    # sources per user decision (this email source never states
    # currency at all; the underlying transactions are UAE-domestic).
    currency = _extract_currency_from_text(amount_text) or "AED"

    bank_name = _extract_field(flat, "Bank Name:", RECEIPT_LABELS)
    payment_method = _extract_field(flat, "Payment Method:", RECEIPT_LABELS)
    customer_name = _extract_field(flat, "Customer Last Name:", RECEIPT_LABELS)
    account = _extract_field(flat, "Bank Account Number:", RECEIPT_LABELS)
    account = re.sub(r"[^0-9]", "", account)

    reference = _extract_field(flat, "Receipt Acknowledgement:", RECEIPT_LABELS)

    pop_value_date = None
    if created_date is not None:
        try:
            pop_value_date = pd.Timestamp(created_date).strftime("%Y-%m-%d")
        except Exception:
            pass
    return {
        "case_number": str(case_number),
        "pop_amount": amount,
        "pop_value_date": pop_value_date,
        "pop_currency": currency,
        "email_bank_account": account,
        "email_customer_name": customer_name,
        "email_bank_name": bank_name,
        "pop_booking_reference": reference,
        "reference_number": reference,
        "email_receipt_reference": reference,
        "email_payment_method": payment_method,
        "overall_confidence": None,
        "fields_count": sum(1 for v in [amount, bank_name, payment_method, customer_name, account, reference] if v),
        "email_received_date": pop_value_date,
    }


def load_email_log_rows(excel_path, sheet_name="POP_attachments"):
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    rows = []
    for _, r in df.iterrows():
        case_number = r.get("Case Number")
        if pd.isna(case_number):
            continue

        row = parse_email_row(
            case_number,
            r.get("EmailBody"),
            r.get("Email Received Date") or r.get("Created Date"),
        )
        rows.append(row)

    return rows


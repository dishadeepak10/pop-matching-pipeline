from __future__ import annotations

import re
import math
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(r"D:\Disha_Workarea\pop_process")

POP_INPUT_DIR = PROJECT_DIR / "data" / "input"
BANK_INPUT_DIR = PROJECT_DIR / "testing_bank_statements"

OUTPUT_DIR = PROJECT_DIR / "data" / "output" / "v9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MATCH_RESULTS = OUTPUT_DIR / "match_results_v9.xlsx"
CANDIDATE_AUDIT = OUTPUT_DIR / "candidate_audit_v9.xlsx"
SCHEMA_REPORT = OUTPUT_DIR / "schema_report_v9.xlsx"
DIAGNOSTIC_REPORT = OUTPUT_DIR / "diagnostic_report_v9.txt"


# Matching configuration
EXACT_AMOUNT_TOLERANCE = 0.01
NEAR_AMOUNT_TOLERANCE = 1.00

DATE_WINDOW_DAYS = 7

MIN_MATCH_SCORE = 70
MIN_SCORE_GAP = 15

MAX_CANDIDATES_PER_POP = 100


# ============================================================
# CANONICAL SCHEMAS
# ============================================================

POP_COLUMNS = [
    "case_number",
    "pop_amount",
    "pop_date",
    "pop_reference",
    "pop_customer_reference",
    "pop_account",
    "pop_customer_name",
    "pop_bank_name",
    "pop_payment_method",
    "pop_source_file",
]

BANK_COLUMNS = [
    "bank_row_index",
    "bank_date",
    "bank_value_date",
    "bank_description",
    "bank_reference",
    "bank_customer_reference",
    "bank_account",
    "bank_transaction_type",
    "bank_debit_amount",
    "bank_credit_amount",
    "bank_balance",
    "bank_amount",
    "bank_name",
    "source_file",
]


# ============================================================
# GENERAL UTILITIES
# ============================================================

def clean_text(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None

    value = str(value)
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value).strip()

    if not value:
        return None

    return value


def normalize_text(value: Any) -> str:
    value = clean_text(value)

    if not value:
        return ""

    value = value.upper()

    value = re.sub(r"[^A-Z0-9]+", "", value)

    return value


def normalize_column_name(value: Any) -> str:
    value = clean_text(value)

    if not value:
        return ""

    value = unicodedata.normalize("NFKC", value).upper()

    value = re.sub(r"[^A-Z0-9]+", "_", value)

    return value.strip("_")


def safe_float(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None

    if isinstance(value, (int, float, np.integer, np.floating)):
        if math.isnan(float(value)):
            return None
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("AED", "")
    text = text.replace("USD", "")
    text = text.replace("$", "")
    text = text.replace("€", "")
    text = text.replace("£", "")

    text = text.strip()

    negative = False

    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    try:
        number = float(text)

        if negative:
            number = -number

        return number

    except Exception:
        return None


def normalize_amount_series(series: pd.Series) -> pd.Series:
    return series.map(safe_float).astype("Float64")


def normalize_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


# ============================================================
# FILE DISCOVERY
# ============================================================

def discover_files(root: Path) -> List[Path]:
    extensions = {".xls", ".xlsx", ".xlsm"}

    files = []

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)

    return sorted(files)


# ============================================================
# WORKBOOK INSPECTION
# ============================================================

@dataclass
class SheetInspection:
    file: Path
    sheet: str
    rows: int
    columns: int
    header_row: Optional[int]
    columns_found: List[str]
    role: str = "UNKNOWN"
    role_score: float = 0.0
    signals: List[str] = field(default_factory=list)


def read_sheet_preview(path: Path, sheet_name: Any) -> pd.DataFrame:
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=None,
            nrows=50,
            engine="openpyxl",
        )

    if suffix == ".xls":
        return pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=None,
            nrows=50,
            engine="xlrd",
        )

    raise ValueError(f"Unsupported file: {path}")


def get_sheet_names(path: Path) -> List[str]:
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xlsm"}:
        xl = pd.ExcelFile(path, engine="openpyxl")
        return xl.sheet_names

    if suffix == ".xls":
        xl = pd.ExcelFile(path, engine="xlrd")
        return xl.sheet_names

    return []


# ============================================================
# HEADER DETECTION
# ============================================================

HEADER_TERMS = {
    "DATE",
    "VALUE DATE",
    "TRANSACTION DATE",
    "DESCRIPTION",
    "REFERENCE",
    "REFERENCE NO",
    "CUSTOMER REFERENCE",
    "CUSTOMER REFERENCE NO",
    "DEBIT",
    "CREDIT",
    "AMOUNT",
    "BALANCE",
    "CASE NUMBER",
    "PAYMENT",
    "PAYMENT AMOUNT",
    "ACCOUNT",
    "CUSTOMER",
    "BANK",
}


def row_header_score(row: pd.Series) -> int:
    values = []

    for value in row.tolist():
        value = clean_text(value)

        if value:
            values.append(value.upper())

    score = 0

    for value in values:
        for term in HEADER_TERMS:
            if value == term or term in value:
                score += 1

    return score


def detect_header_row(preview: pd.DataFrame) -> Optional[int]:
    best_row = None
    best_score = 0

    for idx in range(len(preview)):
        score = row_header_score(preview.iloc[idx])

        if score > best_score:
            best_score = score
            best_row = idx

    return best_row if best_score >= 2 else None


# ============================================================
# COLUMN ROLE DETECTION
# ============================================================

ROLE_TERMS = {

    "date": {
        "DATE",
        "TRANSACTION_DATE",
        "POSTING_DATE",
        "TRANS_DATE",
    },

    "value_date": {
        "VALUE_DATE",
        "VALUE_DT",
        "VALUE",
    },

    "reference": {
        "REFERENCE",
        "REFERENCE_NO",
        "BANK_REFERENCE",
        "BANK_REFERENCE_NO",
        "BANK_REF",
        "REF",
    },

    "customer_reference": {
        "CUSTOMER_REFERENCE",
        "CUSTOMER_REFERENCE_NO",
        "CUST_REF",
        "CUSTOMER_REF",
    },

    "account": {
        "ACCOUNT",
        "ACCOUNT_NO",
        "ACCOUNT_NUMBER",
        "IBAN",
    },

    "customer": {
        "CUSTOMER",
        "CUSTOMER_NAME",
        "ACCOUNT_NAME",
        "NAME",
    },

    "bank": {
        "BANK",
        "BANK_NAME",
    },

    "payment_method": {
        "PAYMENT_METHOD",
        "METHOD",
        "PAYMENT_TYPE",
    },

    "description": {
        "DESCRIPTION",
        "NARRATION",
        "DETAILS",
        "REMARKS",
        "PARTICULARS",
    },

    "transaction_type": {
        "TRANSACTION_TYPE",
        "TYPE",
        "TXN_TYPE",
    },

    "debit": {
        "DEBIT",
        "DEBIT_AMOUNT",
        "WITHDRAWAL",
        "DR",
    },

    "credit": {
        "CREDIT",
        "CREDIT_AMOUNT",
        "DEPOSIT",
        "CR",
    },

    "balance": {
        "BALANCE",
        "RUNNING_BALANCE",
        "RUNNING_BAL",
        "CLOSING_BALANCE",
    },

    "amount": {
        "AMOUNT",
        "PAYMENT_AMOUNT",
        "TRANSACTION_AMOUNT",
        "RECEIPT_AMOUNT",
        "TOTAL_AMOUNT",
    },

    "case_number": {
        "CASE_NUMBER",
        "CASE_NO",
        "CASE_ID",
        "CASE",
    },
}


def column_name_matches_role(column: str, role: str) -> bool:
    normalized = normalize_column_name(column)

    for term in ROLE_TERMS.get(role, set()):
        if normalized == term:
            return True

        if normalized.endswith("_" + term):
            return True

    return False


def numeric_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0

    converted = series.map(safe_float)

    return float(converted.notna().mean())


def non_null_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0

    return float(series.notna().mean())


def detect_role_candidates(df: pd.DataFrame) -> Dict[str, List[Tuple[str, float, str]]]:
    result = {}

    for role in ROLE_TERMS:
        candidates = []

        for column in df.columns:

            score = 0.0
            reasons = []

            normalized = normalize_column_name(column)

            if column_name_matches_role(column, role):
                score += 50
                reasons.append("column_name")

            nr = non_null_ratio(df[column])

            if nr >= 0.5:
                score += 5
                reasons.append("non_null")

            if role in {
                "amount",
                "debit",
                "credit",
                "balance",
            }:
                numeric = numeric_ratio(df[column])

                if numeric >= 0.90:
                    score += 35
                    reasons.append("high_numeric_ratio")
                elif numeric >= 0.70:
                    score += 20
                    reasons.append("numeric_ratio")
                elif numeric < 0.20:
                    score -= 40
                    reasons.append("not_numeric")

            if role in {"date", "value_date"}:
                parsed = pd.to_datetime(
                    df[column],
                    errors="coerce",
                )

                date_ratio = float(parsed.notna().mean())

                if date_ratio >= 0.80:
                    score += 30
                    reasons.append("date_values")
                elif date_ratio >= 0.50:
                    score += 15
                    reasons.append("partial_date_values")

            if role == "amount":
                # CRITICAL SAFETY RULE:
                # A date-like column can NEVER become amount.
                parsed_dates = pd.to_datetime(
                    df[column],
                    errors="coerce",
                )

                date_ratio = float(parsed_dates.notna().mean())

                if date_ratio >= 0.80:
                    score = -100
                    reasons = ["date_like_column_rejected"]

            candidates.append(
                (
                    column,
                    score,
                    ",".join(reasons),
                )
            )

        candidates.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        result[role] = candidates

    return result


# ============================================================
# SHEET CLASSIFICATION
# ============================================================

BANK_SIGNALS = {
    "debit": 20,
    "credit": 20,
    "balance": 20,
    "date": 15,
    "value_date": 10,
    "transaction_type": 10,
    "reference": 5,
    "customer_reference": 5,
    "description": 5,
}


POP_SIGNALS = {
    "case_number": 25,
    "amount": 25,
    "payment_method": 15,
    "customer": 10,
    "customer_reference": 10,
    "account": 10,
    "reference": 10,
    "date": 5,
}


def classify_sheet(
    df: pd.DataFrame,
) -> Tuple[str, float, List[str]]:

    candidates = detect_role_candidates(df)

    bank_score = 0.0
    pop_score = 0.0

    bank_signals = []
    pop_signals = []

    for role, weight in BANK_SIGNALS.items():

        if candidates.get(role):
            column, score, reason = candidates[role][0]

            if score > 40:
                bank_score += weight
                bank_signals.append(
                    f"{role}={column}"
                )

    for role, weight in POP_SIGNALS.items():

        if candidates.get(role):
            column, score, reason = candidates[role][0]

            if score > 40:
                pop_score += weight
                pop_signals.append(
                    f"{role}={column}"
                )

    # Strong bank identity
    if (
        bank_score >= 45
        and len(bank_signals) >= 3
    ):
        return (
            "BANK",
            bank_score,
            bank_signals,
        )

    # Strong POP identity
    if (
        pop_score >= 40
        and len(pop_signals) >= 2
    ):
        return (
            "POP",
            pop_score,
            pop_signals,
        )

    return (
        "UNKNOWN",
        max(bank_score, pop_score),
        bank_signals + pop_signals,
    )


# ============================================================
# INSPECT ALL FILES
# ============================================================

def inspect_files(
    files: List[Path],
) -> List[SheetInspection]:

    inspections = []

    for path in files:

        try:
            sheets = get_sheet_names(path)

        except Exception as exc:
            print(
                f"[ERROR] Cannot inspect {path.name}: {exc}"
            )
            continue

        for sheet in sheets:

            try:
                preview = read_sheet_preview(
                    path,
                    sheet,
                )

                header_row = detect_header_row(
                    preview
                )

                if header_row is not None:

                    header_values = [
                        clean_text(v)
                        for v in preview.iloc[
                            header_row
                        ].tolist()
                    ]

                    header_values = [
                        v
                        for v in header_values
                        if v
                    ]

                else:
                    header_values = []

                role = "UNKNOWN"
                role_score = 0
                signals = []

                if header_row is not None:

                    try:
                        data = preview.iloc[
                            header_row + 1 :
                        ].copy()

                        data.columns = [
                            clean_text(v) or f"COL_{i}"
                            for i, v in enumerate(
                                preview.iloc[
                                    header_row
                                ].tolist()
                            )
                        ]

                        role, role_score, signals = classify_sheet(
                            data
                        )

                    except Exception as exc:
                        signals = [
                            f"classification_error={exc}"
                        ]

                inspections.append(
                    SheetInspection(
                        file=path,
                        sheet=sheet,
                        rows=len(preview),
                        columns=len(preview.columns),
                        header_row=header_row,
                        columns_found=header_values,
                        role=role,
                        role_score=role_score,
                        signals=signals,
                    )
                )

            except Exception as exc:

                print(
                    f"[ERROR] {path.name} / {sheet}: {exc}"
                )

    return inspections


# ============================================================
# PRINT SCHEMA REPORT
# ============================================================

def print_schema_report(
    inspections: List[SheetInspection],
):

    print("\n")
    print("=" * 120)
    print("V9 WORKBOOK / SHEET INSPECTION")
    print("=" * 120)

    for item in inspections:

        print("\n" + "-" * 120)

        print(
            f"FILE        : {item.file.name}"
        )

        print(
            f"SHEET       : {item.sheet}"
        )

        print(
            f"HEADER ROW  : {item.header_row}"
        )

        print(
            f"ROLE        : {item.role}"
        )

        print(
            f"ROLE SCORE  : {item.role_score:.1f}"
        )

        print(
            f"COLUMNS     : {item.columns_found}"
        )

        print(
            f"SIGNALS     : {item.signals}"
        )


# ============================================================
# LOAD SELECTED SHEET
# ============================================================

def load_sheet_with_header(
    path: Path,
    sheet: str,
    header_row: int,
) -> pd.DataFrame:

    suffix = path.suffix.lower()

    engine = (
        "openpyxl"
        if suffix in {".xlsx", ".xlsm"}
        else "xlrd"
    )

    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=header_row,
        engine=engine,
    )

    df.columns = [
        clean_text(c) or f"COL_{i}"
        for i, c in enumerate(df.columns)
    ]

    return df


# ============================================================
# POP SCHEMA VALIDATION
# ============================================================

@dataclass
class SchemaDecision:
    valid: bool
    reason: str
    roles: Dict[str, Optional[str]]
    diagnostics: Dict[str, Any]


def choose_best_column(
    candidates: Dict[str, List[Tuple[str, float, str]]],
    role: str,
    minimum_score: float = 40,
) -> Optional[str]:

    items = candidates.get(role, [])

    if not items:
        return None

    column, score, reason = items[0]

    if score < minimum_score:
        return None

    return column


def validate_pop_schema(
    df: pd.DataFrame,
) -> SchemaDecision:

    candidates = detect_role_candidates(df)

    roles = {}

    for role in POP_COLUMNS:
        roles[role] = None

    roles["case_number"] = choose_best_column(
        candidates,
        "case_number",
        40,
    )

    roles["pop_amount"] = choose_best_column(
        candidates,
        "amount",
        60,
    )

    roles["pop_date"] = choose_best_column(
        candidates,
        "date",
        40,
    )

    roles["pop_reference"] = choose_best_column(
        candidates,
        "reference",
        40,
    )

    roles["pop_customer_reference"] = choose_best_column(
        candidates,
        "customer_reference",
        40,
    )

    roles["pop_account"] = choose_best_column(
        candidates,
        "account",
        40,
    )

    roles["pop_customer_name"] = choose_best_column(
        candidates,
        "customer",
        40,
    )

    roles["pop_bank_name"] = choose_best_column(
        candidates,
        "bank",
        40,
    )

    roles["pop_payment_method"] = choose_best_column(
        candidates,
        "payment_method",
        40,
    )

    diagnostics = {
        "amount_candidates": candidates.get(
            "amount",
            [],
        )[:10],
        "case_candidates": candidates.get(
            "case_number",
            [],
        )[:10],
    }

    if roles["pop_amount"] is None:

        return SchemaDecision(
            valid=False,
            reason=(
                "NO_VALID_POP_AMOUNT_COLUMN. "
                "The sheet does not contain a sufficiently "
                "strong numeric transaction amount field."
            ),
            roles=roles,
            diagnostics=diagnostics,
        )

    if roles["case_number"] is None:

        return SchemaDecision(
            valid=False,
            reason=(
                "NO_POP_IDENTIFIER. "
                "No case/transaction identifier could be "
                "reliably detected."
            ),
            roles=roles,
            diagnostics=diagnostics,
        )

    return SchemaDecision(
        valid=True,
        reason="POP schema validated.",
        roles=roles,
        diagnostics=diagnostics,
    )


# ============================================================
# POP NORMALIZATION
# ============================================================

def normalize_pop(
    df: pd.DataFrame,
    decision: SchemaDecision,
    source_file: str,
) -> pd.DataFrame:

    out = pd.DataFrame(index=df.index)

    roles = decision.roles

    for output_column in POP_COLUMNS:
        out[output_column] = pd.NA

    mapping = {
        "case_number": roles.get("case_number"),
        "pop_amount": roles.get("pop_amount"),
        "pop_date": roles.get("pop_date"),
        "pop_reference": roles.get("pop_reference"),
        "pop_customer_reference": roles.get(
            "pop_customer_reference"
        ),
        "pop_account": roles.get("pop_account"),
        "pop_customer_name": roles.get(
            "pop_customer_name"
        ),
        "pop_bank_name": roles.get(
            "pop_bank_name"
        ),
        "pop_payment_method": roles.get(
            "pop_payment_method"
        ),
    }

    for output_column, input_column in mapping.items():

        if input_column is not None:

            out[output_column] = df[
                input_column
            ]

    out["pop_amount"] = normalize_amount_series(
        out["pop_amount"]
    )

    out["pop_date"] = normalize_date_series(
        out["pop_date"]
    )

    for column in [
        "case_number",
        "pop_reference",
        "pop_customer_reference",
        "pop_account",
        "pop_customer_name",
        "pop_bank_name",
        "pop_payment_method",
    ]:
        out[column] = out[column].map(clean_text)

    out["pop_source_file"] = source_file

    return out


# ============================================================
# BANK SCHEMA DETECTION
# ============================================================

def validate_bank_schema(
    df: pd.DataFrame,
) -> SchemaDecision:

    candidates = detect_role_candidates(df)

    roles = {}

    roles["bank_date"] = choose_best_column(
        candidates,
        "date",
        40,
    )

    roles["bank_value_date"] = choose_best_column(
        candidates,
        "value_date",
        40,
    )

    roles["bank_reference"] = choose_best_column(
        candidates,
        "reference",
        40,
    )

    roles["bank_customer_reference"] = choose_best_column(
        candidates,
        "customer_reference",
        40,
    )

    roles["bank_account"] = choose_best_column(
        candidates,
        "account",
        40,
    )

    roles["bank_description"] = choose_best_column(
        candidates,
        "description",
        40,
    )

    roles["bank_transaction_type"] = choose_best_column(
        candidates,
        "transaction_type",
        40,
    )

    roles["bank_debit_amount"] = choose_best_column(
        candidates,
        "debit",
        40,
    )

    roles["bank_credit_amount"] = choose_best_column(
        candidates,
        "credit",
        40,
    )

    roles["bank_balance"] = choose_best_column(
        candidates,
        "balance",
        40,
    )

    diagnostics = {
        "debit_candidates": candidates.get(
            "debit",
            [],
        )[:10],
        "credit_candidates": candidates.get(
            "credit",
            [],
        )[:10],
        "balance_candidates": candidates.get(
            "balance",
            [],
        )[:10],
    }

    has_debit = roles["bank_debit_amount"] is not None
    has_credit = roles["bank_credit_amount"] is not None

    has_amount = (
        choose_best_column(
            candidates,
            "amount",
            60,
        )
        is not None
    )

    if not (has_debit or has_credit or has_amount):

        return SchemaDecision(
            valid=False,
            reason=(
                "NO_VALID_BANK_AMOUNT_STRUCTURE. "
                "No debit, credit, or transaction amount "
                "column was reliably identified."
            ),
            roles=roles,
            diagnostics=diagnostics,
        )

    if roles["bank_date"] is None:

        return SchemaDecision(
            valid=False,
            reason=(
                "NO_BANK_TRANSACTION_DATE. "
                "A transaction date could not be identified."
            ),
            roles=roles,
            diagnostics=diagnostics,
        )

    return SchemaDecision(
        valid=True,
        reason="BANK schema validated.",
        roles=roles,
        diagnostics=diagnostics,
    )


# ============================================================
# BANK NORMALIZATION
# ============================================================

def normalize_bank(
    df: pd.DataFrame,
    decision: SchemaDecision,
    source_file: str,
    bank_name: str,
) -> pd.DataFrame:

    out = pd.DataFrame(index=df.index)

    for column in BANK_COLUMNS:
        out[column] = pd.NA

    roles = decision.roles

    mapping = {
        "bank_date": roles.get("bank_date"),
        "bank_value_date": roles.get("bank_value_date"),
        "bank_description": roles.get(
            "bank_description"
        ),
        "bank_reference": roles.get(
            "bank_reference"
        ),
        "bank_customer_reference": roles.get(
            "bank_customer_reference"
        ),
        "bank_account": roles.get(
            "bank_account"
        ),
        "bank_transaction_type": roles.get(
            "bank_transaction_type"
        ),
        "bank_debit_amount": roles.get(
            "bank_debit_amount"
        ),
        "bank_credit_amount": roles.get(
            "bank_credit_amount"
        ),
        "bank_balance": roles.get(
            "bank_balance"
        ),
    }

    for output_column, input_column in mapping.items():

        if input_column is not None:
            out[output_column] = df[
                input_column
            ]

    out["bank_date"] = normalize_date_series(
        out["bank_date"]
    )

    out["bank_value_date"] = normalize_date_series(
        out["bank_value_date"]
    )

    for column in [
        "bank_debit_amount",
        "bank_credit_amount",
        "bank_balance",
    ]:
        out[column] = normalize_amount_series(
            out[column]
        )

    # --------------------------------------------------------
    # SAFE BANK AMOUNT
    # --------------------------------------------------------

    debit = out["bank_debit_amount"]
    credit = out["bank_credit_amount"]

    debit_present = debit.notna()
    credit_present = credit.notna()

    out["bank_amount"] = pd.Series(
        pd.NA,
        index=out.index,
        dtype="Float64",
    )

    # Only one side populated -> safe
    only_debit = debit_present & ~credit_present
    only_credit = credit_present & ~debit_present

    out.loc[
        only_debit,
        "bank_amount",
    ] = debit.loc[only_debit]

    out.loc[
        only_credit,
        "bank_amount",
    ] = credit.loc[only_credit]

    # Both populated:
    # preserve as unresolved rather than inventing direction.
    both = debit_present & credit_present

    if both.any():

        print(
            f"[WARNING] {source_file}: "
            f"{int(both.sum())} rows contain both debit "
            f"and credit. bank_amount left unresolved "
            f"for those rows."
        )

    # Text fields
    for column in [
        "bank_description",
        "bank_reference",
        "bank_customer_reference",
        "bank_account",
        "bank_transaction_type",
    ]:
        out[column] = out[column].map(clean_text)

    out["bank_name"] = bank_name
    out["source_file"] = source_file

    out["bank_row_index"] = np.arange(
        len(out),
        dtype=int,
    )

    return out


# ============================================================
# EVIDENCE FUNCTIONS
# ============================================================

def exact_text_match(
    a: Any,
    b: Any,
) -> bool:

    na = normalize_text(a)
    nb = normalize_text(b)

    return bool(
        na
        and nb
        and na == nb
    )


def contains_strong_text(
    a: Any,
    b: Any,
) -> bool:

    na = normalize_text(a)
    nb = normalize_text(b)

    if not na or not nb:
        return False

    if len(na) < 5 or len(nb) < 5:
        return False

    return na in nb or nb in na


def amount_difference(
    pop_amount: Any,
    bank_amount: Any,
) -> Optional[float]:

    if pd.isna(pop_amount) or pd.isna(bank_amount):
        return None

    return abs(
        float(pop_amount)
        - float(bank_amount)
    )


def date_difference_days(
    pop_date: Any,
    bank_date: Any,
) -> Optional[int]:

    if pd.isna(pop_date) or pd.isna(bank_date):
        return None

    return abs(
        int(
            (
                pd.Timestamp(pop_date)
                - pd.Timestamp(bank_date)
            ).days
        )
    )


# ============================================================
# EVIDENCE MODEL
# ============================================================

def calculate_evidence(
    pop: pd.Series,
    bank: pd.Series,
) -> Dict[str, Any]:

    evidence = []

    strong_identifiers = 0
    independent_families = 0

    # --------------------------------------------------------
    # REFERENCE FAMILY
    # --------------------------------------------------------

    reference_exact = exact_text_match(
        pop["pop_reference"],
        bank["bank_reference"],
    )

    customer_reference_exact = exact_text_match(
        pop["pop_customer_reference"],
        bank["bank_customer_reference"],
    )

    account_exact = exact_text_match(
        pop["pop_account"],
        bank["bank_account"],
    )

    customer_exact = exact_text_match(
        pop["pop_customer_name"],
        bank["bank_description"],
    )

    bank_exact = exact_text_match(
        pop["pop_bank_name"],
        bank["bank_name"],
    )

    source_exact = exact_text_match(
        pop["pop_source_file"],
        bank["source_file"],
    )

    payment_exact = exact_text_match(
        pop["pop_payment_method"],
        bank["bank_transaction_type"],
    )

    if reference_exact:
        evidence.append(
            "REFERENCE_EXACT"
        )
        strong_identifiers += 1
        independent_families += 1

    if customer_reference_exact:
        evidence.append(
            "CUSTOMER_REFERENCE_EXACT"
        )
        strong_identifiers += 1
        independent_families += 1

    if account_exact:
        evidence.append(
            "ACCOUNT_EXACT"
        )
        strong_identifiers += 1
        independent_families += 1

    if customer_exact:
        evidence.append(
            "CUSTOMER_EXACT"
        )
        independent_families += 1

    if bank_exact:
        evidence.append(
            "BANK_EXACT"
        )

    if source_exact:
        evidence.append(
            "SOURCE_EXACT"
        )

    if payment_exact:
        evidence.append(
            "PAYMENT_METHOD_EXACT"
        )

    # --------------------------------------------------------
    # AMOUNT
    # --------------------------------------------------------

    diff = amount_difference(
        pop["pop_amount"],
        bank["bank_amount"],
    )

    if diff is not None:

        if diff <= EXACT_AMOUNT_TOLERANCE:
            evidence.append(
                "AMOUNT_EXACT"
            )

        elif diff <= NEAR_AMOUNT_TOLERANCE:
            evidence.append(
                "AMOUNT_NEAR"
            )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_diff = date_difference_days(
        pop["pop_date"],
        bank["bank_date"],
    )

    if date_diff is not None:

        if date_diff == 0:
            evidence.append(
                "DATE_EXACT"
            )

        elif date_diff <= 1:
            evidence.append(
                "DATE_WITHIN_1_DAY"
            )

        elif date_diff <= 3:
            evidence.append(
                "DATE_WITHIN_3_DAYS"
            )

        elif date_diff <= DATE_WINDOW_DAYS:
            evidence.append(
                "DATE_WITHIN_WINDOW"
            )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 0

    if "AMOUNT_EXACT" in evidence:
        score += 35

    elif "AMOUNT_NEAR" in evidence:
        score += 20

    if reference_exact:
        score += 40

    if customer_reference_exact:
        score += 35

    if account_exact:
        score += 30

    if customer_exact:
        score += 15

    if payment_exact:
        score += 10

    if bank_exact:
        score += 5

    if date_diff == 0:
        score += 10

    elif date_diff is not None and date_diff <= 3:
        score += 5

    return {
        "score": score,
        "evidence": evidence,
        "strong_identifiers": strong_identifiers,
        "independent_families": independent_families,
        "amount_difference": diff,
        "date_difference": date_diff,
    }


# ============================================================
# MATCH DECISION
# ============================================================

def decide_match(
    ranked_candidates: List[Dict[str, Any]],
) -> Tuple[str, Optional[Dict[str, Any]]]:

    if not ranked_candidates:
        return "NO_MATCH", None

    best = ranked_candidates[0]

    second_score = (
        ranked_candidates[1]["score"]
        if len(ranked_candidates) > 1
        else None
    )

    if second_score is None:
        score_gap = float("inf")

    else:
        score_gap = (
            best["score"]
            - second_score
        )

    best["score_gap"] = score_gap

    # --------------------------------------------------------
    # Weak candidate
    # --------------------------------------------------------

    if best["score"] < MIN_MATCH_SCORE:
        return "NO_MATCH", best

    # --------------------------------------------------------
    # Ambiguous candidate
    # --------------------------------------------------------

    if (
        second_score is not None
        and score_gap < MIN_SCORE_GAP
    ):
        return "AMBIGUOUS", best

    # --------------------------------------------------------
    # Exact vs near
    # --------------------------------------------------------

    if (
        "AMOUNT_NEAR"
        in best["evidence"]
        and "AMOUNT_EXACT"
        not in best["evidence"]
    ):
        return "NEAR_AMOUNT", best

    return "MATCHED", best


# ============================================================
# MATCH ENGINE
# ============================================================

def generate_candidates(
    pop_row: pd.Series,
    bank_df: pd.DataFrame,
    locked_rows: set,
) -> List[Dict[str, Any]]:

    amount = pop_row["pop_amount"]

    if pd.isna(amount):
        return []

    bank = bank_df[
        ~bank_df["bank_row_index"].isin(
            locked_rows
        )
    ].copy()

    if bank.empty:
        return []

    # --------------------------------------------------------
    # EXACT AMOUNT FIRST
    # --------------------------------------------------------

    exact = bank[
        (
            bank["bank_amount"]
            - float(amount)
        ).abs()
        <= EXACT_AMOUNT_TOLERANCE
    ]

    # --------------------------------------------------------
    # NEAR AMOUNT SECOND
    # --------------------------------------------------------

    near = bank[
        (
            bank["bank_amount"]
            - float(amount)
        ).abs()
        <= NEAR_AMOUNT_TOLERANCE
    ]

    # Exact candidates have priority.
    if not exact.empty:
        candidates_df = exact

    else:
        candidates_df = near

    if candidates_df.empty:
        return []

    if len(candidates_df) > MAX_CANDIDATES_PER_POP:
        candidates_df = candidates_df.head(
            MAX_CANDIDATES_PER_POP
        )

    results = []

    for _, bank_row in candidates_df.iterrows():

        ev = calculate_evidence(
            pop_row,
            bank_row,
        )

        result = {
            "bank_row_index": bank_row[
                "bank_row_index"
            ],
            "score": ev["score"],
            "evidence": ev["evidence"],
            "strong_identifiers": ev[
                "strong_identifiers"
            ],
            "independent_families": ev[
                "independent_families"
            ],
            "amount_difference": ev[
                "amount_difference"
            ],
            "date_difference": ev[
                "date_difference"
            ],
        }

        results.append(result)

    results.sort(
        key=lambda x: (
            x["score"],
            x["strong_identifiers"],
            x["independent_families"],
            -(
                x["amount_difference"]
                if x["amount_difference"]
                is not None
                else 999999
            ),
            -(
                x["date_difference"]
                if x["date_difference"]
                is not None
                else 999999
            ),
        ),
        reverse=True,
    )

    for rank, candidate in enumerate(
        results,
        start=1,
    ):
        candidate["candidate_rank"] = rank

    return results


# ============================================================
# MATCH OUTPUT
# ============================================================

def run_matching(
    pop_df: pd.DataFrame,
    bank_df: pd.DataFrame,
):

    matches = []
    candidates_output = []

    locked_rows = set()

    for _, pop_row in pop_df.iterrows():

        case_number = pop_row[
            "case_number"
        ]

        if pd.isna(pop_row["pop_amount"]):

            matches.append(
                {
                    "case_number": case_number,
                    "status": "INVALID_POP",
                    "match_reason": "Missing POP amount.",
                    "score": None,
                    "score_gap": None,
                    "candidate_count": 0,
                }
            )

            continue

        candidates = generate_candidates(
            pop_row,
            bank_df,
            locked_rows,
        )

        status, selected = decide_match(
            candidates
        )

        for candidate in candidates:

            candidate_row = {
                "case_number": case_number,
                "candidate_rank": candidate[
                    "candidate_rank"
                ],
                "is_selected": (
                    selected is not None
                    and candidate[
                        "bank_row_index"
                    ]
                    == selected[
                        "bank_row_index"
                    ]
                ),
                "already_locked": False,
                "status": status,
                "score": candidate["score"],
                "score_gap": (
                    selected["score_gap"]
                    if selected
                    else None
                ),
                "amount_difference": candidate[
                    "amount_difference"
                ],
                "date_difference": candidate[
                    "date_difference"
                ],
                "evidence": "|".join(
                    candidate["evidence"]
                ),
            }

            bank_match = bank_df[
                bank_df["bank_row_index"]
                == candidate[
                    "bank_row_index"
                ]
            ]

            if not bank_match.empty:

                bank_dict = bank_match.iloc[
                    0
                ].to_dict()

                candidate_row.update(
                    bank_dict
                )

            pop_dict = pop_row.to_dict()

            candidate_row.update(
                {
                    f"POP_{k}": v
                    for k, v in pop_dict.items()
                }
            )

            candidates_output.append(
                candidate_row
            )

        match_record = {
            "case_number": case_number,
            "status": status,
            "match_reason": (
                "|".join(
                    selected["evidence"]
                )
                if selected
                else None
            ),
            "score": (
                selected["score"]
                if selected
                else None
            ),
            "score_gap": (
                selected["score_gap"]
                if selected
                else None
            ),
            "candidate_count": len(
                candidates
            ),
        }

        if selected:

            bank_match = bank_df[
                bank_df["bank_row_index"]
                == selected[
                    "bank_row_index"
                ]
            ]

            if not bank_match.empty:

                bank_dict = bank_match.iloc[
                    0
                ].to_dict()

                match_record.update(
                    bank_dict
                )

        match_record.update(
            {
                f"POP_{k}": v
                for k, v in pop_row.to_dict().items()
            }
        )

        matches.append(
            match_record
        )

        # ----------------------------------------------------
        # LOCK ONLY CONFIDENT MATCHES
        # ----------------------------------------------------

        if (
            status in {
                "MATCHED",
                "NEAR_AMOUNT",
            }
            and selected is not None
        ):

            locked_rows.add(
                selected[
                    "bank_row_index"
                ]
            )

    return (
        pd.DataFrame(matches),
        pd.DataFrame(candidates_output),
        locked_rows,
    )


# ============================================================
# DIAGNOSTICS
# ============================================================

def write_diagnostic(
    text: str,
):

    print("\n" + text)

    with open(
        DIAGNOSTIC_REPORT,
        "w",
        encoding="utf-8",
    ) as f:
        f.write(text)


def build_diagnostic_report(
    inspections: List[SheetInspection],
) -> str:

    lines = []

    lines.append(
        "POP -> BANK MATCHING ENGINE V9"
    )

    lines.append(
        "=" * 80
    )

    lines.append("")

    for item in inspections:

        lines.append(
            f"FILE       : {item.file}"
        )

        lines.append(
            f"SHEET      : {item.sheet}"
        )

        lines.append(
            f"HEADER ROW : {item.header_row}"
        )

        lines.append(
            f"ROLE       : {item.role}"
        )

        lines.append(
            f"ROLE SCORE : {item.role_score}"
        )

        lines.append(
            f"COLUMNS    : {item.columns_found}"
        )

        lines.append(
            f"SIGNALS    : {item.signals}"
        )

        lines.append("")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 120)
    print("POP -> BANK MATCHING ENGINE V9")
    print("=" * 120)

    print(
        f"\nPOP INPUT : {POP_INPUT_DIR}"
    )

    print(
        f"BANK INPUT: {BANK_INPUT_DIR}"
    )

    # --------------------------------------------------------
    # DISCOVERY
    # --------------------------------------------------------

    pop_files = discover_files(
        POP_INPUT_DIR
    )

    bank_files = discover_files(
        BANK_INPUT_DIR
    )

    print(
        f"\nDiscovered POP-side files : {len(pop_files)}"
    )

    print(
        f"Discovered BANK-side files: {len(bank_files)}"
    )

    all_files = pop_files + bank_files

    # --------------------------------------------------------
    # INSPECTION
    # --------------------------------------------------------

    inspections = inspect_files(
        all_files
    )

    print_schema_report(
        inspections
    )

    diagnostic_text = build_diagnostic_report(
        inspections
    )

    with open(
        DIAGNOSTIC_REPORT,
        "w",
        encoding="utf-8",
    ) as f:
        f.write(diagnostic_text)

    # --------------------------------------------------------
    # SAVE SCHEMA REPORT
    # --------------------------------------------------------

    schema_rows = []

    for item in inspections:

        schema_rows.append(
            {
                "file": str(item.file),
                "sheet": item.sheet,
                "rows_previewed": item.rows,
                "columns": item.columns,
                "header_row": item.header_row,
                "role": item.role,
                "role_score": item.role_score,
                "columns_found": " | ".join(
                    item.columns_found
                ),
                "signals": " | ".join(
                    item.signals
                ),
            }
        )

    pd.DataFrame(
        schema_rows
    ).to_excel(
        SCHEMA_REPORT,
        index=False,
    )

    # --------------------------------------------------------
    # IDENTIFY POP SHEETS
    # --------------------------------------------------------

    pop_candidates = [
        x
        for x in inspections
        if x.role == "POP"
    ]

    bank_candidates = [
        x
        for x in inspections
        if x.role == "BANK"
    ]

    print("\n")
    print("=" * 120)
    print("ROLE CLASSIFICATION")
    print("=" * 120)

    print(
        f"POP candidates : {len(pop_candidates)}"
    )

    print(
        f"BANK candidates: {len(bank_candidates)}"
    )

    # --------------------------------------------------------
    # POP VALIDATION
    # --------------------------------------------------------

    valid_pop_sources = []

    for candidate in pop_candidates:

        try:

            df = load_sheet_with_header(
                candidate.file,
                candidate.sheet,
                candidate.header_row,
            )

            decision = validate_pop_schema(
                df
            )

            print("\n" + "-" * 100)

            print(
                f"POP CANDIDATE: {candidate.file.name}"
            )

            print(
                f"SHEET: {candidate.sheet}"
            )

            print(
                f"VALID: {decision.valid}"
            )

            print(
                f"REASON: {decision.reason}"
            )

            print(
                f"ROLES: {json.dumps(decision.roles, indent=2, default=str)}"
            )

            if decision.valid:

                valid_pop_sources.append(
                    (
                        candidate,
                        df,
                        decision,
                    )
                )

        except Exception as exc:

            print(
                f"[POP ERROR] "
                f"{candidate.file.name}: {exc}"
            )

    # --------------------------------------------------------
    # CRITICAL SAFE STOP
    # --------------------------------------------------------

    if not valid_pop_sources:

        print("\n")
        print("=" * 120)
        print("SAFE STOP — NO VALID POP TRANSACTION SOURCE")
        print("=" * 120)

        print(
            """
The engine did NOT find a reliable POP transaction dataset.

This is intentional.

The currently available POP workbook appears to be
insufficient for transaction matching if it only contains
email/attachment metadata.

The engine will NOT:

    Value Date -> amount
    Bank Reference -> customer
    Bank Reference -> bank name
    Attachments Count -> account

or any other speculative mapping.

Required next step:

Provide the actual POP transaction/payment source containing,
at minimum:

    1. transaction/case identifier
    2. transaction/payment amount

Ideally also:

    reference
    customer reference
    customer name
    account
    bank
    payment method
    transaction date

The diagnostic files have been generated so the missing
schema can be reviewed.

No matching was performed.
"""
        )

        return

    # --------------------------------------------------------
    # CURRENT VERSION:
    # Require exactly one valid POP source
    # --------------------------------------------------------

    if len(valid_pop_sources) > 1:

        print("\n")
        print(
            "MULTIPLE VALID POP SOURCES FOUND."
        )

        for candidate, _, _ in valid_pop_sources:

            print(
                f"  {candidate.file.name}"
                f" / {candidate.sheet}"
            )

        print(
            "\nV9 will NOT arbitrarily choose one."
        )

        print(
            "Provide an explicit POP source or "
            "extend source-resolution policy."
        )

        return

    pop_candidate, pop_raw, pop_decision = (
        valid_pop_sources[0]
    )

    print("\n")
    print("=" * 120)
    print("SELECTED POP SOURCE")
    print("=" * 120)

    print(
        f"FILE : {pop_candidate.file}"
    )

    print(
        f"SHEET: {pop_candidate.sheet}"
    )

    print(
        f"ROLES: {pop_decision.roles}"
    )

    pop_df = normalize_pop(
        pop_raw,
        pop_decision,
        pop_candidate.file.name,
    )

    pop_df = pop_df[
        pop_df["pop_amount"].notna()
    ].copy()

    print(
        f"\nUsable POP transaction rows: {len(pop_df)}"
    )

    # --------------------------------------------------------
    # BANK NORMALIZATION
    # --------------------------------------------------------

    normalized_banks = []

    for candidate in bank_candidates:

        try:

            raw = load_sheet_with_header(
                candidate.file,
                candidate.sheet,
                candidate.header_row,
            )

            decision = validate_bank_schema(
                raw
            )

            print("\n" + "-" * 100)

            print(
                f"BANK: {candidate.file.name}"
            )

            print(
                f"SHEET: {candidate.sheet}"
            )

            print(
                f"VALID: {decision.valid}"
            )

            print(
                f"REASON: {decision.reason}"
            )

            if not decision.valid:
                continue

            normalized = normalize_bank(
                raw,
                decision,
                candidate.file.name,
                candidate.file.stem,
            )

            normalized_banks.append(
                normalized
            )

        except Exception as exc:

            print(
                f"[BANK ERROR] "
                f"{candidate.file.name}: {exc}"
            )

    if not normalized_banks:

        print(
            "\nSAFE STOP — no valid bank statement "
            "transaction source was identified."
        )

        return

    bank_df = pd.concat(
        normalized_banks,
        ignore_index=True,
    )

    bank_df["bank_row_index"] = np.arange(
        len(bank_df),
        dtype=int,
    )

    bank_df = bank_df[
        bank_df["bank_amount"].notna()
    ].copy()

    print(
        f"\nNormalized bank rows: {len(bank_df)}"
    )

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    print("\n")
    print("=" * 120)
    print("STARTING MATCHING")
    print("=" * 120)

    matches, candidates, locked = run_matching(
        pop_df,
        bank_df,
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    matches.to_excel(
        MATCH_RESULTS,
        index=False,
    )

    candidates.to_excel(
        CANDIDATE_AUDIT,
        index=False,
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n")
    print("=" * 120)
    print("FINAL MATCHING SUMMARY")
    print("=" * 120)

    if not matches.empty:

        print(
            matches[
                "status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

    print(
        f"\nUnique bank rows locked: {len(locked)}"
    )

    print(
        f"Candidate rows: {len(candidates)}"
    )

    print(
        f"\nMATCH RESULTS:"
        f"\n{MATCH_RESULTS}"
    )

    print(
        f"\nCANDIDATE AUDIT:"
        f"\n{CANDIDATE_AUDIT}"
    )

    print(
        f"\nSCHEMA REPORT:"
        f"\n{SCHEMA_REPORT}"
    )

    print(
        f"\nDIAGNOSTIC REPORT:"
        f"\n{DIAGNOSTIC_REPORT}"
    )


if __name__ == "__main__":
    main()
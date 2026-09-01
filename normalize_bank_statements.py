
from pathlib import Path
import csv
import io
import re

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_DIR = Path(
    r"D:\AUG-bank_files\normalization_input"
)

OUTPUT_FILE = INPUT_DIR / "normalized_bank_statements.xlsx"
FAILED_FILE = INPUT_DIR / "normalization_failures.txt"

STANDARD_COLUMNS = [
    "date",
    "value_date",
    "description",
    "reference",
    "customer_reference",
    "transaction_type",
    "debit_amount",
    "credit_amount",
    "balance",
    "bank_name",
    "source_file",
]

SUPPORTED_EXTENSIONS = {
    ".xls",
    ".xlsx",
    ".xlsm",
    ".csv",
    ".html",
    ".htm",
}


# ============================================================
# TEXT / NORMALIZATION HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    value = str(value)
    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_column_name(value):
    value = clean_text(value).lower()

    value = value.replace("&", " and ")

    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)

    return value.strip("_")


def is_blank(value):
    return clean_text(value) == ""


def row_text(row):
    return " ".join(
        clean_text(v).lower()
        for v in row.tolist()
        if clean_text(v)
    )


# ============================================================
# BANK DETECTION
# ============================================================

def detect_bank(filename):
    """
    Filename-based bank detection.

    Unknown banks are allowed. Bank recognition is NOT used
    as a requirement for extraction.
    """

    name = Path(filename).name.upper().strip()
    bank_prefixes = {
        "FAB": "FAB",
        "ADCB": "ADCB",
        "CBD": "CBD",
        "MASHREQ": "MASHREQ",
        "NBO": "NBO",
        "UAB": "UAB",
        "UBL": "UBL",
        "AJMAN": "AJMAN",
        "CBI": "CBI",
        "ABK": "ABK",

        # Newly identified banks
        "NBF": "NBF",
        "NBRAK": "NBRAK",
        "ADIB": "ADIB",
        "NBB": "NBB",

        # Already observed in output
        "INVEST": "INVEST BANK",
    }
    for prefix, bank in sorted(
        bank_prefixes.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    ):
        if name.startswith(prefix):
            return bank

    # Generic fallback: unknown banks are not blocked, they are
    # tagged with a filename-derived name instead of collapsing
    # to "UNKNOWN". Matches the mentor's "any bank should work"
    # requirement without hardcoding every bank the pipeline
    # will ever see.
    match = re.match(r"([A-Z]+)", name)
    if match and match.group(1):
        return match.group(1)

    return "UNKNOWN"


# ============================================================
# FILE FORMAT DETECTION
# ============================================================

def detect_file_type(path):
    """
    Detect actual format from file signature/content.
    """

    path = Path(path)

    with open(path, "rb") as f:
        signature = f.read(4096)

    # ZIP-based Office files: XLSX / XLSM
    if signature.startswith(b"PK"):
        return "xlsx"

    # Legacy XLS / OLE compound document
    if signature.startswith(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    ):
        return "xls"

    lower_signature = signature.lower()

    # HTML
    if (
        b"<!doctype html" in lower_signature
        or b"<html" in lower_signature
        or b"<table" in lower_signature
        or b"<head" in lower_signature
    ):
        return "html"

    # Text / CSV
    try:
        text = signature.decode(
            "utf-8",
            errors="ignore",
        )

        lower_text = text.lower()

        if (
            "," in text
            or "\t" in text
            or ";" in text
            or "date" in lower_text
            or "transaction" in lower_text
            or "description" in lower_text
        ):
            return "text"

    except Exception:
        pass

    return "unknown"


# ============================================================
# RAW EXCEL READING
# ============================================================

def read_excel_sheets(path, engine):
    excel = pd.ExcelFile(
        path,
        engine=engine,
    )

    print(f"SHEETS: {excel.sheet_names}")

    sheets = {}

    for sheet_name in excel.sheet_names:
        df = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=None,
            dtype=object,
            engine=engine,
        )

        sheets[sheet_name] = df

        print(
            f"  SHEET={sheet_name} "
            f"SHAPE={df.shape}"
        )

    return sheets


# ============================================================
# ROBUST TEXT / CSV READING
# ============================================================

def detect_text_encoding(path):
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin1",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]

    for encoding in encodings:
        try:
            with open(
                path,
                "r",
                encoding=encoding,
                errors="strict",
            ) as f:
                f.read(10000)

            return encoding

        except Exception:
            continue

    return "latin1"


def detect_delimiter(text):
    """
    Robust delimiter detection.

    We do not rely entirely on csv.Sniffer because bank CSVs
    often contain metadata lines with inconsistent structures.
    """

    candidates = [",", "\t", ";", "|"]

    lines = [
        line
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return ","

    sample_lines = lines[:80]

    scores = {}

    for delimiter in candidates:
        counts = []

        for line in sample_lines:
            try:
                count = len(
                    next(
                        csv.reader(
                            [line],
                            delimiter=delimiter,
                        )
                    )
                )
            except Exception:
                count = 1

            counts.append(count)

        multi_field = sum(
            1 for count in counts
            if count > 1
        )

        if multi_field == 0:
            scores[delimiter] = (-1, -1)
            continue

        # Prefer delimiters that repeatedly produce the same
        # number of columns.
        frequency = {}

        for count in counts:
            if count > 1:
                frequency[count] = frequency.get(
                    count,
                    0,
                ) + 1

        most_common_width = max(
            frequency,
            key=frequency.get,
        )

        consistency = frequency[
            most_common_width
        ]

        scores[delimiter] = (
            consistency,
            most_common_width,
        )

    best = max(
        scores,
        key=scores.get,
    )

    if scores[best][0] <= 0:
        return ","

    return best


def read_text_file(path):
    encoding = detect_text_encoding(path)

    with open(
        path,
        "r",
        encoding=encoding,
        errors="replace",
        newline="",
    ) as f:
        text = f.read()

    delimiter = detect_delimiter(text)

    print(
        f"TEXT ENCODING: {encoding}"
    )
    print(
        f"TEXT DELIMITER: {repr(delimiter)}"
    )

    rows = []

    reader = csv.reader(
        io.StringIO(text),
        delimiter=delimiter,
    )

    for row in reader:
        rows.append(row)

    if not rows:
        return {
            "CSV": pd.DataFrame()
        }

    max_columns = max(
        len(row)
        for row in rows
    )

    padded = []

    for row in rows:
        row = list(row)

        if len(row) < max_columns:
            row.extend(
                [""] * (
                    max_columns - len(row)
                )
            )

        elif len(row) > max_columns:
            row = row[:max_columns]

        padded.append(row)

    df = pd.DataFrame(
        padded,
        dtype=object,
    )

    print(
        f"TEXT RAW SHAPE: {df.shape}"
    )

    return {
        "CSV": df
    }


# ============================================================
# RAW FILE READING
# ============================================================

def read_raw_file(path):
    file_type = detect_file_type(path)

    print("\n" + "=" * 100)
    print(f"FILE: {path.name}")
    print(f"ACTUAL FORMAT: {file_type}")
    print("=" * 100)

    if file_type == "xlsx":
        return read_excel_sheets(
            path,
            "openpyxl",
        )

    if file_type == "xls":
        return read_excel_sheets(
            path,
            "xlrd",
        )

    if file_type == "html":
        tables = pd.read_html(path)

        print(
            f"HTML TABLES FOUND: {len(tables)}"
        )

        sheets = {}

        for i, table in enumerate(tables):
            name = f"HTML_TABLE_{i + 1}"

            sheets[name] = table

            print(
                f"  {name} "
                f"SHAPE={table.shape}"
            )

        return sheets

    if file_type == "text":
        return read_text_file(path)

    raise ValueError(
        f"Unknown file format: {path.name}"
    )


# ============================================================
# HEADER DETECTION
# ============================================================

HEADER_ALIASES = {
    "date": {
        "date",
        "transaction_date",
        "transaction_dates",
        "posting_date",
        "booking_date",
        "trans_date",
    },

    "value_date": {
        "value_date",
        "value_dates",
        "valuedate",
        "value_dt",
    },

    "description": {
        "description",
        "narration",
        "particulars",
        "particular",
        "details",
        "remarks",
        "transaction_description",
        "transaction_details",
        "transaction_remarks",
        "text",
    },

    "reference": {
        "reference",
        "transaction_reference",
        "bank_reference",
        "bank_ref",
        "channel_reference",
        "channel_ref",
        "doc_no",
        "document_no",
        "document_number",
        "cheque_no",
        "check_no",
        "instrument_no",
        "instrument_number",
    },

    "customer_reference": {
        "customer_reference",
        "customer_ref",
        "cust_ref",
        "buyer_code",
        "buyer_reference",
        "customer_code",
        "client_reference",
    },

    "transaction_type": {
        "transaction_type",
        "type",
        "type_code",
        "transaction_code",
        "txn_type",
        "txn_code",
    },

    "debit_amount": {
        "debit",
        "debit_amount",
        "withdrawls",
        "withdrawals",
        "withdrawl",
        "withdrawal",
        "dr",
        "debit_value",
        "debit_amt",
        "withdrawal_amount",
    },

    "credit_amount": {
        "credit",
        "credit_amount",
        "deposits",
        "deposit",
        "cr",
        "credit_value",
        "credit_amt",
        "deposit_amount",
    },

    "balance": {
        "balance",
        "running_balance",
        "running_bal",
        "closing_balance",
        "available_balance",
        "ledger_balance",
        "current_balance",
    },
}


HEADER_KEYWORDS = set().union(
    *HEADER_ALIASES.values()
)


def header_cell_score(value):
    normalized = normalize_column_name(value)

    if not normalized:
        return 0

    if normalized in HEADER_KEYWORDS:
        return 3

    # Controlled partial matches.
    for alias in HEADER_KEYWORDS:
        if (
            len(alias) >= 5
            and (
                normalized.startswith(alias + "_")
                or normalized.endswith("_" + alias)
            )
        ):
            return 2

    return 0


def score_header_row(df, row_index):
    """
    Score a candidate header using semantic coverage.

    A high score requires several distinct standard fields,
    rather than simply many occurrences of generic banking
    words.
    """

    row = df.iloc[row_index]

    normalized_values = [
        normalize_column_name(v)
        for v in row.tolist()
        if clean_text(v)
    ]

    if not normalized_values:
        return 0

    matched_fields = set()
    exact_matches = 0

    for value in normalized_values:
        if value in HEADER_KEYWORDS:
            exact_matches += 1

        for field, aliases in HEADER_ALIASES.items():
            if value in aliases:
                matched_fields.add(field)
                break

    score = 0

    # Distinct semantic fields are much more valuable.
    score += len(matched_fields) * 4

    score += min(
        exact_matches,
        5,
    )

    # Strong combinations.
    if "date" in matched_fields:
        score += 3

    if (
        "description" in matched_fields
        or "reference" in matched_fields
    ):
        score += 2

    if (
        "debit_amount" in matched_fields
        or "credit_amount" in matched_fields
    ):
        score += 3

    if "balance" in matched_fields:
        score += 3

    return score


def date_parse_ratio(values):
    if not values:
        return 0.0

    series = pd.Series(values)

    parsed = pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True,
    )

    return float(
        parsed.notna().mean()
    )


def numeric_ratio(values):
    if not values:
        return 0.0

    parsed = pd.Series(
        values
    ).apply(
        normalize_amount
    )

    return float(
        parsed.notna().mean()
    )


def score_data_below_header(
    df,
    header_row,
    header_width,
):
    """
    Validate the rows following a candidate header.

    This prevents metadata rows with banking words from being
    selected as the actual transaction header.
    """

    start = header_row + 1
    end = min(
        len(df),
        start + 15,
    )

    if start >= end:
        return 0

    sample = df.iloc[
        start:end,
        :header_width,
    ]

    if sample.empty:
        return 0

    score = 0

    for _, row in sample.iterrows():
        values = [
            clean_text(v)
            for v in row.tolist()
        ]

        nonempty = [
            v for v in values
            if v
        ]

        if not nonempty:
            continue

        date_values = [
            v for v in nonempty
            if re.search(
                r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
                v,
            )
            or re.search(
                r"\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}",
                v,
                flags=re.IGNORECASE,
            )
        ]

        if date_values:
            score += 3

        if any(
            normalize_amount(v)
            is not np.nan
            and pd.notna(
                normalize_amount(v)
            )
            for v in nonempty
        ):
            score += 1

    return score


def find_header_row(df):
    """
    SINGLE header detection strategy.

    Returns:
        (row_index, score)

    Raises:
        ValueError if no credible header exists.
    """

    if df is None or df.empty:
        raise ValueError(
            "Empty dataframe"
        )

    best = None

    # Avoid treating extremely deep report/footer rows as
    # headers. Transaction headers normally occur near the
    # beginning of the useful sheet.
    max_scan = min(
        len(df),
        100,
    )

    for row_index in range(max_scan):
        base_score = score_header_row(
            df,
            row_index,
        )

        if base_score <= 0:
            continue

        header_width = len(
            df.iloc[row_index]
        )

        data_score = score_data_below_header(
            df,
            row_index,
            header_width,
        )

        total_score = (
            base_score
            + data_score
        )

        candidate = (
            total_score,
            base_score,
            data_score,
            row_index,
        )

        if best is None or candidate > best:
            best = candidate

    if best is None:
        raise ValueError(
            "Could not detect transaction header row"
        )

    total_score, base_score, data_score, row_index = best

    # Credibility threshold.
    if (
        base_score < 8
        and total_score < 12
    ):
        raise ValueError(
            "No credible transaction header detected"
        )

    return row_index, total_score


# ============================================================
# COLUMN UTILITIES
# ============================================================

def make_unique_columns(columns):
    result = []
    counts = {}

    for col in columns:
        col = normalize_column_name(col)

        if not col:
            col = "unnamed"

        if col not in counts:
            counts[col] = 0
            result.append(col)
        else:
            counts[col] += 1

            result.append(
                f"{col}_{counts[col]}"
            )

    return result


def combine_multilevel_headers(df):
    """
    Handle simple two-row/multi-row headers.

    We only combine adjacent rows when the first row appears
    to contain header terminology and the second row contains
    complementary header terminology.
    """

    if df is None or len(df) < 2:
        return df

    best_single = max(
        (
            score_header_row(df, i),
            i,
        )
        for i in range(
            min(len(df), 10)
        )
    )

    # If a strong single-row header exists, use it.
    if best_single[0] >= 12:
        return df

    best_multi = None

    for i in range(
        min(len(df) - 1, 10)
    ):
        row1 = df.iloc[i]
        row2 = df.iloc[i + 1]

        combined = []

        for a, b in zip(
            row1.tolist(),
            row2.tolist(),
        ):
            a = clean_text(a)
            b = clean_text(b)

            if a and b:
                combined.append(
                    f"{a} {b}"
                )
            elif a:
                combined.append(a)
            else:
                combined.append(b)

        score = 0

        for value in combined:
            score += header_cell_score(
                value
            )

        if best_multi is None or score > best_multi[0]:
            best_multi = (
                score,
                i,
                combined,
            )

    if (
        best_multi is not None
        and best_multi[0] >= 10
    ):
        i = best_multi[1]

        combined_row = pd.DataFrame(
            [best_multi[2]]
        )

        remainder = df.iloc[
            i + 2:
        ].copy()

        result = pd.concat(
            [
                combined_row,
                remainder,
            ],
            ignore_index=True,
        )

        return result

    return df


# ============================================================
# GENERIC TABLE EXTRACTION
# ============================================================

def extract_transaction_table(df):
    if df is None or df.empty:
        raise ValueError(
            "Empty dataframe"
        )

    df = df.copy()

    # Remove fully empty rows/columns first.
    df = df.dropna(
        how="all"
    )

    df = df.dropna(
        axis=1,
        how="all",
    )

    if df.empty:
        raise ValueError(
            "No data after removing empty rows"
        )

    header_row, score = find_header_row(
        df
    )

    print(
        f"  HEADER ROW: {header_row} "
        f"(score={score})"
    )

    print(
        "  RAW HEADERS:",
        df.iloc[header_row].tolist(),
    )

    data = df.iloc[
        header_row + 1:
    ].copy()

    data.columns = make_unique_columns(
        df.iloc[header_row].tolist()
    )

    data = data.dropna(
        how="all"
    )

    data = data.dropna(
        axis=1,
        how="all",
    )

    if data.empty:
        return data

    return data.reset_index(
        drop=True
    )


# ============================================================
# HTML TABLE DETECTION
# ============================================================

def html_column_field_set(df):
    fields = set()

    for col in df.columns:
        normalized = normalize_column_name(
            col
        )

        for field, aliases in HEADER_ALIASES.items():
            if normalized in aliases:
                fields.add(field)
                break

            for alias in aliases:
                if (
                    len(alias) >= 5
                    and (
                        normalized.startswith(
                            alias + "_"
                        )
                        or normalized.endswith(
                            "_" + alias
                        )
                    )
                ):
                    fields.add(field)
                    break

    return fields


def looks_like_html_transaction_table(df):
    if df is None or df.empty:
        return False

    fields = html_column_field_set(
        df
    )

    if not fields:
        return False

    # Strong table.
    if (
        "date" in fields
        and (
            "description" in fields
            or "reference" in fields
        )
        and (
            "debit_amount" in fields
            or "credit_amount" in fields
            or "balance" in fields
        )
    ):
        return True

    # Some banks omit descriptions.
    if (
        "date" in fields
        and "balance" in fields
        and (
            "reference" in fields
            or "customer_reference" in fields
        )
    ):
        return True

    # Transaction table without a date can still be valid.
    if (
        len(fields) >= 4
        and (
            "debit_amount" in fields
            or "credit_amount" in fields
        )
        and (
            "description" in fields
            or "reference" in fields
        )
    ):
        return True

    return False


def clean_html_table(df):
    if df is None or df.empty:
        return None

    df = df.copy()

    df.columns = make_unique_columns(
        df.columns
    )

    df = df.dropna(
        how="all"
    )

    df = df.dropna(
        axis=1,
        how="all",
    )

    if df.empty:
        return None

    return df.reset_index(
        drop=True
    )


# ============================================================
# NON-TRANSACTION CLASSIFICATION
# ============================================================

SUMMARY_PATTERNS = [
    r"^total$",
    r"\baccount statement report\b",
    r"\btotal transactions?\b",
    r"\btotal debit\b",
    r"\btotal credit\b",
    r"\bgrand total\b",
    r"\bsubtotal\b",
    r"\bpage total\b",
    r"\bstatement generated\b",
    r"\bgenerated on\b",
    r"\bstatement period\b",
    r"\bstatement date\b",
    r"\bopening balance\b",
    r"\bopening bal\b",
    r"\bclosing balance\b",
    r"\bclosing bal\b",
    r"\bbrought forward\b",
    r"\bcarried forward\b",
    r"\bbalance brought forward\b",
    r"\bbalance carried forward\b",
]


def is_summary_text(text):
    text = clean_text(text).lower()

    if not text:
        return False

    for pattern in SUMMARY_PATTERNS:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return True

    return False


def is_non_transaction_row(row):
    """
    Generic classification of metadata, opening/closing
    balance, totals, report summaries, page rows, etc.
    """

    values = [
        clean_text(v)
        for v in row.tolist()
        if clean_text(v)
    ]

    if not values:
        return True

    # Summary/report labels can appear in one cell while
    # the same row also contains aggregate amounts.
    for value in values:
        if is_summary_text(value):
            return True

    joined = " ".join(values).lower()

    # Summary/report rows.
    if is_summary_text(joined):
        return True

    # A row consisting almost entirely of report labels.
    if (
        "account statement" in joined
        and not re.search(
            r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
            joined,
        )
    ):
        return True

    return False


# ============================================================
# AMOUNT NORMALIZATION
# ============================================================

def normalize_amount(value):
    if value is None:
        return np.nan

    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass

    text = clean_text(value)

    if not text:
        return np.nan

    upper = text.upper()

    is_debit = bool(
        re.search(
            r"\bDR$",
            upper,
        )
    )

    is_credit = bool(
        re.search(
            r"\bCR$",
            upper,
        )
    )

    text = re.sub(
        r"\s*(CR|DR)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Parentheses represent negative values.
    negative = (
        text.startswith("(")
        and text.endswith(")")
    )

    text = text.replace(
        ",",
        "",
    )

    # Remove currency names/symbols and other text.
    text = re.sub(
        r"[^\d.\-()]",
        "",
        text,
    )

    if not text:
        return np.nan

    if (
        text.startswith("(")
        and text.endswith(")")
    ):
        text = "-" + text[1:-1]

    try:
        number = float(text)
    except (ValueError, TypeError):
        return np.nan

    if negative:
        number = -abs(number)

    # Debit/credit source columns normally contain positive
    # magnitudes. Keep them positive.
    if is_debit or is_credit:
        number = abs(number)

    return number


def normalize_amounts(df):
    for col in [
        "debit_amount",
        "credit_amount",
        "balance",
    ]:
        df[col] = df[col].apply(
            normalize_amount
        )

    return df
# ============================================================
# DATE NORMALIZATION
# ============================================================

def normalize_single_date(value):
    """
    Convert different bank date formats into one standard date.

    IMPORTANT:
    The raw value is preserved during extraction.
    This function only standardizes the value for matching.
    """

    if value is None:
        return pd.NaT

    try:
        if pd.isna(value):
            return pd.NaT
    except Exception:
        pass

    text = clean_text(value)

    if not text:
        return pd.NaT

    # --------------------------------------------------------
    # CASE 1: Already a pandas / Python datetime
    # --------------------------------------------------------
    if isinstance(value, pd.Timestamp):
        return value.normalize()

    # --------------------------------------------------------
    # CASE 2: Excel serial date
    # --------------------------------------------------------
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            number = float(value)

            # Reasonable Excel date serial range.
            if 1 <= number <= 100000:
                parsed = pd.Timestamp(
                    "1899-12-30"
                ) + pd.to_timedelta(
                    number,
                    unit="D",
                )
                return parsed.normalize()
        except Exception:
            pass

    # --------------------------------------------------------
    # Remove unnecessary whitespace
    # --------------------------------------------------------
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # --------------------------------------------------------
    # Try explicit common formats first.
    # This avoids ambiguous parsing where possible.
    # --------------------------------------------------------
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d.%m.%y",

        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y.%m.%d",

        "%d-%b-%Y",
        "%d-%b-%y",
        "%d %b %Y",
        "%d %b %y",

        "%d-%B-%Y",
        "%d-%B-%y",
        "%d %B %Y",
        "%d %B %y",

        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            parsed = pd.to_datetime(
                text,
                format=fmt,
                errors="coerce",
            )

            if pd.notna(parsed):
                return parsed.normalize()

        except Exception:
            continue

    # --------------------------------------------------------
    # Final fallback.
    # Most bank statements use day-first conventions.
    # --------------------------------------------------------
    try:
        parsed = pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=True,
        )

        if pd.notna(parsed):
            return parsed.normalize()

    except Exception:
        pass

    return pd.NaT


def normalize_dates(df):
    """
    Standardize raw bank dates into pandas datetime values.

    Raw dates are temporarily preserved in:
        _raw_date
        _raw_value_date

    The final output still contains only:
        date
        value_date
    """

    df = df.copy()

    # --------------------------------------------------------
    # Preserve RAW dates before conversion.
    # --------------------------------------------------------
    df["_raw_date"] = df["date"].copy()
    df["_raw_value_date"] = df["value_date"].copy()

    # --------------------------------------------------------
    # Standardize dates.
    # --------------------------------------------------------
    df["date"] = df["_raw_date"].apply(
        normalize_single_date
    )

    df["value_date"] = df["_raw_value_date"].apply(
        normalize_single_date
    )

    return df
# ============================================================
# COLUMN MATCHING
# ============================================================

COLUMN_ALIASES = {
    "date": [
        "date",
        "transaction_date",
        "transaction_dates",
        "posting_date",
        "booking_date",
        "trans_date",
    ],

    "value_date": [
        "value_date",
        "value_dates",
        "valuedate",
        "value_dt",
    ],

    "description": [
        "description",
        "narration",
        "transaction_description",
        "transaction_remarks",
        "text",
        "remarks",
        "particulars",
        "particular",
        "details",
        "transaction_details",
    ],

    "reference": [
        "reference",
        "transaction_reference",
        "bank_reference",
        "bank_ref",
        "channel_reference",
        "channel_ref",
        "doc_no",
        "document_no",
        "document_number",
        "cheque_no",
        "check_no",
        "instrument_no",
        "instrument_number",
    ],

    "customer_reference": [
        "customer_reference",
        "customer_ref",
        "cust_ref",
        "buyer_code",
        "buyer_reference",
        "customer_code",
        "client_reference",
    ],

    "transaction_type": [
        "transaction_type",
        "type",
        "type_code",
        "transaction_code",
        "txn_type",
        "txn_code",
    ],

    "debit_amount": [
        "debit",
        "debit_amount",
        "withdrawls",
        "withdrawals",
        "withdrawl",
        "withdrawal",
        "dr",
        "debit_value",
        "debit_amt",
        "withdrawal_amount",
    ],

    "credit_amount": [
        "credit",
        "credit_amount",
        "deposits",
        "deposit",
        "cr",
        "credit_value",
        "credit_amt",
        "deposit_amount",
    ],

    "balance": [
        "balance",
        "running_balance",
        "running_bal",
        "closing_balance",
        "available_balance",
        "ledger_balance",
        "current_balance",
    ],
}


def find_matching_column(
    df,
    aliases,
    used_columns=None,
):
    """
    Conservative column matching.

    Exact semantic matches are preferred.
    Broad matching is only used when necessary.
    """

    if used_columns is None:
        used_columns = set()

    normalized = []

    for col in df.columns:
        normalized.append(
            (
                normalize_column_name(col),
                col,
            )
        )

    # Exact aliases first.
    for alias in aliases:
        alias_norm = normalize_column_name(
            alias
        )

        for col_norm, original in normalized:
            if original in used_columns:
                continue

            if col_norm == alias_norm:
                return original

    # Controlled partial matching.
    for alias in aliases:
        alias_norm = normalize_column_name(
            alias
        )

        if len(alias_norm) < 5:
            continue

        for col_norm, original in normalized:
            if original in used_columns:
                continue

            if (
                col_norm.startswith(
                    alias_norm + "_"
                )
                or col_norm.endswith(
                    "_" + alias_norm
                )
            ):
                return original

    return None


# ============================================================
# STANDARDIZATION
# ============================================================

def standardize_dataframe(
    df,
    bank_name,
    source_file,
):
    result = pd.DataFrame(
        index=df.index
    )

    used_columns = set()

    for standard_col in STANDARD_COLUMNS:
        if standard_col in {
            "bank_name",
            "source_file",
        }:
            continue

        source_col = find_matching_column(
            df,
            COLUMN_ALIASES.get(
                standard_col,
                [],
            ),
            used_columns,
        )

        if source_col is not None:
            result[standard_col] = df[
                source_col
            ]

            used_columns.add(
                source_col
            )

        else:
            result[standard_col] = pd.NA

    result["bank_name"] = bank_name
    result["source_file"] = source_file

    # Ensure exact schema.
    for col in STANDARD_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA

    return result[
        STANDARD_COLUMNS
    ]


# ============================================================
# TRANSACTION EVIDENCE
# ============================================================

def nonempty_text(value):
    return clean_text(value) != ""


def transaction_row_score(row):
    """
    Score evidence that a normalized row represents an
    actual transaction.

    Balance alone is deliberately insufficient.
    """

    score = 0

    date_valid = pd.notna(
        row.get("date")
    )

    value_date_valid = pd.notna(
        row.get("value_date")
    )

    description = clean_text(
        row.get("description")
    )

    reference = clean_text(
        row.get("reference")
    )

    customer_reference = clean_text(
        row.get("customer_reference")
    )

    transaction_type = clean_text(
        row.get("transaction_type")
    )

    debit = row.get(
        "debit_amount"
    )

    credit = row.get(
        "credit_amount"
    )

    balance = row.get(
        "balance"
    )

    has_debit = pd.notna(debit)
    has_credit = pd.notna(credit)
    has_balance = pd.notna(balance)

    has_amount = (
        has_debit
        or has_credit
    )

    has_identity = (
        date_valid
        or value_date_valid
        or bool(description)
        or bool(reference)
        or bool(customer_reference)
        or bool(transaction_type)
    )

    if date_valid:
        score += 4

    if value_date_valid:
        score += 2

    if description:
        score += 3

    if reference:
        score += 2

    if customer_reference:
        score += 1

    if transaction_type:
        score += 1

    if has_debit:
        score += 3

    if has_credit:
        score += 3

    if has_balance:
        score += 1

    # Balance alone is never enough.
    if (
        has_balance
        and not has_amount
        and not date_valid
        and not value_date_valid
        and not description
        and not reference
        and not customer_reference
        and not transaction_type
    ):
        return 0

    # Strong transaction combinations.
    if (
        (date_valid or value_date_valid)
        and (
            has_amount
            or description
            or reference
        )
    ):
        return max(score, 7)

    if (
        has_amount
        and (
            description
            or reference
            or customer_reference
            or date_valid
            or value_date_valid
        )
    ):
        return max(score, 6)

    # Date + description is useful even where amount is absent.
    if (
        (date_valid or value_date_valid)
        and description
    ):
        return max(score, 6)

    return 0


def remove_non_transaction_rows(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    keep_indices = []

    for idx, row in df.iterrows():
        if is_non_transaction_row(
            row
        ):
            continue

        score = transaction_row_score(
            row
        )

        if score > 0:
            keep_indices.append(
                idx
            )

    if not keep_indices:
        return pd.DataFrame(
            columns=df.columns
        )

    return df.loc[
        keep_indices
    ].copy()


# ============================================================
# DEDUPLICATION
# ============================================================

def normalized_identity_value(value):
    if pd.isna(value):
        return ""

    if isinstance(
        value,
        pd.Timestamp,
    ):
        return value.strftime(
            "%Y-%m-%d"
        )

    if isinstance(
        value,
        float,
    ):
        if np.isnan(value):
            return ""

        return f"{value:.10f}"

    return clean_text(value).lower()


def transaction_identity(row):
    """
    Conservative identity.

    Source file is included because identical transactions
    across different bank statements must not be collapsed.
    """

    fields = [
        "date",
        "value_date",
        "description",
        "reference",
        "customer_reference",
        "debit_amount",
        "credit_amount",
        "balance",
        "bank_name",
        "source_file",
    ]

    return tuple(
        normalized_identity_value(
            row.get(field)
        )
        for field in fields
    )


def deduplicate_transactions(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    identities = df.apply(
        transaction_identity,
        axis=1,
    )

    duplicate_mask = identities.duplicated(
        keep="first"
    )

    duplicate_count = int(
        duplicate_mask.sum()
    )

    if duplicate_count:
        print(
            f"  DUPLICATE TRANSACTIONS REMOVED: "
            f"{duplicate_count}"
        )

    return df.loc[
        ~duplicate_mask
    ].copy()


# ============================================================
# FINAL CLEANUP
# ============================================================

def final_cleanup(df):
    if df is None:
        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    if df.empty:
        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    df = df.copy()

    # Ensure all standard columns exist.
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    # Text cleanup.
    for col in [
        "description",
        "reference",
        "customer_reference",
        "transaction_type",
        "bank_name",
    ]:
        df[col] = df[col].apply(
            clean_text
        )

    # Dates and amounts must be normalized BEFORE
    # transaction evidence is evaluated.
    df = normalize_dates(
        df
    )

    df = normalize_amounts(
        df
    )

    # Remove metadata / summary / fake transaction rows.
    df = remove_non_transaction_rows(
        df
    )

    if df.empty:
        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    # Deduplicate.
    df = deduplicate_transactions(
        df
    )
    # Remove temporary raw-date columns.
    df = df.drop(
        columns=[
            "_raw_date",
            "_raw_value_date",
        ],
        errors="ignore",
    )

    # Exact schema.
    df = df[
        STANDARD_COLUMNS
    ]

    return df.reset_index(
        drop=True
    )
# ============================================================
# HTML PROCESSING
# ============================================================

def html_table_score(df):
    """
    Rank HTML candidates.

    Number of actual transaction-like rows is important, but
    semantic column coverage is more important.
    """

    fields = html_column_field_set(
        df
    )

    score = (
        len(fields) * 5
    )

    if "date" in fields:
        score += 5

    if "description" in fields:
        score += 5

    if "reference" in fields:
        score += 3

    if (
        "debit_amount" in fields
        or "credit_amount" in fields
    ):
        score += 5

    if "balance" in fields:
        score += 4

    return score


def get_html_transaction_tables(path):
    tables = pd.read_html(
        path
    )

    print(
        f"HTML TABLES FOUND: {len(tables)}"
    )

    candidates = []

    for i, table in enumerate(
        tables
    ):
        print(
            f"\n--- HTML TABLE {i + 1} ---"
        )

        print(
            "RAW SHAPE:",
            table.shape,
        )

        print(
            "RAW COLUMNS:",
            table.columns.tolist(),
        )

        cleaned = clean_html_table(
            table
        )

        if cleaned is None:
            print(
                "STATUS: EMPTY"
            )
            continue

        fields = html_column_field_set(
            cleaned
        )

        print(
            "DETECTED FIELDS:",
            sorted(fields),
        )

        if not looks_like_html_transaction_table(
            cleaned
        ):
            print(
                "STATUS: NOT A TRANSACTION TABLE"
            )
            continue

        # Standardize temporarily so we can evaluate actual
        # transaction rows.
        temporary = standardize_dataframe(
            cleaned,
            "UNKNOWN",
            path.name,
        )

        temporary = final_cleanup(
            temporary
        )

        transaction_count = len(
            temporary
        )

        table_score = html_table_score(
            cleaned
        )

        print(
            f"TRANSACTION-LIKE ROWS: "
            f"{transaction_count}"
        )

        print(
            f"TABLE SCORE: {table_score}"
        )

        # A table with zero transactions is still structurally
        # valid. It is not a failure.
        candidates.append(
            (
                transaction_count,
                table_score,
                i,
                cleaned,
            )
        )

    if not candidates:
        return [], False

    # Prefer tables with actual transaction rows.
    # If several have the same transaction rows, prefer the
    # strongest semantic structure.
    candidates.sort(
        key=lambda x: (
            x[0],
            x[1],
            -x[2],
        ),
        reverse=True,
    )

    best = candidates[0]

    transaction_count = best[0]
    table_score = best[1]
    table_index = best[2]
    table = best[3]

    print(
        "\nSELECTED HTML TABLE:"
    )

    print(
        f"  TABLE NUMBER: {table_index + 1}"
    )

    print(
        f"  TRANSACTION ROWS: {transaction_count}"
    )

    print(
        f"  TABLE SCORE: {table_score}"
    )

    # True means a structurally usable statement/table was
    # found, even if it contains zero transactions.
    return [table], True


def process_html_file(
    path,
    bank_name,
):
    tables, structurally_valid = (
        get_html_transaction_tables(
            path
        )
    )

    if not structurally_valid:
        raise ValueError(
            f"No credible transaction table found "
            f"in {path.name}"
        )

    normalized_parts = []

    for table in tables:
        normalized = standardize_dataframe(
            table,
            bank_name,
            path.name,
        )

        normalized = final_cleanup(
            normalized
        )

        if not normalized.empty:
            normalized_parts.append(
                normalized
            )

    # Valid statement, but no transactions.
    if not normalized_parts:
        print(
            f"VALID STATEMENT WITH ZERO TRANSACTIONS: "
            f"{path.name}"
        )

        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    result = pd.concat(
        normalized_parts,
        ignore_index=True,
    )

    return final_cleanup(
        result
    )


# ============================================================
# STRUCTURED XLS/XLSX PROCESSING
# ============================================================

def process_structured_file(
    path,
    bank_name,
):
    sheets = read_raw_file(
        path
    )

    normalized_parts = []
    credible_sheet_found = False

    for sheet_name, raw_df in sheets.items():
        print(
            f"\nPROCESSING SHEET: "
            f"{sheet_name}"
        )

        if (
            raw_df is None
            or raw_df.empty
        ):
            print(
                "  EMPTY SHEET"
            )
            continue

        try:
            transaction_df = (
                extract_transaction_table(
                    raw_df
                )
            )

            credible_sheet_found = True

            if (
                transaction_df is None
                or transaction_df.empty
            ):
                print(
                    "  NO DATA AFTER HEADER"
                )
                continue

            normalized = standardize_dataframe(
                transaction_df,
                bank_name,
                path.name,
            )

            normalized = final_cleanup(
                normalized
            )

            if normalized.empty:
                print(
                    "  NO ACTUAL TRANSACTIONS"
                )
                continue

            normalized_parts.append(
                normalized
            )

            print(
                f"  EXTRACTED ROWS: "
                f"{len(normalized)}"
            )

        except Exception as exc:
            print(
                f"  SHEET FAILED: "
                f"{repr(exc)}"
            )

    if not credible_sheet_found:
        raise ValueError(
            f"No credible transaction table found "
            f"in {path.name}"
        )

    # Important:
    # A credible statement with zero transactions is valid.
    if not normalized_parts:
        print(
            f"VALID STATEMENT WITH ZERO TRANSACTIONS: "
            f"{path.name}"
        )

        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    result = pd.concat(
        normalized_parts,
        ignore_index=True,
    )

    return final_cleanup(
        result
    )


# ============================================================
# CSV PROCESSING
# ============================================================

def process_csv_file(
    path,
    bank_name,
):
    print(
        "\nPROCESSING CSV:"
    )

    print(
        path.name
    )

    sheets = read_text_file(
        path
    )

    df = sheets.get(
        "CSV"
    )

    if df is None or df.empty:
        raise ValueError(
            f"No data found in {path.name}"
        )

    transaction_df = extract_transaction_table(
        df
    )

    if transaction_df is None or transaction_df.empty:
        return pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    normalized = standardize_dataframe(
        transaction_df,
        bank_name,
        path.name,
    )

    normalized = final_cleanup(
        normalized
    )

    return normalized


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(path):
    path = Path(path)

    bank_name = detect_bank(
        path.name
    )

    file_type = detect_file_type(
        path
    )

    print(
        f"\nBANK DETECTED: {bank_name}"
    )

    if file_type == "html":
        return process_html_file(
            path,
            bank_name,
        )

    if file_type in {
        "xls",
        "xlsx",
    }:
        return process_structured_file(
            path,
            bank_name,
        )

    if file_type == "text":
        return process_csv_file(
            path,
            bank_name,
        )

    raise ValueError(
        f"Unsupported file format "
        f"for {path.name}: {file_type}"
    )


# ============================================================
# SAFE PROCESSING
# ============================================================

def safe_process_file(path):
    path = Path(path)

    try:
        print(
            "\n" + "=" * 100
        )

        print(
            f"PROCESSING FILE: {path.name}"
        )

        print(
            "=" * 100
        )

        df = process_file(
            path
        )

        if df is None:
            return (
                None,
                "No dataframe returned",
            )

        # IMPORTANT:
        # Empty is NOT automatically a failure anymore.
        #
        # A valid statement can legitimately contain zero
        # transactions, e.g. UBL Total Transactions: 0.
        if df.empty:
            print(
                f"\nSUCCESS: {path.name}"
            )

            print(
                "VALID STATEMENT — 0 TRANSACTIONS"
            )

            return (
                df,
                None,
            )

        if len(df.columns) == 0:
            return (
                None,
                "No columns detected",
            )

        print(
            f"\nSUCCESS: {path.name}"
        )

        print(
            f"ROWS: {len(df)}"
        )

        print(
            f"COLUMNS: {df.columns.tolist()}"
        )

        return (
            df,
            None,
        )

    except Exception as exc:
        print(
            f"\nSKIPPED: {path.name}"
        )

        print(
            f"REASON: {repr(exc)}"
        )

        return (
            None,
            repr(exc),
        )


# ============================================================
# PROCESS DIRECTORY
# ============================================================

def process_directory(root):
    root = Path(root)

    files = sorted(
        p
        for p in root.iterdir()
        if (
            p.is_file()
            and not p.name.startswith("~$")
            and "_cleaned" not in p.name.lower()
            and "normalized_bank_statements"
            not in p.name.lower()
            and p.name.lower() not in {
                "source_inventory.xlsx",
                "zero_file_diagnosis.xlsx",
            }
            and p.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    )

    print(
        "=" * 100
    )

    print(
        "BANK STATEMENT NORMALIZATION"
    )

    print(
        "=" * 100
    )

    print(
        f"ROOT: {root}"
    )

    print(
        f"FILES FOUND: {len(files)}"
    )

    successful = []
    failures = []

    for path in files:
        df, error = safe_process_file(
            path
        )

        if df is not None:
            successful.append(
                df
            )

        else:
            failures.append(
                {
                    "file": str(path),
                    "reason": error,
                }
            )

    # ========================================================
    # COMBINE
    # ========================================================

    nonempty = [
        df
        for df in successful
        if df is not None
        and not df.empty
    ]

    if nonempty:
        combined = pd.concat(
            nonempty,
            ignore_index=True,
            sort=False,
        )

        combined = final_cleanup(
            combined
        )

    else:
        combined = pd.DataFrame(
            columns=STANDARD_COLUMNS
        )

    # ========================================================
    # FINAL GLOBAL DEDUPLICATION
    # ========================================================

    if not combined.empty:
        combined = deduplicate_transactions(
            combined
        )

        combined = combined[
            STANDARD_COLUMNS
        ]

    # ========================================================
    # FAILURE REPORT
    # ========================================================

    failure_df = pd.DataFrame(
        failures
    )

    if not failure_df.empty:
        FAILED_FILE.write_text(
            failure_df.to_string(
                index=False
            ),
            encoding="utf-8",
        )

    elif FAILED_FILE.exists():
        FAILED_FILE.unlink()

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print(
        "\n"
    )

    print(
        "=" * 100
    )

    print(
        "FINAL RESULT"
    )

    print(
        "=" * 100
    )

    print(
        f"TOTAL FILES:      {len(files)}"
    )

    print(
        f"SUCCESSFUL FILES: {len(successful)}"
    )

    print(
        f"FAILED/SKIPPED:   {len(failures)}"
    )

    print(
        f"FINAL DATAFRAME SHAPE: {combined.shape}"
    )

    if not combined.empty:
        print(
            "\nFINAL COLUMNS:"
        )

        print(
            combined.columns.tolist()
        )

        print(
            "\nROWS BY BANK:"
        )

        print(
            combined[
                "bank_name"
            ].value_counts(
                dropna=False
            )
        )

        print(
            "\nROWS BY SOURCE FILE:"
        )

        print(
            combined[
                "source_file"
            ].value_counts()
        )

        print(
            "\nMISSING VALUES:"
        )

        print(
            combined.isna().sum()
        )

        print(
            "\nFINAL DATAFRAME PREVIEW:"
        )

        print(
            combined.head(20).to_string(
                index=False
            )
        )

    if not failure_df.empty:
        print(
            "\nFILES REQUIRING LATER INVESTIGATION:"
        )

        print(
            failure_df.to_string(
                index=False
            )
        )

        print(
            "\nFAILURE REPORT:"
        )

        print(
            FAILED_FILE
        )

    # ========================================================
    # SAVE OUTPUT
    # ========================================================

    # Always write the output file, including a valid empty
    # result. This keeps the pipeline deterministic.
    combined.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\nOUTPUT:"
    )

    print(
        OUTPUT_FILE
    )

    return (
        combined,
        failure_df,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    process_directory(
        INPUT_DIR
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

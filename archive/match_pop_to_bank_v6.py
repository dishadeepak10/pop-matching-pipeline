# ============================================================
# POP -> BANK MATCHING ENGINE V8
#
# PURPOSE
# ------------------------------------------------------------
# Robust POP -> Bank statement transaction matching.
#
# DESIGN PRINCIPLES
# ------------------------------------------------------------
# 1. Automatically discover POP and BANK workbooks/sheets.
# 2. Do NOT confuse email/log workbooks with POP transaction data.
# 3. Detect headers even when they are not on row 1.
# 4. Normalize different column names into a common schema.
# 5. AMOUNT FIRST.
# 6. Exact amount candidates are preferred.
# 7. Near-amount candidates require stronger evidence.
# 8. Reference/customer-reference/account/customer/bank/source
#    evidence are used to separate candidates.
# 9. Date is SUPPORTING evidence, not the primary key.
# 10. One bank transaction can only be used once.
# 11. Never force a weak match.
# 12. Produce both final matches and detailed candidates.
#
# OUTPUT
# ------------------------------------------------------------
# matches.xlsx
# candidates.xlsx
#
# STATUSES
# ------------------------------------------------------------
# MATCHED
# NEAR_AMOUNT
# AMBIGUOUS
# NO_MATCH
#
# ============================================================

from pathlib import Path
import math
import re
import traceback

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Search these locations recursively.
SEARCH_DIRS = [
    BASE_DIR / "data",
    BASE_DIR / "testing_bank_statements",
    BASE_DIR,
]

OUTPUT_DIR = BASE_DIR / "data" / "output"

MATCH_OUTPUT = OUTPUT_DIR / "POP_BANK_MATCHES_V8.xlsx"
CANDIDATE_OUTPUT = OUTPUT_DIR / "POP_BANK_CANDIDATES_V8.xlsx"

# ------------------------------------------------------------
# Matching thresholds
# ------------------------------------------------------------

# Amount tolerance used for "near" amount candidates.
AMOUNT_TOLERANCE = 1.00

# Maximum transaction date distance considered useful.
DATE_WINDOW_DAYS = 7

# Minimum score for a normal exact-amount match.
MATCH_THRESHOLD = 70.0

# Minimum score for a near-amount match.
NEAR_MATCH_THRESHOLD = 82.0

# Minimum difference between first and second candidate.
MIN_SCORE_GAP = 12.0

# Maximum number of candidates retained per POP row.
MAX_CANDIDATES_PER_POP = 100


# ============================================================
# COLUMN ALIASES
# ============================================================

# All aliases are normalized before comparison.
#
# The lists intentionally contain many common bank / POP names.
# More can be added without changing the matching engine.

POP_ALIASES = {

    "case_number": [
        "case number",
        "case no",
        "case id",
        "case",
        "pop case",
        "ticket number",
        "ticket no",
        "ticket id",
        "reference case",
    ],

    "amount": [
        "amount",
        "payment amount",
        "pop amount",
        "transaction amount",
        "paid amount",
        "payment value",
        "value",
        "total amount",
        "received amount",
        "transfer amount",
        "amount paid",
        "amount received",
        "net amount",
        "gross amount",
        "payment value aed",
        "amount aed",
    ],

    "reference": [
        "reference",
        "ref",
        "payment reference",
        "transaction reference",
        "transaction ref",
        "bank reference",
        "bank ref",
        "payment ref",
        "utr",
        "utr number",
        "utr no",
        "utr ref",
        "rrn",
        "rrn number",
        "transaction id",
        "transaction number",
        "transaction no",
        "transfer id",
        "transfer reference",
    ],

    "customer_reference": [
        "customer reference",
        "customer ref",
        "cust reference",
        "cust ref",
        "customer transaction reference",
        "customer transaction ref",
        "payer reference",
        "payer ref",
        "sender reference",
        "sender ref",
        "beneficiary reference",
        "beneficiary ref",
    ],

    "account": [
        "account",
        "account number",
        "account no",
        "account name",
        "bank account",
        "beneficiary account",
        "beneficiary account number",
        "sender account",
        "sender account number",
        "debit account",
        "credit account",
        "iban",
        "iban number",
    ],

    "customer": [
        "customer",
        "customer name",
        "customer fullname",
        "customer full name",
        "client",
        "client name",
        "payer",
        "payer name",
        "sender",
        "sender name",
        "beneficiary",
        "beneficiary name",
        "account holder",
        "account holder name",
        "name",
    ],

    "bank_name": [
        "bank",
        "bank name",
        "customer bank",
        "beneficiary bank",
        "sender bank",
        "banking institution",
    ],

    "payment_method": [
        "payment method",
        "method",
        "payment type",
        "payment channel",
        "channel",
        "mode of payment",
        "transfer type",
    ],

    "source_file": [
        "source file",
        "file name",
        "filename",
        "source",
        "attachment",
        "attachment name",
        "document",
        "document name",
    ],

    "date": [
        "date",
        "transaction date",
        "payment date",
        "transfer date",
        "value date",
        "posting date",
        "received date",
        "payment received date",
        "transaction datetime",
        "transaction time",
        "email received date",
    ],
}


BANK_ALIASES = {

    "date": [
        "date",
        "transaction date",
        "transaction datetime",
        "posting date",
        "posting value date",
        "value date",
        "transaction value date",
        "txn date",
        "txn value date",
        "booking date",
    ],

    "value_date": [
        "value date",
        "value date time",
        "transaction value date",
        "posting date",
    ],

    "description": [
        "description",
        "transaction description",
        "narration",
        "transaction details",
        "details",
        "particulars",
        "remarks",
        "memo",
        "payment details",
        "transaction narration",
    ],

    "reference": [
        "reference",
        "ref",
        "bank reference",
        "bank ref",
        "transaction reference",
        "transaction ref",
        "transaction id",
        "transaction number",
        "transaction no",
        "utr",
        "utr number",
        "utr no",
        "rrn",
        "rrn number",
    ],

    "customer_reference": [
        "customer reference",
        "customer ref",
        "cust reference",
        "cust ref",
        "customer transaction reference",
        "customer transaction ref",
        "payer reference",
        "payer ref",
        "sender reference",
        "sender ref",
        "remitter reference",
        "remitter ref",
    ],

    "account": [
        "account",
        "account number",
        "account no",
        "iban",
        "iban number",
        "account name",
        "beneficiary account",
        "debit account",
        "credit account",
    ],

    "transaction_type": [
        "transaction type",
        "txn type",
        "type",
        "transaction category",
        "credit debit",
        "debit credit",
        "dr cr",
        "dr/cr",
    ],

    "debit_amount": [
        "debit amount",
        "debit",
        "debit amount aed",
        "withdrawal",
        "withdrawal amount",
        "paid out",
        "dr amount",
        "dr",
    ],

    "credit_amount": [
        "credit amount",
        "credit",
        "credit amount aed",
        "deposit",
        "deposit amount",
        "received",
        "received amount",
        "cr amount",
        "cr",
    ],

    "balance": [
        "balance",
        "closing balance",
        "available balance",
        "running balance",
        "account balance",
    ],

    "bank_name": [
        "bank",
        "bank name",
    ],

    "source_file": [
        "source file",
        "file name",
        "filename",
        "source",
    ],
}


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_text(value):
    """
    General text normalization.

    Keeps alphanumeric information while removing punctuation
    differences, repeated spaces and case differences.
    """
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    value = str(value).strip().upper()

    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\t", " ")

    value = re.sub(r"\s+", " ", value)

    return value


def normalize_key(value):
    """
    Used for column/header matching.
    """
    value = normalize_text(value)

    value = re.sub(
        r"[^A-Z0-9]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def compact_text(value):
    """
    Used for strong reference comparison.

    Example:
        ABC-123 / abc123 / ABC 123
    become comparable.
    """
    value = normalize_text(value)

    return re.sub(
        r"[^A-Z0-9]",
        "",
        value,
    )


def is_blank(value):
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    return str(value).strip() == ""


def safe_float(value):
    """
    Convert financial values safely.

    Handles:
      1,234.50
      AED 1,234.50
      (1,234.50)
      -1,234.50
      blank
    """
    if value is None:
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return np.nan
        return float(value)

    text = str(value).strip()

    if not text:
        return np.nan

    negative = False

    if (
        text.startswith("(")
        and text.endswith(")")
    ):
        negative = True

    text = text.replace(",", "")
    text = text.replace("AED", "")
    text = text.replace("USD", "")
    text = text.replace("INR", "")
    text = text.replace("EUR", "")
    text = text.replace("GBP", "")
    text = text.replace("₹", "")
    text = text.replace("$", "")

    text = text.replace("(", "")
    text = text.replace(")", "")

    text = text.strip()

    # Keep only numeric characters, dot and minus.
    text = re.sub(
        r"[^0-9.\-]",
        "",
        text,
    )

    if not text:
        return np.nan

    try:
        number = float(text)

        if negative:
            number = -abs(number)

        return number

    except Exception:
        return np.nan


def parse_date(value):
    if value is None:
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value

    if isinstance(value, np.datetime64):
        try:
            return pd.Timestamp(value)
        except Exception:
            return pd.NaT

    if isinstance(value, (int, float)):
        if pd.isna(value):
            return pd.NaT

        # Excel serial date.
        if 20000 <= float(value) <= 70000:
            try:
                return pd.Timestamp(
                    "1899-12-30"
                ) + pd.to_timedelta(
                    float(value),
                    unit="D",
                )
            except Exception:
                pass

    try:
        return pd.to_datetime(
            value,
            errors="coerce",
            dayfirst=False,
        )
    except Exception:
        return pd.NaT


def date_difference_days(
    date_a,
    date_b,
):
    if pd.isna(date_a) or pd.isna(date_b):
        return np.nan

    try:
        return abs(
            (
                pd.Timestamp(date_a)
                - pd.Timestamp(date_b)
            ).total_seconds()
        ) / 86400.0

    except Exception:
        return np.nan


# ============================================================
# HEADER DETECTION
# ============================================================

def read_excel_safely(path):
    """
    Read every sheet without assuming the first row is the header.
    """
    try:
        return pd.read_excel(
            path,
            sheet_name=None,
            header=None,
        )
    except Exception as exc:
        print(
            f"WARNING: Could not read {path}: {exc}"
        )
        return {}


def find_best_header_row(
    raw_df,
    aliases,
    max_rows=30,
):
    """
    Find the row most likely to contain column headers.
    """

    if raw_df.empty:
        return None, 0

    alias_keys = set()

    for values in aliases.values():
        for alias in values:
            alias_keys.add(
                normalize_key(alias)
            )

    best_row = None
    best_score = -1
    best_hits = 0

    rows_to_check = min(
        max_rows,
        len(raw_df),
    )

    for row_idx in range(rows_to_check):

        row_values = raw_df.iloc[
            row_idx
        ].tolist()

        hits = 0
        score = 0

        seen = set()

        for value in row_values:

            key = normalize_key(value)

            if not key:
                continue

            if key in seen:
                continue

            seen.add(key)

            if key in alias_keys:

                hits += 1
                score += 10

            else:

                # Partial header support.
                for alias_key in alias_keys:

                    if (
                        len(key) >= 4
                        and (
                            key in alias_key
                            or alias_key in key
                        )
                    ):
                        score += 2
                        break

        if hits > 0 and score > best_score:

            best_row = row_idx
            best_score = score
            best_hits = hits

    return best_row, best_hits


def build_mapping_from_columns(
    columns,
    aliases,
):
    """
    Map actual columns to normalized semantic fields.
    """

    mapping = {}

    normalized_columns = {
        col: normalize_key(col)
        for col in columns
    }

    for field, possible_names in aliases.items():

        alias_keys = [
            normalize_key(x)
            for x in possible_names
        ]

        best_column = None
        best_score = 0

        for column, column_key in normalized_columns.items():

            if not column_key:
                continue

            score = 0

            for alias_key in alias_keys:

                if column_key == alias_key:
                    score = max(
                        score,
                        100,
                    )

                elif (
                    column_key
                    in alias_key
                ):
                    score = max(
                        score,
                        80,
                    )

                elif (
                    alias_key
                    in column_key
                ):
                    score = max(
                        score,
                        70,
                    )

                else:

                    # Token overlap.
                    a = set(
                        column_key.split()
                    )

                    b = set(
                        alias_key.split()
                    )

                    if a and b:
                        overlap = len(
                            a & b
                        ) / max(
                            len(a),
                            len(b),
                        )

                        if overlap >= 0.75:
                            score = max(
                                score,
                                50,
                            )

            if score > best_score:

                best_score = score
                best_column = column

        mapping[field] = (
            best_column
            if best_score >= 50
            else None
        )

    return mapping


# ============================================================
# WORKBOOK / SHEET DISCOVERY
# ============================================================

def get_excel_files():
    """
    Search recursively.

    Excludes generated output files.
    """

    files = set()

    for search_dir in SEARCH_DIRS:

        if not search_dir.exists():
            continue

        for path in search_dir.rglob("*"):

            if not path.is_file():
                continue

            if path.suffix.lower() not in {
                ".xlsx",
                ".xls",
                ".xlsm",
            }:
                continue

            # Never treat generated outputs as inputs.
            if OUTPUT_DIR in path.parents:
                continue

            if path.name.startswith(
                "~$"
            ):
                continue

            files.add(
                path.resolve()
            )

    return sorted(
        files,
        key=lambda x: str(x).lower(),
    )


def inspect_workbook(
    path,
    aliases,
    role,
):
    """
    Inspect every sheet and return candidates.

    role:
        POP
        BANK
    """

    sheets = read_excel_safely(
        path
    )

    candidates = []

    for sheet_name, raw_df in sheets.items():

        if raw_df is None:
            continue

        if raw_df.empty:
            continue

        header_row, header_hits = (
            find_best_header_row(
                raw_df,
                aliases,
            )
        )

        if header_row is None:
            continue

        header_values = (
            raw_df.iloc[
                header_row
            ]
            .tolist()
        )

        columns = []

        used = set()

        for position, value in enumerate(
            header_values
        ):

            name = (
                str(value).strip()
                if not is_blank(value)
                else f"Unnamed_{position}"
            )

            # Excel can contain duplicate header names.
            original = name
            counter = 2

            while name in used:

                name = (
                    f"{original}_{counter}"
                )

                counter += 1

            used.add(name)

            columns.append(name)

        data = raw_df.iloc[
            header_row + 1 :
        ].copy()

        data.columns = columns

        data = data.dropna(
            how="all"
        )

        if data.empty:
            continue

        mapping = build_mapping_from_columns(
            data.columns,
            aliases,
        )

        score = 0

        # ----------------------------------------------------
        # POP scoring
        # ----------------------------------------------------

        if role == "POP":

            if mapping.get(
                "case_number"
            ):
                score += 15

            if mapping.get(
                "amount"
            ):
                score += 50

            if mapping.get(
                "reference"
            ):
                score += 10

            if mapping.get(
                "customer_reference"
            ):
                score += 8

            if mapping.get(
                "account"
            ):
                score += 6

            if mapping.get(
                "customer"
            ):
                score += 6

            if mapping.get(
                "date"
            ):
                score += 4

            if mapping.get(
                "bank_name"
            ):
                score += 3

            # Amount is mandatory for POP transaction data.
            if not mapping.get(
                "amount"
            ):
                score -= 100

        # ----------------------------------------------------
        # BANK scoring
        # ----------------------------------------------------

        else:

            if mapping.get(
                "debit_amount"
            ):
                score += 35

            if mapping.get(
                "credit_amount"
            ):
                score += 35

            if mapping.get(
                "date"
            ):
                score += 10

            if mapping.get(
                "description"
            ):
                score += 8

            if mapping.get(
                "reference"
            ):
                score += 8

            if mapping.get(
                "customer_reference"
            ):
                score += 5

            if mapping.get(
                "account"
            ):
                score += 4

            if (
                not mapping.get(
                    "debit_amount"
                )
                and not mapping.get(
                    "credit_amount"
                )
            ):
                score -= 100

        candidates.append(
            {
                "path": path,
                "sheet": sheet_name,
                "data": data,
                "mapping": mapping,
                "score": score,
                "header_row": header_row,
                "header_hits": header_hits,
                "role": role,
            }
        )

    return candidates


def print_discovery_candidates(
    candidates,
):
    for candidate in candidates:

        print(
            f"\n{candidate['path']}"
            f" | sheet={candidate['sheet']}"
            f" | score={candidate['score']}"
            f" | header_row={candidate['header_row'] + 1}"
        )

        print(
            f"  mapping={candidate['mapping']}"
        )


def discover_input_files():
    """
    Identify exactly one POP transaction sheet and one bank
    transaction sheet.

    Critical difference from previous versions:

    _POP_EmailsLog.xlsx will NOT win merely because it has
    "Case Number".

    A POP candidate MUST have a usable amount column.
    """

    print(
        "\nSearching for Excel input files..."
    )

    files = get_excel_files()

    if not files:
        raise FileNotFoundError(
            "No Excel files found in configured search directories."
        )

    print(
        "\nExcel files found:"
    )

    for path in files:
        print(
            f"  - {path}"
        )

    print(
        "\nInspecting workbook/sheet structures..."
    )

    pop_candidates = []
    bank_candidates = []

    for path in files:

        pop_candidates.extend(
            inspect_workbook(
                path,
                POP_ALIASES,
                "POP",
            )
        )

        bank_candidates.extend(
            inspect_workbook(
                path,
                BANK_ALIASES,
                "BANK",
            )
        )

    print(
        "\nPOP candidates:"
    )

    print_discovery_candidates(
        pop_candidates
    )

    print(
        "\nBANK candidates:"
    )

    print_discovery_candidates(
        bank_candidates
    )

    # --------------------------------------------------------
    # POP
    # --------------------------------------------------------

    valid_pop = [
        x
        for x in pop_candidates
        if x["mapping"].get(
            "amount"
        )
        and x["score"] > 0
    ]

    if not valid_pop:

        raise ValueError(
            "\nCould not identify a POP transaction workbook/sheet "
            "with a usable amount column.\n\n"
            "The email log workbook may be present, but it is not "
            "a POP transaction table.\n"
            "The actual POP transaction workbook must contain an "
            "amount/payment amount column."
        )

    # --------------------------------------------------------
    # BANK
    # --------------------------------------------------------

    valid_bank = [
        x
        for x in bank_candidates
        if (
            x["mapping"].get(
                "debit_amount"
            )
            or x["mapping"].get(
                "credit_amount"
            )
        )
        and x["score"] > 0
    ]

    if not valid_bank:

        raise ValueError(
            "\nCould not identify a bank statement with debit/credit "
            "amount columns."
        )

    # --------------------------------------------------------
    # Prefer POP workbook that looks most like a POP file.
    # --------------------------------------------------------

    valid_pop.sort(
        key=lambda x: (
            x["score"],
            len(x["data"]),
            x["header_hits"],
        ),
        reverse=True,
    )

    valid_bank.sort(
        key=lambda x: (
            x["score"],
            len(x["data"]),
            x["header_hits"],
        ),
        reverse=True,
    )

    pop = valid_pop[0]
    bank = valid_bank[0]

    # --------------------------------------------------------
    # Prevent same sheet being selected as both.
    # --------------------------------------------------------

    if (
        pop["path"] == bank["path"]
        and pop["sheet"] == bank["sheet"]
    ):

        # Try next bank candidate.
        alternatives = [
            x
            for x in valid_bank
            if not (
                x["path"] == pop["path"]
                and x["sheet"] == pop["sheet"]
            )
        ]

        if alternatives:
            bank = alternatives[0]

        else:
            raise ValueError(
                "Could not identify separate POP and BANK transaction "
                "sources."
            )

    print(
        "\n" + "=" * 100
    )

    print(
        "SELECTED INPUT SOURCES"
    )

    print(
        "=" * 100
    )

    print(
        f"POP workbook : {pop['path']}"
    )

    print(
        f"POP sheet    : {pop['sheet']}"
    )

    print(
        f"POP score    : {pop['score']}"
    )

    print(
        f"POP rows     : {len(pop['data'])}"
    )

    print(
        f"POP mapping  : {pop['mapping']}"
    )

    print()

    print(
        f"BANK workbook: {bank['path']}"
    )

    print(
        f"BANK sheet   : {bank['sheet']}"
    )

    print(
        f"BANK score   : {bank['score']}"
    )

    print(
        f"BANK rows    : {len(bank['data'])}"
    )

    print(
        f"BANK mapping : {bank['mapping']}"
    )

    return pop, bank


# ============================================================
# PREPARE POP
# ============================================================

def prepare_pop_df(
    data,
    mapping,
    source_file,
    sheet_name,
):
    """
    Convert POP into standard fields.
    """

    rows = []

    for position, raw in data.iterrows():

        amount = safe_float(
            raw.get(
                mapping.get(
                    "amount"
                )
            )
        )

        # Ignore rows with no amount.
        if pd.isna(amount):
            continue

        def get_field(field):
            column = mapping.get(
                field
            )

            if not column:
                return None

            return raw.get(
                column
            )

        row = {

            "pop_position": position,

            "case_number": get_field(
                "case_number"
            ),

            "pop_amount": amount,

            "pop_date": parse_date(
                get_field(
                    "date"
                )
            ),

            "pop_reference": get_field(
                "reference"
            ),

            "pop_customer_reference": get_field(
                "customer_reference"
            ),

            "pop_account": get_field(
                "account"
            ),

            "pop_customer_name": get_field(
                "customer"
            ),

            "pop_bank_name": get_field(
                "bank_name"
            ),

            "pop_payment_method": get_field(
                "payment_method"
            ),

            "pop_source_file": (
                get_field(
                    "source_file"
                )
                if get_field(
                    "source_file"
                )
                else source_file
            ),

            "pop_sheet": sheet_name,
        }

        # ----------------------------------------------------
        # Normalized fields
        # ----------------------------------------------------

        row[
            "norm_reference"
        ] = compact_text(
            row["pop_reference"]
        )

        row[
            "norm_customer_reference"
        ] = compact_text(
            row["pop_customer_reference"]
        )

        row[
            "norm_account"
        ] = compact_text(
            row["pop_account"]
        )

        row[
            "norm_customer"
        ] = compact_text(
            row["pop_customer_name"]
        )

        row[
            "norm_bank"
        ] = compact_text(
            row["pop_bank_name"]
        )

        rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# PREPARE BANK
# ============================================================

def prepare_bank_df(
    data,
    mapping,
    source_file,
    sheet_name,
):
    """
    Convert bank statement into standard transaction rows.

    Bank amount is derived from:
        debit
        credit

    If both are present, the populated amount is used.

    Credit transactions are positive.
    Debit transactions are negative internally.

    For POP matching we compare absolute transaction value.
    """

    rows = []

    for position, raw in data.iterrows():

        debit = safe_float(
            raw.get(
                mapping.get(
                    "debit_amount"
                )
            )
            if mapping.get(
                "debit_amount"
            )
            else None
        )

        credit = safe_float(
            raw.get(
                mapping.get(
                    "credit_amount"
                )
            )
            if mapping.get(
                "credit_amount"
            )
            else None
        )

        # ----------------------------------------------------
        # Determine usable transaction amount.
        # ----------------------------------------------------

        if pd.notna(credit) and abs(
            credit
        ) > 0:

            bank_amount = abs(
                credit
            )

        elif pd.notna(debit) and abs(
            debit
        ) > 0:

            bank_amount = abs(
                debit
            )

        else:

            continue

        def get_field(field):
            column = mapping.get(
                field
            )

            if not column:
                return None

            return raw.get(
                column
            )

        row = {

            "bank_position": position,

            "bank_row_index": position,

            "bank_date": parse_date(
                get_field(
                    "date"
                )
            ),

            "bank_value_date": parse_date(
                get_field(
                    "value_date"
                )
            ),

            "bank_description": get_field(
                "description"
            ),

            "bank_reference": get_field(
                "reference"
            ),

            "bank_customer_reference": get_field(
                "customer_reference"
            ),

            "bank_account": get_field(
                "account"
            ),

            "bank_transaction_type": get_field(
                "transaction_type"
            ),

            "bank_debit_amount": debit,

            "bank_credit_amount": credit,

            "bank_balance": get_field(
                "balance"
            ),

            "bank_amount": bank_amount,

            "bank_name": get_field(
                "bank_name"
            ),

            "source_file": source_file,

            "bank_sheet": sheet_name,
        }

        # ----------------------------------------------------
        # Normalized bank fields
        # ----------------------------------------------------

        combined_description = " ".join(
            [
                normalize_text(
                    row["bank_description"]
                ),
                normalize_text(
                    row["bank_reference"]
                ),
                normalize_text(
                    row["bank_customer_reference"]
                ),
            ]
        )

        row[
            "norm_bank_reference"
        ] = compact_text(
            row["bank_reference"]
        )

        row[
            "norm_bank_customer_reference"
        ] = compact_text(
            row["bank_customer_reference"]
        )

        row[
            "norm_bank_account"
        ] = compact_text(
            row["bank_account"]
        )

        row[
            "norm_bank_name"
        ] = compact_text(
            row["bank_name"]
        )

        row[
            "norm_description"
        ] = compact_text(
            row["bank_description"]
        )

        row[
            "norm_combined_description"
        ] = compact_text(
            combined_description
        )

        rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# FIELD COMPARISON
# ============================================================

def exact_nonempty(
    a,
    b,
):
    a = compact_text(a)
    b = compact_text(b)

    return bool(
        a
        and b
        and a == b
    )


def strong_contains(
    a,
    b,
):
    a = compact_text(a)
    b = compact_text(b)

    if not a or not b:
        return False

    if len(a) < 5 or len(b) < 5:
        return False

    return (
        a in b
        or b in a
    )


def token_overlap(
    a,
    b,
):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    a_tokens = set(
        re.findall(
            r"[A-Z0-9]+",
            a,
        )
    )

    b_tokens = set(
        re.findall(
            r"[A-Z0-9]+",
            b,
        )
    )

    if not a_tokens or not b_tokens:
        return 0.0

    return len(
        a_tokens & b_tokens
    ) / max(
        len(a_tokens),
        len(b_tokens),
    )


# ============================================================
# SCORE CANDIDATE
# ============================================================

def score_candidate(
    pop,
    bank,
):
    """
    Evidence score.

    Score is deliberately evidence based.

    A date by itself cannot create a match.

    Reference / customer reference carry the most weight.
    """

    score = 0.0

    reasons = []

    evidence = {}

    # --------------------------------------------------------
    # AMOUNT
    # --------------------------------------------------------

    amount_difference = abs(
        float(
            pop["pop_amount"]
        )
        - float(
            bank["bank_amount"]
        )
    )

    if amount_difference == 0:
        score += 30
        reasons.append(
            "AMOUNT_EXACT"
        )

    elif amount_difference <= AMOUNT_TOLERANCE:
        score += 18
        reasons.append(
            "AMOUNT_NEAR"
        )

    else:
        # Candidate should normally never reach here.
        score += max(
            0,
            10
            - amount_difference,
        )

    evidence[
        "amount_difference"
    ] = amount_difference

    # --------------------------------------------------------
    # REFERENCE
    # --------------------------------------------------------

    if exact_nonempty(
        pop["pop_reference"],
        bank["bank_reference"],
    ):

        score += 40

        reasons.append(
            "REFERENCE_EXACT"
        )

        evidence[
            "reference"
        ] = "EXACT"

    elif strong_contains(
        pop["pop_reference"],
        bank["bank_reference"],
    ):

        score += 30

        reasons.append(
            "REFERENCE_STRONG"
        )

        evidence[
            "reference"
        ] = "STRONG"

    else:

        evidence[
            "reference"
        ] = "NONE"

    # --------------------------------------------------------
    # CUSTOMER REFERENCE
    # --------------------------------------------------------

    if exact_nonempty(
        pop["pop_customer_reference"],
        bank["bank_customer_reference"],
    ):

        score += 38

        reasons.append(
            "CUSTOMER_REFERENCE_EXACT"
        )

        evidence[
            "customer_reference"
        ] = "EXACT"

    elif strong_contains(
        pop["pop_customer_reference"],
        bank["bank_customer_reference"],
    ):

        score += 28

        reasons.append(
            "CUSTOMER_REFERENCE_STRONG"
        )

        evidence[
            "customer_reference"
        ] = "STRONG"

    else:

        evidence[
            "customer_reference"
        ] = "NONE"

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    if exact_nonempty(
        pop["pop_account"],
        bank["bank_account"],
    ):

        score += 25

        reasons.append(
            "ACCOUNT_EXACT"
        )

        evidence[
            "account"
        ] = "EXACT"

    elif strong_contains(
        pop["pop_account"],
        bank["bank_account"],
    ):

        score += 18

        reasons.append(
            "ACCOUNT_STRONG"
        )

        evidence[
            "account"
        ] = "STRONG"

    else:

        evidence[
            "account"
        ] = "NONE"

    # --------------------------------------------------------
    # CUSTOMER NAME vs DESCRIPTION
    # --------------------------------------------------------

    customer_overlap = token_overlap(
        pop["pop_customer_name"],
        bank["bank_description"],
    )

    if customer_overlap >= 0.80:

        score += 25

        reasons.append(
            "CUSTOMER_EXACT"
        )

        evidence[
            "customer"
        ] = "EXACT"

    elif customer_overlap >= 0.50:

        score += 15

        reasons.append(
            "CUSTOMER_STRONG"
        )

        evidence[
            "customer"
        ] = "STRONG"

    else:

        evidence[
            "customer"
        ] = "NONE"

    # --------------------------------------------------------
    # BANK NAME
    # --------------------------------------------------------

    if exact_nonempty(
        pop["pop_bank_name"],
        bank["bank_name"],
    ):

        score += 18

        reasons.append(
            "BANK_EXACT"
        )

        evidence[
            "bank"
        ] = "EXACT"

    elif strong_contains(
        pop["pop_bank_name"],
        bank["bank_name"],
    ):

        score += 12

        reasons.append(
            "BANK_STRONG"
        )

        evidence[
            "bank"
        ] = "STRONG"

    else:

        evidence[
            "bank"
        ] = "NONE"

    # --------------------------------------------------------
    # SOURCE FILE
    # --------------------------------------------------------

    if pop["pop_source_file"]:

        pop_source = compact_text(
            pop["pop_source_file"]
        )

        bank_source = compact_text(
            bank["source_file"]
        )

        if (
            pop_source
            and bank_source
            and (
                pop_source in bank_source
                or bank_source in pop_source
            )
        ):

            score += 15

            reasons.append(
                "SOURCE_FILE_EXACT"
            )

    # --------------------------------------------------------
    # PAYMENT METHOD / TRANSACTION TYPE
    # --------------------------------------------------------

    payment_method = normalize_text(
        pop["pop_payment_method"]
    )

    transaction_type = normalize_text(
        bank["bank_transaction_type"]
    )

    if (
        payment_method
        and transaction_type
    ):

        if (
            payment_method in transaction_type
            or transaction_type in payment_method
        ):

            score += 8

            reasons.append(
                "PAYMENT_METHOD_SUPPORT"
            )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_diff = date_difference_days(
        pop["pop_date"],
        bank["bank_date"],
    )

    evidence[
        "date_difference_days"
    ] = date_diff

    if pd.notna(date_diff):

        if date_diff == 0:

            score += 18

            reasons.append(
                "DATE_EXACT"
            )

        elif date_diff <= 1:

            score += 12

            reasons.append(
                "DATE_WITHIN_1_DAY"
            )

        elif date_diff <= 3:

            score += 7

            reasons.append(
                "DATE_WITHIN_3_DAYS"
            )

        elif date_diff <= DATE_WINDOW_DAYS:

            score += 2

            reasons.append(
                "DATE_WITHIN_WINDOW"
            )

        else:

            # Important:
            # Do not massively punish date mismatch.
            #
            # Bank posting dates can differ from payment dates.
            #
            # The decision layer handles serious date conflicts.
            reasons.append(
                "DATE_OUTSIDE_WINDOW"
            )

    # --------------------------------------------------------
    # INDEPENDENT SUPPORT
    # --------------------------------------------------------

    independent_support = any(
        x in reasons
        for x in [
            "REFERENCE_EXACT",
            "REFERENCE_STRONG",
            "CUSTOMER_REFERENCE_EXACT",
            "CUSTOMER_REFERENCE_STRONG",
            "ACCOUNT_EXACT",
            "ACCOUNT_STRONG",
            "CUSTOMER_EXACT",
            "CUSTOMER_STRONG",
            "BANK_EXACT",
            "BANK_STRONG",
            "SOURCE_FILE_EXACT",
        ]
    )

    strong_identity = any(
        x in reasons
        for x in [
            "REFERENCE_EXACT",
            "CUSTOMER_REFERENCE_EXACT",
            "ACCOUNT_EXACT",
        ]
    )

    return {
        "score": round(
            score,
            4,
        ),

        "amount_difference": (
            amount_difference
        ),

        "date_difference_days": (
            date_diff
        ),

        "reasons": reasons,

        "independent_support": (
            independent_support
        ),

        "strong_identity": (
            strong_identity
        ),

        "evidence": evidence,
    }


# ============================================================
# AMOUNT CANDIDATES
# ============================================================

def get_amount_candidates(
    pop_amount,
    bank_df,
):
    """
    AMOUNT FIRST.

    EXACT candidates are always preferred.

    If none exist, search near amount.
    """

    if bank_df.empty:
        return (
            bank_df.copy(),
            "NONE",
        )

    amounts = bank_df[
        "bank_amount"
    ].astype(float)

    exact_mask = np.isclose(
        amounts,
        float(pop_amount),
        atol=0.005,
        rtol=0,
    )

    exact = bank_df[
        exact_mask
    ].copy()

    if not exact.empty:

        exact[
            "amount_difference"
        ] = (
            exact[
                "bank_amount"
            ].astype(float)
            - float(pop_amount)
        ).abs()

        exact = exact.sort_values(
            "amount_difference"
        )

        return (
            exact.head(
                MAX_CANDIDATES_PER_POP
            ),
            "EXACT",
        )

    near_mask = (
        amounts
        .sub(
            float(pop_amount)
        )
        .abs()
        <= AMOUNT_TOLERANCE
    )

    near = bank_df[
        near_mask
    ].copy()

    if near.empty:

        return (
            near,
            "NONE",
        )

    near[
        "amount_difference"
    ] = (
        near[
            "bank_amount"
        ].astype(float)
        - float(pop_amount)
    ).abs()

    near = near.sort_values(
        "amount_difference"
    )

    return (
        near.head(
            MAX_CANDIDATES_PER_POP
        ),
        "NEAR",
    )


# ============================================================
# CANDIDATE RANKING
# ============================================================

def rank_candidates(
    candidates,
):
    if not candidates:
        return []

    return sorted(
        candidates,
        key=lambda x: (
            -float(
                x["score"]
            ),

            float(
                x["amount_difference"]
            )
            if pd.notna(
                x["amount_difference"]
            )
            else math.inf,

            float(
                x["date_difference_days"]
            )
            if pd.notna(
                x["date_difference_days"]
            )
            else math.inf,

            x["bank_row_index"],
        ),
    )


# ============================================================
# MATCH ONE POP ROW
# ============================================================

def match_one(
    pop,
    bank_df,
    locked_rows,
):
    base = {

        "case_number": pop[
            "case_number"
        ],

        "pop_account": pop[
            "pop_account"
        ],

        "pop_amount": pop[
            "pop_amount"
        ],

        "pop_date": pop[
            "pop_date"
        ],

        "pop_reference": pop[
            "pop_reference"
        ],

        "pop_customer_reference": pop[
            "pop_customer_reference"
        ],

        "pop_customer_name": pop[
            "pop_customer_name"
        ],

        "pop_bank_name": pop[
            "pop_bank_name"
        ],

        "pop_payment_method": pop[
            "pop_payment_method"
        ],

        "pop_source_file": pop[
            "pop_source_file"
        ],

        "pop_sheet": pop[
            "pop_sheet"
        ],
    }

    # ========================================================
    # STEP 1
    # AMOUNT FIRST
    # ========================================================

    amount_candidates, amount_mode = (
        get_amount_candidates(
            pop["pop_amount"],
            bank_df,
        )
    )

    if amount_candidates.empty:

        return (
            {
                **base,

                "status": "NO_MATCH",

                "match_reason": (
                    "NO_AMOUNT_CANDIDATE"
                ),

                "score": np.nan,

                "score_gap": np.nan,

                "candidate_count": 0,

                "source_mode": (
                    "AMOUNT_FIRST"
                ),

                "bank_row_index": np.nan,
            },

            [],
        )

    # ========================================================
    # STEP 2
    # SCORE ALL AMOUNT CANDIDATES
    # ========================================================

    rows = []

    for _, bank_series in (
        amount_candidates.iterrows()
    ):

        bank = bank_series.to_dict()

        scored = score_candidate(
            pop,
            bank,
        )

        row = {

            **base,

            "bank_row_index": bank[
                "bank_row_index"
            ],

            "bank_date": bank[
                "bank_date"
            ],

            "bank_value_date": bank[
                "bank_value_date"
            ],

            "bank_description": bank[
                "bank_description"
            ],

            "bank_reference": bank[
                "bank_reference"
            ],

            "bank_customer_reference": bank[
                "bank_customer_reference"
            ],

            "bank_account": bank[
                "bank_account"
            ],

            "bank_transaction_type": bank[
                "bank_transaction_type"
            ],

            "bank_debit_amount": bank[
                "bank_debit_amount"
            ],

            "bank_credit_amount": bank[
                "bank_credit_amount"
            ],

            "bank_balance": bank[
                "bank_balance"
            ],

            "bank_amount": bank[
                "bank_amount"
            ],

            "bank_name": bank[
                "bank_name"
            ],

            "source_file": bank[
                "source_file"
            ],

            "bank_sheet": bank[
                "bank_sheet"
            ],

            "amount_mode": amount_mode,

            "score": scored[
                "score"
            ],

            "amount_difference": scored[
                "amount_difference"
            ],

            "date_difference_days": scored[
                "date_difference_days"
            ],

            "reasons": scored[
                "reasons"
            ],

            "independent_support": scored[
                "independent_support"
            ],

            "strong_identity": scored[
                "strong_identity"
            ],

            "already_locked": (
                bank[
                    "bank_row_index"
                ]
                in locked_rows
            ),

            "status": "",

            "match_reason": "",

            "score_gap": np.nan,

            "candidate_rank": np.nan,

            "is_selected": False,
        }

        rows.append(row)

    # ========================================================
    # ONLY UNUSED BANK ROWS CAN BE SELECTED
    # ========================================================

    usable = [
        row
        for row in rows
        if not row[
            "already_locked"
        ]
    ]

    if not usable:

        ranked = rank_candidates(
            rows
        )

        best_locked = ranked[0]

        for row in rows:

            row[
                "status"
            ] = "NO_MATCH"

            row[
                "match_reason"
            ] = (
                "ALL_AMOUNT_CANDIDATES_ALREADY_USED"
            )

        return (
            {
                **base,

                "status": "NO_MATCH",

                "match_reason": (
                    "ALL_AMOUNT_CANDIDATES_ALREADY_USED"
                ),

                "score": best_locked[
                    "score"
                ],

                "score_gap": np.nan,

                "candidate_count": len(
                    rows
                ),

                "source_mode": (
                    "AMOUNT_FIRST"
                ),

                "bank_row_index": (
                    best_locked[
                        "bank_row_index"
                    ]
                ),

                "bank_amount": (
                    best_locked[
                        "bank_amount"
                    ]
                ),

                "amount_difference": (
                    best_locked[
                        "amount_difference"
                    ]
                ),

                "amount_mode": amount_mode,

                "bank_date": (
                    best_locked[
                        "bank_date"
                    ]
                ),

                "date_difference_days": (
                    best_locked[
                        "date_difference_days"
                    ]
                ),
            },
            rows,
        )

    # ========================================================
    # RANK USABLE CANDIDATES
    # ========================================================

    ranked = rank_candidates(
        usable
    )

    best = ranked[0]

    if len(ranked) > 1:

        second = ranked[1]

        score_gap = (
            best["score"]
            - second["score"]
        )

    else:

        score_gap = np.inf

    # ========================================================
    # EVIDENCE FLAGS
    # ========================================================

    reasons = best[
        "reasons"
    ]

    reference_hit = any(
        x in reasons
        for x in [
            "REFERENCE_EXACT",
            "REFERENCE_STRONG",
        ]
    )

    customer_reference_hit = any(
        x in reasons
        for x in [
            "CUSTOMER_REFERENCE_EXACT",
            "CUSTOMER_REFERENCE_STRONG",
        ]
    )

    customer_hit = any(
        x in reasons
        for x in [
            "CUSTOMER_EXACT",
            "CUSTOMER_STRONG",
        ]
    )

    account_hit = any(
        x in reasons
        for x in [
            "ACCOUNT_EXACT",
            "ACCOUNT_STRONG",
        ]
    )

    bank_hit = any(
        x in reasons
        for x in [
            "BANK_EXACT",
            "BANK_STRONG",
        ]
    )

    source_hit = any(
        x in reasons
        for x in [
            "SOURCE_FILE_EXACT",
            "SOURCE_FILE_STRONG",
        ]
    )

    identity_hit = (
        reference_hit
        or customer_reference_hit
        or customer_hit
        or account_hit
        or bank_hit
        or source_hit
    )

    strong_identity = (
        reference_hit
        or customer_reference_hit
        or account_hit
    )

    # ========================================================
    # DATE CONFLICT
    # ========================================================

    date_conflict = False

    if (
        not pd.isna(
            pop["pop_date"]
        )
        and pd.notna(
            best["date_difference_days"]
        )
    ):

        if (
            best[
                "date_difference_days"
            ]
            > DATE_WINDOW_DAYS
        ):

            date_conflict = True

    # ========================================================
    # DECISION
    # ========================================================

    status = "AMBIGUOUS"
    match_reason = ""

    # ========================================================
    # EXACT AMOUNT
    # ========================================================

    if amount_mode == "EXACT":

        # ----------------------------------------------------
        # ONE AVAILABLE EXACT AMOUNT
        # ----------------------------------------------------

        if len(ranked) == 1:

            # Exact amount alone is NOT automatically enough.
            #
            # However, a unique exact amount with no contradictory
            # information is a valid match.
            #
            # Strong identity gives additional confidence.

            if (
                best["score"]
                >= MATCH_THRESHOLD
                and not date_conflict
            ):

                status = "MATCHED"

                if reference_hit:

                    match_reason = (
                        "EXACT_AMOUNT_REFERENCE_UNIQUE"
                    )

                elif customer_reference_hit:

                    match_reason = (
                        "EXACT_AMOUNT_CUSTOMER_REFERENCE_UNIQUE"
                    )

                elif account_hit:

                    match_reason = (
                        "EXACT_AMOUNT_ACCOUNT_UNIQUE"
                    )

                elif customer_hit:

                    match_reason = (
                        "EXACT_AMOUNT_CUSTOMER_UNIQUE"
                    )

                elif source_hit:

                    match_reason = (
                        "EXACT_AMOUNT_SOURCE_UNIQUE"
                    )

                elif bank_hit:

                    match_reason = (
                        "EXACT_AMOUNT_BANK_UNIQUE"
                    )

                else:

                    match_reason = (
                        "EXACT_AMOUNT_UNIQUE"
                    )

            elif date_conflict:

                status = "AMBIGUOUS"

                match_reason = (
                    "EXACT_AMOUNT_DATE_CONFLICT"
                )

            else:

                status = "AMBIGUOUS"

                match_reason = (
                    "EXACT_AMOUNT_BUT_WEAK_SUPPORT"
                )

        # ----------------------------------------------------
        # MULTIPLE EXACT AMOUNTS
        # ----------------------------------------------------

        else:

            # A duplicate amount must be separated by evidence.
            #
            # Strong identity is preferred.
            #
            # Score gap is mandatory.
            #
            # This prevents:
            #
            #   POP = 1000
            #   BANK = 1000
            #   BANK = 1000
            #
            # from being arbitrarily matched.

            if (
                best["score"]
                >= MATCH_THRESHOLD
                and score_gap
                >= MIN_SCORE_GAP
                and identity_hit
                and not date_conflict
            ):

                status = "MATCHED"

                if reference_hit:

                    match_reason = (
                        "EXACT_AMOUNT_REFERENCE_CLEAR_WINNER"
                    )

                elif customer_reference_hit:

                    match_reason = (
                        "EXACT_AMOUNT_CUSTOMER_REFERENCE_CLEAR_WINNER"
                    )

                elif account_hit:

                    match_reason = (
                        "EXACT_AMOUNT_ACCOUNT_CLEAR_WINNER"
                    )

                elif customer_hit:

                    match_reason = (
                        "EXACT_AMOUNT_CUSTOMER_CLEAR_WINNER"
                    )

                elif source_hit:

                    match_reason = (
                        "EXACT_AMOUNT_SOURCE_CLEAR_WINNER"
                    )

                elif bank_hit:

                    match_reason = (
                        "EXACT_AMOUNT_BANK_CLEAR_WINNER"
                    )

                else:

                    match_reason = (
                        "EXACT_AMOUNT_CLEAR_WINNER"
                    )

            elif date_conflict:

                status = "AMBIGUOUS"

                match_reason = (
                    "MULTIPLE_EXACT_AMOUNT_DATE_CONFLICT"
                )

            else:

                status = "AMBIGUOUS"

                match_reason = (
                    "MULTIPLE_EXACT_AMOUNT_CANDIDATES"
                )

    # ========================================================
    # NEAR AMOUNT
    # ========================================================

    else:

        # Near amount is intentionally harder to match.

        if (
            best["score"]
            >= NEAR_MATCH_THRESHOLD
            and identity_hit
            and (
                len(ranked) == 1
                or score_gap
                >= MIN_SCORE_GAP
            )
        ):

            if date_conflict:

                status = "AMBIGUOUS"

                match_reason = (
                    "NEAR_AMOUNT_DATE_CONFLICT"
                )

            else:

                status = "NEAR_AMOUNT"

                if reference_hit:

                    match_reason = (
                        "NEAR_AMOUNT_REFERENCE_SUPPORT"
                    )

                elif customer_reference_hit:

                    match_reason = (
                        "NEAR_AMOUNT_CUSTOMER_REFERENCE_SUPPORT"
                    )

                elif account_hit:

                    match_reason = (
                        "NEAR_AMOUNT_ACCOUNT_SUPPORT"
                    )

                elif customer_hit:

                    match_reason = (
                        "NEAR_AMOUNT_CUSTOMER_SUPPORT"
                    )

                elif source_hit:

                    match_reason = (
                        "NEAR_AMOUNT_SOURCE_SUPPORT"
                    )

                elif bank_hit:

                    match_reason = (
                        "NEAR_AMOUNT_BANK_SUPPORT"
                    )

                else:

                    match_reason = (
                        "NEAR_AMOUNT_STRONG_SUPPORT"
                    )

        elif len(ranked) > 1:

            status = "AMBIGUOUS"

            match_reason = (
                "MULTIPLE_NEAR_AMOUNT_CANDIDATES"
            )

        else:

            status = "NO_MATCH"

            match_reason = (
                "NEAR_AMOUNT_WITHOUT_STRONG_SUPPORT"
            )

    # ========================================================
    # COPY DECISION TO BEST ROW
    # ========================================================

    best_idx = best[
        "bank_row_index"
    ]

    for row in rows:

        if (
            row[
                "bank_row_index"
            ]
            == best_idx
        ):

            row[
                "status"
            ] = status

            row[
                "match_reason"
            ] = match_reason

            row[
                "score_gap"
            ] = (
                score_gap
                if np.isfinite(
                    score_gap
                )
                else np.nan
            )

    # ========================================================
    # RANK ALL CANDIDATES
    # ========================================================

    ranked_all = rank_candidates(
        rows
    )

    for rank, row in enumerate(
        ranked_all,
        start=1,
    ):

        row[
            "candidate_rank"
        ] = rank

        row[
            "is_selected"
        ] = (
            row[
                "bank_row_index"
            ]
            == best_idx
            and status
            in {
                "MATCHED",
                "NEAR_AMOUNT",
            }
            and not row[
                "already_locked"
            ]
        )

    # ========================================================
    # RESULT
    # ========================================================

    result = {

        **base,

        "status": status,

        "match_reason": match_reason,

        "score": best[
            "score"
        ],

        "score_gap": (
            score_gap
            if np.isfinite(
                score_gap
            )
            else np.nan
        ),

        "candidate_count": len(
            rows
        ),

        "source_mode": (
            "AMOUNT_FIRST"
        ),

        "bank_row_index": best[
            "bank_row_index"
        ],

        "bank_amount": best[
            "bank_amount"
        ],

        "amount_difference": best[
            "amount_difference"
        ],

        "amount_mode": amount_mode,

        "bank_date": best[
            "bank_date"
        ],

        "date_difference_days": best[
            "date_difference_days"
        ],

        "bank_value_date": best[
            "bank_value_date"
        ],

        "bank_description": best[
            "bank_description"
        ],

        "bank_reference": best[
            "bank_reference"
        ],

        "bank_customer_reference": best[
            "bank_customer_reference"
        ],

        "bank_account": best[
            "bank_account"
        ],

        "bank_transaction_type": best[
            "bank_transaction_type"
        ],

        "bank_debit_amount": best[
            "bank_debit_amount"
        ],

        "bank_credit_amount": best[
            "bank_credit_amount"
        ],

        "bank_balance": best[
            "bank_balance"
        ],

        "bank_name": best[
            "bank_name"
        ],

        "source_file": best[
            "source_file"
        ],

        "bank_sheet": best[
            "bank_sheet"
        ],

        "reasons": best[
            "reasons"
        ],
    }

    return (
        result,
        ranked_all,
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_pop(
    pop_df,
):
    if pop_df.empty:
        raise ValueError(
            "POP contains no usable transaction rows."
        )

    if "pop_amount" not in pop_df.columns:
        raise ValueError(
            "POP amount field was not prepared."
        )

    usable = pop_df[
        "pop_amount"
    ].notna().sum()

    if usable == 0:
        raise ValueError(
            "POP contains no usable numeric amounts."
        )


def validate_bank(
    bank_df,
):
    if bank_df.empty:
        raise ValueError(
            "Bank statement contains no usable transactions."
        )

    if "bank_amount" not in bank_df.columns:
        raise ValueError(
            "Bank amount field was not prepared."
        )

    usable = bank_df[
        "bank_amount"
    ].notna().sum()

    if usable == 0:
        raise ValueError(
            "Bank statement contains no usable amounts."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 100
    )

    print(
        "POP -> BANK MATCHING ENGINE V8"
    )

    print(
        "=" * 100
    )

    print(
        "\nMATCHING ORDER:"
    )

    print(
        "  1. AMOUNT FIRST"
    )

    print(
        "  2. REFERENCE / CUSTOMER REFERENCE"
    )

    print(
        "  3. ACCOUNT"
    )

    print(
        "  4. CUSTOMER / DESCRIPTION"
    )

    print(
        "  5. BANK / SOURCE / PAYMENT METHOD"
    )

    print(
        "  6. DATE AS SUPPORTING EVIDENCE"
    )

    print(
        "  7. ONE BANK TRANSACTION = ONE MATCH"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "  Weak evidence is NOT force-matched."
    )

    print(
        "  Duplicate amounts require separation."
    )

    print(
        "  Near amounts require stronger evidence."
    )

    # ========================================================
    # OUTPUT DIR
    # ========================================================

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # DISCOVER
    # ========================================================

    pop_source, bank_source = (
        discover_input_files()
    )

    # ========================================================
    # PREPARE
    # ========================================================

    print(
        "\nPreparing POP transactions..."
    )

    pop_df = prepare_pop_df(
        pop_source["data"],
        pop_source["mapping"],
        str(
            pop_source["path"]
        ),
        pop_source["sheet"],
    )

    print(
        f"Usable POP rows: {len(pop_df)}"
    )

    validate_pop(
        pop_df
    )

    print(
        "\nPreparing bank transactions..."
    )

    bank_df = prepare_bank_df(
        bank_source["data"],
        bank_source["mapping"],
        str(
            bank_source["path"]
        ),
        bank_source["sheet"],
    )

    print(
        f"Usable bank rows: {len(bank_df)}"
    )

    validate_bank(
        bank_df
    )

    # ========================================================
    # MATCH
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "MATCHING"
    )

    print(
        "=" * 100
    )

    matches = []
    candidates = []

    locked_rows = set()

    total_pop = len(
        pop_df
    )

    for position, (
        _,
        pop,
    ) in enumerate(
        pop_df.iterrows(),
        start=1,
    ):

        best, rows = match_one(
            pop,
            bank_df,
            locked_rows,
        )

        # ----------------------------------------------------
        # LOCK ONLY CONFIDENT MATCHES.
        # ----------------------------------------------------

        if best.get(
            "status"
        ) in {
            "MATCHED",
            "NEAR_AMOUNT",
        }:

            bank_idx = best.get(
                "bank_row_index"
            )

            if pd.notna(
                bank_idx
            ):

                locked_rows.add(
                    bank_idx
                )

        matches.append(
            best
        )

        candidates.extend(
            rows
        )

        print(
            f"[{position:>4}/{total_pop}] "
            f"CASE={best.get('case_number')} "
            f"| {best.get('status', ''):<10} "
            f"| {best.get('match_reason', '')}"
        )

    # ========================================================
    # DATAFRAMES
    # ========================================================

    matches_df = pd.DataFrame(
        matches
    )

    candidates_df = pd.DataFrame(
        candidates
    )

    # ========================================================
    # SAVE MATCH OUTPUT
    # ========================================================

    match_cols = [

        "case_number",

        "status",

        "match_reason",

        "score",

        "score_gap",

        "candidate_count",

        "source_mode",

        "pop_amount",

        "pop_date",

        "pop_reference",

        "pop_customer_reference",

        "pop_customer_name",

        "pop_account",

        "pop_bank_name",

        "pop_payment_method",

        "pop_source_file",

        "pop_sheet",

        "bank_amount",

        "amount_difference",

        "amount_mode",

        "bank_date",

        "bank_value_date",

        "date_difference_days",

        "bank_description",

        "bank_reference",

        "bank_customer_reference",

        "bank_account",

        "bank_transaction_type",

        "bank_debit_amount",

        "bank_credit_amount",

        "bank_balance",

        "bank_name",

        "source_file",

        "bank_sheet",

        "bank_row_index",

        "reasons",
    ]

    match_cols = [
        col
        for col in match_cols
        if col in matches_df.columns
    ]

    remaining = [
        col
        for col in matches_df.columns
        if col not in match_cols
    ]

    matches_df = matches_df[
        match_cols
        + remaining
    ]

    # ========================================================
    # CANDIDATE OUTPUT
    # ========================================================

    if not candidates_df.empty:

        candidate_cols = [

            "case_number",

            "candidate_rank",

            "is_selected",

            "already_locked",

            "status",

            "match_reason",

            "score",

            "score_gap",

            "source_mode",

            "amount_mode",

            "pop_amount",

            "pop_date",

            "pop_reference",

            "pop_customer_reference",

            "pop_customer_name",

            "pop_account",

            "pop_bank_name",

            "pop_payment_method",

            "pop_source_file",

            "bank_amount",

            "amount_difference",

            "bank_date",

            "bank_value_date",

            "date_difference_days",

            "bank_description",

            "bank_reference",

            "bank_customer_reference",

            "bank_account",

            "bank_transaction_type",

            "bank_debit_amount",

            "bank_credit_amount",

            "bank_balance",

            "bank_name",

            "source_file",

            "bank_sheet",

            "bank_row_index",

            "reasons",
        ]

        candidate_cols = [
            col
            for col in candidate_cols
            if col in candidates_df.columns
        ]

        remaining = [
            col
            for col in candidates_df.columns
            if col not in candidate_cols
        ]

        candidates_df = candidates_df[
            candidate_cols
            + remaining
        ]

    # ========================================================
    # WRITE OUTPUT
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "SAVING OUTPUT"
    )

    print(
        "=" * 100
    )

    matches_df.to_excel(
        MATCH_OUTPUT,
        index=False,
    )

    candidates_df.to_excel(
        CANDIDATE_OUTPUT,
        index=False,
    )

    print(
        f"\nMatch output:"
    )

    print(
        MATCH_OUTPUT
    )

    print(
        f"\nCandidate output:"
    )

    print(
        CANDIDATE_OUTPUT
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL MATCHING SUMMARY"
    )

    print(
        "=" * 100
    )

    total = len(
        matches_df
    )

    counts = (
        matches_df[
            "status"
        ]
        .value_counts()
    )

    for status in [
        "MATCHED",
        "NEAR_AMOUNT",
        "AMBIGUOUS",
        "NO_MATCH",
    ]:

        count = int(
            counts.get(
                status,
                0,
            )
        )

        percentage = (
            count
            / total
            * 100
            if total
            else 0
        )

        print(
            f"{status:<15}"
            f"{count:>6} "
            f"({percentage:>7.2f}%)"
        )

    strict_matches = int(
        (
            matches_df[
                "status"
            ]
            == "MATCHED"
        ).sum()
    )

    near_matches = int(
        (
            matches_df[
                "status"
            ]
            == "NEAR_AMOUNT"
        ).sum()
    )

    usable_matches = (
        strict_matches
        + near_matches
    )

    ambiguous = int(
        (
            matches_df[
                "status"
            ]
            == "AMBIGUOUS"
        ).sum()
    )

    no_match = int(
        (
            matches_df[
                "status"
            ]
            == "NO_MATCH"
        ).sum()
    )

    print(
        "\n"
        + "=" * 100
    )

    print(
        "MATCHING PERCENTAGES"
    )

    print(
        "=" * 100
    )

    def pct(value):
        return (
            value
            / total
            * 100
            if total
            else 0
        )

    print(
        f"Strict MATCHED % : {pct(strict_matches):>7.2f}%"
    )

    print(
        f"NEAR_AMOUNT %    : {pct(near_matches):>7.2f}%"
    )

    print(
        f"Usable MATCH %   : {pct(usable_matches):>7.2f}%"
    )

    print(
        f"AMBIGUOUS %      : {pct(ambiguous):>7.2f}%"
    )

    print(
        f"NO_MATCH %       : {pct(no_match):>7.2f}%"
    )

    print(
        f"\nUnique bank rows locked: "
        f"{len(locked_rows)}"
    )

    print(
        f"Candidate rows generated: "
        f"{len(candidates_df)}"
    )

    # ========================================================
    # REASON SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "MATCH REASONS"
    )

    print(
        "=" * 100
    )

    print(
        matches_df[
            "match_reason"
        ]
        .value_counts()
        .to_string()
    )

    # ========================================================
    # AMOUNT SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "AMOUNT MODE SUMMARY"
    )

    print(
        "=" * 100
    )

    if (
        "amount_mode"
        in matches_df.columns
    ):

        print(
            matches_df[
                "amount_mode"
            ]
            .value_counts()
            .to_string()
        )

    # ========================================================
    # SELECTED MATCHES
    # ========================================================

    selected = matches_df[
        matches_df[
            "status"
        ].isin(
            [
                "MATCHED",
                "NEAR_AMOUNT",
            ]
        )
    ]

    print(
        "\n"
        + "=" * 100
    )

    print(
        "SELECTED MATCHES"
    )

    print(
        "=" * 100
    )

    if selected.empty:

        print(
            "No selected matches."
        )

    else:

        display_cols = [

            "case_number",

            "status",

            "match_reason",

            "score",

            "score_gap",

            "candidate_count",

            "pop_amount",

            "bank_amount",

            "amount_difference",

            "pop_reference",

            "bank_reference",

            "pop_customer_reference",

            "bank_customer_reference",

            "pop_customer_name",

            "bank_description",

            "pop_account",

            "bank_account",

            "pop_date",

            "bank_date",

            "date_difference_days",

            "bank_row_index",

            "reasons",
        ]

        display_cols = [
            col
            for col in display_cols
            if col in selected.columns
        ]

        print(
            selected[
                display_cols
            ].to_string(
                index=False
            )
        )

    # ========================================================
    # COMPLETE
    # ========================================================

    print(
        "\n"
        + "=" * 100
    )

    print(
        "PROCESS COMPLETE"
    )

    print(
        "=" * 100
    )

    print(
        "\nMatching logic:"
    )

    print(
        "  1. Discover actual transaction sheets"
    )

    print(
        "  2. Detect headers automatically"
    )

    print(
        "  3. Normalize POP and bank columns"
    )

    print(
        "  4. AMOUNT FIRST"
    )

    print(
        "  5. Exact amount candidates first"
    )

    print(
        "  6. Reference / customer reference"
    )

    print(
        "  7. Account"
    )

    print(
        "  8. Customer / description"
    )

    print(
        "  9. Bank / source / payment method"
    )

    print(
        " 10. Date as supporting evidence"
    )

    print(
        " 11. Candidate score separation"
    )

    print(
        " 12. One-to-one bank transaction locking"
    )

    print(
        "\nNo weak candidate is automatically forced into MATCHED."
    )

    print(
        "\nOutput files:"
    )

    print(
        MATCH_OUTPUT
    )

    print(
        CANDIDATE_OUTPUT
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n"
            + "=" * 100
        )

        print(
            "PROCESS FAILED"
        )

        print(
            "=" * 100
        )

        print(
            f"\n{type(exc).__name__}: {exc}"
        )

        print(
            "\nFull traceback:"
        )

        traceback.print_exc()

        raise
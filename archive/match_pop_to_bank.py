from pathlib import Path
import re
import math
import pandas as pd
import numpy as np


# ============================================================
# CONFIG
# ============================================================

PROJECT_DIR = Path(r"D:\Disha_Workarea\pop_process")

POP_INPUT = Path(r"D:\AUG-bank_files\normalization_input\AUG_POP_matching_input.xlsx")
BANK_INPUT = Path(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

OUTPUT_DIR = PROJECT_DIR / "data" / "output"

MATCH_OUTPUT = OUTPUT_DIR / "POP_bank_match_results.xlsx"
AUDIT_OUTPUT = OUTPUT_DIR / "POP_bank_candidate_audit.xlsx"
DIAGNOSTIC_OUTPUT = OUTPUT_DIR / "POP_bank_diagnostic.txt"


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


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return ""

    value = str(value).strip().upper()

    value = re.sub(r"\s+", " ", value)

    return value


def normalize_alnum(value):
    value = clean_text(value)
    return re.sub(r"[^A-Z0-9]", "", value)


def normalize_account(value):
    value = normalize_alnum(value)

    # Keep account numbers as strings.
    return value


def normalize_name(value):
    value = clean_text(value)

    value = re.sub(r"[^A-Z0-9 ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def name_tokens(value):
    value = normalize_name(value)

    if not value:
        return set()

    return {
        x for x in value.split()
        if len(x) >= 2
    }


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan

        return float(value)

    except Exception:
        return np.nan


def amount_from_bank(row):
    debit = safe_float(row.get("debit_amount"))
    credit = safe_float(row.get("credit_amount"))

    # Normalized bank data should contain exactly one side.
    if pd.notna(credit) and abs(credit) > 0:
        return abs(credit)

    if pd.notna(debit) and abs(debit) > 0:
        return abs(debit)

    return np.nan


def normalize_date(value):
    if pd.isna(value):
        return pd.NaT

    return pd.to_datetime(value, errors="coerce")


# ============================================================
# BANK DETECTION
# ============================================================

def detect_bank_from_filename(filename):

    name = filename.upper()

    if name.startswith("FAB"):
        return "FAB"

    if name.startswith("ADCB"):
        return "ADCB"

    if name.startswith("CBD"):
        return "CBD"

    if name.startswith("MASHREQ"):
        return "MASHREQ"

    if name.startswith("NBO"):
        return "NBO"

    if name.startswith("UAB"):
        return "UAB"

    if name.startswith("UBL"):
        return "UBL"

    if name.startswith("AJMAN"):
        return "AJMAN"

    if name.startswith("CBI"):
        return "CBI"

    if name.startswith("ABK"):
        return "ABK"

    return "UNKNOWN"


# ============================================================
# BANK FILE READER
# ============================================================

def read_bank_file(path):

    suffix = path.suffix.lower()

    if suffix == ".xlsx":
        return pd.read_excel(path, header=None)

    if suffix == ".xls":
        return pd.read_excel(path, header=None)

    if suffix == ".csv":
        return pd.read_csv(path, header=None)

    raise ValueError(f"Unsupported bank file: {path.name}")


# ============================================================
# HEADER DETECTION
# ============================================================

HEADER_WORDS = {
    "date",
    "value date",
    "transaction date",
    "description",
    "narrative",
    "debit",
    "debit amount",
    "credit",
    "credit amount",
    "balance",
    "running balance",
    "running bal",
    "bank reference no",
    "bank ref",
    "customer reference no",
    "cust ref",
    "cheque no",
    "transaction type",
}


def find_header_row(df):

    best_row = None
    best_score = -1

    for i in range(min(len(df), 100)):

        values = [
            clean_text(x).lower()
            for x in df.iloc[i].tolist()
        ]

        score = 0

        for value in values:

            if value in HEADER_WORDS:
                score += 2

            elif any(
                word in value
                for word in [
                    "date",
                    "debit",
                    "credit",
                    "balance",
                    "description",
                    "reference",
                    "narrative",
                ]
            ):
                score += 1

        if score > best_score:

            best_score = score
            best_row = i

    if best_score <= 0:
        raise ValueError(
            f"Could not identify bank header row. score={best_score}"
        )

    return best_row


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def normalize_column_name(value):

    value = clean_text(value).lower()

    value = re.sub(r"[^a-z0-9]+", " ", value)

    return value.strip()


COLUMN_MAPPING = {

    "date": "date",
    "transaction date": "date",

    "value date": "value_date",

    "description": "description",
    "narrative": "description",

    "bank reference no": "reference",
    "bank ref": "reference",

    "customer reference no": "customer_reference",
    "cust ref": "customer_reference",
    "cheque no": "customer_reference",

    "transaction type": "transaction_type",

    "debit": "debit_amount",
    "debit amount": "debit_amount",

    "credit": "credit_amount",
    "credit amount": "credit_amount",

    "balance": "balance",
    "running balance": "balance",
    "running bal": "balance",
}


def normalize_bank_dataframe(raw, source_file):

    header_row = find_header_row(raw)

    df = raw.iloc[header_row + 1:].copy()

    headers = [
        normalize_column_name(x)
        for x in raw.iloc[header_row].tolist()
    ]

    df.columns = headers

    mapped = {}

    for col in df.columns:

        if col in COLUMN_MAPPING:
            mapped[col] = COLUMN_MAPPING[col]

    df = df.rename(columns=mapped)

    # Add missing standard fields.
    for col in STANDARD_COLUMNS:

        if col not in df.columns:
            df[col] = pd.NA

    # Keep only standard schema.
    df = df[STANDARD_COLUMNS].copy()

    # Metadata.
    df["bank_name"] = detect_bank_from_filename(source_file)
    df["source_file"] = source_file

    # Dates.
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["value_date"] = pd.to_datetime(
        df["value_date"],
        errors="coerce"
    )

    # Amounts.
    for col in [
        "debit_amount",
        "credit_amount",
        "balance",
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # IMPORTANT:
    # FAB often contains 0.00 in the unused side.
    # Convert zero unused values to NA.
    for col in [
        "debit_amount",
        "credit_amount",
    ]:

        df.loc[
            df[col].abs().fillna(0).eq(0),
            col
        ] = np.nan

    # Text.
    for col in [
        "description",
        "reference",
        "customer_reference",
        "transaction_type",
    ]:

        df[col] = df[col].map(
            lambda x: clean_text(x) if not pd.isna(x) else ""
        )

    # Remove completely empty transactions.
    transaction_columns = [
        "date",
        "value_date",
        "description",
        "reference",
        "customer_reference",
        "transaction_type",
        "debit_amount",
        "credit_amount",
        "balance",
    ]

    df = df.dropna(
        subset=transaction_columns,
        how="all"
    ).reset_index(drop=True)

    return df


# ============================================================
# LOAD BANK DATA
# ============================================================
def load_all_bank_data():

    if not BANK_INPUT.exists():
        raise FileNotFoundError(
            f"Normalized bank file not found: {BANK_INPUT}"
        )

    if not BANK_INPUT.is_file():
        raise RuntimeError(
            f"BANK_INPUT is not a file: {BANK_INPUT}"
        )

    print(
        f"Loading normalized bank master: {BANK_INPUT}"
    )

    bank_df = pd.read_excel(
        BANK_INPUT
    )

    required_columns = [
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

    missing = [
        column
        for column in required_columns
        if column not in bank_df.columns
    ]

    if missing:
        raise ValueError(
            "Normalized bank file is missing required columns: "
            + ", ".join(missing)
        )

    bank_df = bank_df[
        required_columns
    ].copy()

    print(
        f"    Bank rows : {len(bank_df)}"
    )

    print(
        f"    Bank columns : {len(bank_df.columns)}"
    )

    return bank_df

# ============================================================
# POP LOADING
# ============================================================

def load_pop():

    df = pd.read_excel(
        POP_INPUT
    )
    required = [
        "case_number",
        "email_receipt_amount",
        "email_bank_account",
    ]
    missing = [
        c for c in required
        if c not in df.columns
    ]
    if missing:
        raise ValueError(
            f"POP missing required columns: {missing}"
        )

    df = df.copy()

    df["pop_amount"] = pd.to_numeric(
        df["email_receipt_amount"],
        errors="coerce"
    )

    df["email_bank_account"] = (
        df["email_bank_account"]
        .map(normalize_account)
    )

    return df

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"POP missing required columns: {missing}"
        )

    df = df.copy()

    df["pop_amount"] = pd.to_numeric(
        df["pop_amount"],
        errors="coerce"
    )

    df["email_bank_account"] = (
        df["email_bank_account"]
        .map(normalize_account)
    )

    return df


# ============================================================
# POP -> BANK ACCOUNT IDENTIFICATION
# ============================================================

def bank_account_matches_pop(pop_row, bank_row):

    pop_account = normalize_account(
        pop_row.get("email_bank_account")
    )

    if not pop_account:
        return False

    bank_source = clean_text(
        bank_row.get("source_file")
    )

    # Extract long numeric account from filename.
    numbers = re.findall(
        r"\d{8,}",
        bank_source
    )

    for number in numbers:

        if normalize_account(number) == pop_account:
            return True

    return False


# ============================================================
# FIELD EVIDENCE
# ============================================================

def field_evidence(pop, bank):

    evidence = []
    score = 0

    # --------------------------------------------------------
    # POP booking/reference
    # --------------------------------------------------------

    pop_refs = []

    for col in [
        "pop_booking_reference",
        "reference_number",
        "email_receipt_reference",
    ]:

        value = normalize_alnum(
            pop.get(col)
        )

        if value:
            pop_refs.append(value)

    bank_refs = []

    for col in [
        "reference",
        "customer_reference",
        "description",
    ]:

        value = normalize_alnum(
            bank.get(col)
        )

        if value:
            bank_refs.append(value)

    for pref in pop_refs:

        for bref in bank_refs:

            if pref == bref:

                score += 40

                evidence.append(
                    f"EXACT_REFERENCE:{pref}"
                )

            elif len(pref) >= 6 and pref in bref:

                score += 30

                evidence.append(
                    f"REFERENCE_CONTAINS:{pref}"
                )

            elif len(bref) >= 6 and bref in pref:

                score += 25

                evidence.append(
                    f"BANK_REFERENCE_CONTAINS:{bref}"
                )

    # --------------------------------------------------------
    # Customer name
    # --------------------------------------------------------

    pop_names = []

    for col in [
        "email_customer_name",
        "sender_name",
        "beneficiary_name",
    ]:

        value = name_tokens(
            pop.get(col)
        )

        if value:
            pop_names.append(value)

    bank_text = normalize_name(
        " ".join(
            [
                str(bank.get("description", "")),
                str(bank.get("reference", "")),
                str(bank.get("customer_reference", "")),
            ]
        )
    )

    bank_name_tokens = name_tokens(
        bank_text
    )

    for tokens in pop_names:

        if not tokens:
            continue

        overlap = tokens.intersection(
            bank_name_tokens
        )

        if len(overlap) >= 2:

            score += 25

            evidence.append(
                "CUSTOMER_2+_TOKENS:" +
                ",".join(sorted(overlap))
            )

        elif len(overlap) == 1:

            score += 10

            evidence.append(
                "CUSTOMER_1_TOKEN:" +
                next(iter(overlap))
            )

    # --------------------------------------------------------
    # Bank name
    # --------------------------------------------------------

    pop_bank = normalize_name(
        pop.get("email_bank_name")
    )

    bank_name = clean_text(
        bank.get("bank_name")
    )

    bank_aliases = {

        "FAB": [
            "FAB",
            "FIRST ABU DHABI BANK",
            "FIRSTABUDHABIBANK",
        ],

        "ADCB": [
            "ADCB",
            "ABU DHABI COMMERCIAL BANK",
        ],

        "CBD": [
            "CBD",
            "COMMERCIAL BANK OF DUBAI",
        ],
    }

    aliases = bank_aliases.get(
        bank_name,
        []
    )

    if pop_bank:

        normalized_pop_bank = normalize_alnum(
            pop_bank
        )

        for alias in aliases:

            if normalized_pop_bank in normalize_alnum(alias):

                score += 10

                evidence.append(
                    "POP_BANK_SUPPORT"
                )

                break

    return score, evidence


# ============================================================
# DATE EVIDENCE
# ============================================================

def date_difference_days(pop, bank):

    pop_dates = []

    for col in [
        "pop_value_date",
        "transaction_date",
        "date_source",
    ]:

        value = normalize_date(
            pop.get(col)
        )

        if pd.notna(value):
            pop_dates.append(value)

    bank_date = normalize_date(
        bank.get("date")
    )

    bank_value_date = normalize_date(
        bank.get("value_date")
    )

    if not pop_dates:
        return np.nan

    bank_dates = [
        x for x in [
            bank_date,
            bank_value_date,
        ]
        if pd.notna(x)
    ]

    if not bank_dates:
        return np.nan

    differences = []

    for p in pop_dates:

        for b in bank_dates:

            differences.append(
                abs((p - b).days)
            )

    return min(differences)


def date_score(days):

    if pd.isna(days):
        return 0

    if days == 0:
        return 30

    if days == 1:
        return 20

    if days <= 3:
        return 10

    if days <= 7:
        return 3

    return 0


# ============================================================
# MATCH ONE POP
# ============================================================
def generate_candidates(pop, bank_df):

    pop_amount = safe_float(
        pop.get("pop_amount")
    )

    if pd.isna(pop_amount):
        return []

    candidates = []

    # ========================================================
    # STAGE 1:
    # EXACT POP SOURCE FILE -> BANK SOURCE FILE
    # ========================================================

    pop_source_file = str(
        pop.get("bank_source_file") or ""
    ).strip().upper()

    if not pop_source_file:
        return []

    bank_source_files = (
        bank_df["source_file"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    account_rows = bank_df[
        bank_source_files.eq(
            pop_source_file
        )
    ].copy()

    # The POP already identifies its exact bank statement.
    # Do NOT fall back to the full bank dataset if the
    # source file is not found.
    if account_rows.empty:
        return []

    working = account_rows.copy()

    # ========================================================
    # STAGE 2:
    # EXACT AMOUNT
    # ========================================================

    working = working.copy()

    working["_bank_amount"] = working.apply(
        amount_from_bank,
        axis=1
    )

    working["_amount_difference"] = (
        working["_bank_amount"] - pop_amount
    ).abs()

    exact = working[
        working["_amount_difference"].le(0.01)
    ].copy()

    # IMPORTANT:
    # If exact amount candidates exist,
    # do NOT allow near-amount candidates to compete.
    if not exact.empty:

        working = exact

    else:

        # Near amount fallback.
        working = working[
            working["_amount_difference"].le(5.00)
        ].copy()

        if working.empty:
            return []

    # ========================================================
    # STAGE 3:
    # FIELD + DATE SCORING
    # ========================================================

    for idx, bank in working.iterrows():

        field_score, field_evidence_list = (
            field_evidence(
                pop,
                bank
            )
        )

        days = date_difference_days(
            pop,
            bank
        )

        dscore = date_score(
            days
        )

        amount_difference = float(
            bank["_amount_difference"]
        )

        # Amount is the dominant signal.
        if amount_difference <= 0.01:
            amount_score = 100
        else:
            amount_score = max(
                0,
                50 - amount_difference * 5
            )

        total_score = (
            amount_score
            + field_score
            + dscore
        )

        candidates.append(
            {
                "bank_row_index": idx,
                "bank_date": bank.get("date"),
                "bank_value_date": bank.get("value_date"),
                "bank_description": bank.get("description"),
                "bank_reference": bank.get("reference"),
                "bank_customer_reference": bank.get(
                    "customer_reference"
                ),
                "bank_transaction_type": bank.get(
                    "transaction_type"
                ),
                "bank_debit_amount": bank.get(
                    "debit_amount"
                ),
                "bank_credit_amount": bank.get(
                    "credit_amount"
                ),
                "bank_balance": bank.get(
                    "balance"
                ),
                "bank_amount": bank["_bank_amount"],
                "bank_name": bank.get("bank_name"),
                "source_file": bank.get("source_file"),
                "amount_difference": amount_difference,
                "date_difference": days,
                "field_score": field_score,
                "date_score": dscore,
                "amount_score": amount_score,
                "score": total_score,
                "evidence": "; ".join(
                    field_evidence_list
                ),
            }
        )

    candidates.sort(
        key=lambda x: (
            x["score"],
            -x["amount_difference"],
            -(
                x["field_score"]
                + x["date_score"]
            ),
        ),
        reverse=True
    )

    return candidates

# ============================================================
# DECISION LOGIC
# ============================================================

def decide(candidates):

    if not candidates:

        return {
            "status": "NO_MATCH",
            "match_reason": "NO_VALID_CANDIDATE",
            "selected": None,
            "score": np.nan,
            "score_gap": np.nan,
        }

    best = candidates[0]

    second_score = (
        candidates[1]["score"]
        if len(candidates) > 1
        else np.nan
    )

    score_gap = (
        best["score"] - second_score
        if pd.notna(second_score)
        else np.inf
    )

    exact_amount = (
        best["amount_difference"] <= 0.01
    )

    # --------------------------------------------------------
    # EXACT AMOUNT + STRONG FIELD EVIDENCE
    # --------------------------------------------------------

    if (
        exact_amount
        and best["field_score"] >= 25
    ):

        return {
            "status": "MATCHED",
            "match_reason": "EXACT_AMOUNT_STRONG_FIELD",
            "selected": best,
            "score": best["score"],
            "score_gap": score_gap,
        }

    # --------------------------------------------------------
    # EXACT AMOUNT + DATE
    # --------------------------------------------------------

    if (
        exact_amount
        and best["date_difference"] <= 1
        and score_gap >= 10
    ):

        return {
            "status": "MATCHED",
            "match_reason": "EXACT_AMOUNT_DATE",
            "selected": best,
            "score": best["score"],
            "score_gap": score_gap,
        }

    # --------------------------------------------------------
    # EXACT AMOUNT BUT COMPETING CANDIDATES
    # --------------------------------------------------------

    if (
        exact_amount
        and len(candidates) > 1
        and score_gap < 10
    ):

        return {
            "status": "AMBIGUOUS",
            "match_reason": "MULTIPLE_EXACT_AMOUNT_CANDIDATES",
            "selected": best,
            "score": best["score"],
            "score_gap": score_gap,
        }

    # --------------------------------------------------------
    # EXACT AMOUNT UNIQUE
    # --------------------------------------------------------

    if (
        exact_amount
        and len(candidates) == 1
    ):

        return {
            "status": "MATCHED",
            "match_reason": "UNIQUE_EXACT_AMOUNT",
            "selected": best,
            "score": best["score"],
            "score_gap": score_gap,
        }

    # --------------------------------------------------------
    # NEAR AMOUNT
    # --------------------------------------------------------

    return {
        "status": "NEAR_AMOUNT",
        "match_reason": "NO_EXACT_AMOUNT",
        "selected": best,
        "score": best["score"],
        "score_gap": score_gap,
    }


# ============================================================
# MAIN MATCHING ENGINE
# ============================================================

def main():

    print("=" * 120)
    print("POP -> BANK MATCHING ENGINE")
    print("=" * 120)

    print()
    print("POP INPUT :", POP_INPUT)
    print("BANK INPUT:", BANK_INPUT)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # LOAD POP
    # --------------------------------------------------------

    pop_df = load_pop()

    print()
    print("=" * 120)
    print("POP SOURCE VALIDATION")
    print("=" * 120)

    print(
        "POP rows extracted       :",
        len(pop_df)
    )

    print(
        "Rows with case number    :",
        pop_df["case_number"].notna().sum()
    )

    print(
        "Rows with amount         :",
        pop_df["pop_amount"].notna().sum()
    )

    # --------------------------------------------------------
    # LOAD BANK
    # --------------------------------------------------------

    print()
    print("=" * 120)
    print("BANK NORMALIZATION")
    print("=" * 120)

    bank_df = load_all_bank_data()

    print()
    print(
        "Normalized bank transactions:",
        len(bank_df)
    )

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    print()
    print("=" * 120)
    print("MATCHING")
    print("=" * 120)

    print(
        "Logic:"
    )

    print(
        "  1. POP ACCOUNT -> CORRECT BANK STATEMENT"
    )

    print(
        "  2. EXACT AMOUNT"
    )

    print(
        "  3. POP REFERENCE / CUSTOMER / BANK EVIDENCE"
    )

    print(
        "  4. DATE SUPPORT"
    )

    print(
        "  5. CONFIDENCE + SCORE GAP"
    )

    print(
        "  6. ONE-TO-ONE BANK ROW LOCKING"
    )

    results = []
    audit = []

    locked_bank_rows = set()

    for _, pop in pop_df.iterrows():

        candidates = generate_candidates(
            pop,
            bank_df
        )

        # Remove already locked rows.
        candidates = [
            x for x in candidates
            if x["bank_row_index"]
            not in locked_bank_rows
        ]

        decision = decide(
            candidates
        )

        selected = decision["selected"]

        if selected is not None:

            bank_idx = selected[
                "bank_row_index"
            ]

            # Only actual MATCHED rows get locked.
            if decision["status"] == "MATCHED":

                locked_bank_rows.add(
                    bank_idx
                )

        case_number = pop.get(
            "case_number"
        )

        result = {
            "case_number": case_number,
            "status": decision["status"],
            "match_reason": decision[
                "match_reason"
            ],
            "score": decision["score"],
            "score_gap": decision["score_gap"],
            "candidate_count": len(candidates),

            "pop_amount": pop.get(
                "pop_amount"
            ),

            "pop_date": pop.get(
                "pop_value_date"
            ),

            "pop_reference": pop.get(
                "pop_booking_reference"
            ),

            "pop_customer_reference": pop.get(
                "reference_number"
            ),

            "pop_account": pop.get(
                "email_bank_account"
            ),

            "pop_customer_name": pop.get(
                "email_customer_name"
            ),

            "pop_bank_name": pop.get(
                "email_bank_name"
            ),

            "pop_payment_method": pop.get(
                "email_payment_method"
            ),

            "pop_source_file": pop.get(
                "bank_source_file"
            ),

            "bank_row_index": (
                selected["bank_row_index"]
                if selected
                else np.nan
            ),

            "bank_date": (
                selected["bank_date"]
                if selected
                else pd.NaT
            ),

            "bank_value_date": (
                selected["bank_value_date"]
                if selected
                else pd.NaT
            ),

            "bank_description": (
                selected["bank_description"]
                if selected
                else ""
            ),

            "bank_reference": (
                selected["bank_reference"]
                if selected
                else ""
            ),

            "bank_customer_reference": (
                selected[
                    "bank_customer_reference"
                ]
                if selected
                else ""
            ),

            "bank_transaction_type": (
                selected[
                    "bank_transaction_type"
                ]
                if selected
                else ""
            ),

            "bank_debit_amount": (
                selected[
                    "bank_debit_amount"
                ]
                if selected
                else np.nan
            ),

            "bank_credit_amount": (
                selected[
                    "bank_credit_amount"
                ]
                if selected
                else np.nan
            ),

            "bank_balance": (
                selected[
                    "bank_balance"
                ]
                if selected
                else np.nan
            ),

            "bank_amount": (
                selected["bank_amount"]
                if selected
                else np.nan
            ),

            "bank_name": (
                selected["bank_name"]
                if selected
                else ""
            ),

            "source_file": (
                selected["source_file"]
                if selected
                else ""
            ),

            "amount_difference": (
                selected[
                    "amount_difference"
                ]
                if selected
                else np.nan
            ),

            "date_difference": (
                selected[
                    "date_difference"
                ]
                if selected
                else np.nan
            ),

            "evidence": (
                selected["evidence"]
                if selected
                else ""
            ),
        }

        results.append(
            result
        )

        # ----------------------------------------------------
        # AUDIT ALL TOP CANDIDATES
        # ----------------------------------------------------

        for rank, candidate in enumerate(
            candidates[:10],
            start=1
        ):

            audit.append(
                {
                    "case_number": case_number,
                    "rank": rank,
                    "selected": (
                        rank == 1
                        and selected is not None
                    ),
                    "status": decision["status"],
                    "bank_row_index":
                        candidate[
                            "bank_row_index"
                        ],
                    "source_file":
                        candidate[
                            "source_file"
                        ],
                    "bank_name":
                        candidate[
                            "bank_name"
                        ],
                    "bank_amount":
                        candidate[
                            "bank_amount"
                        ],
                    "amount_difference":
                        candidate[
                            "amount_difference"
                        ],
                    "date_difference":
                        candidate[
                            "date_difference"
                        ],
                    "amount_score":
                        candidate[
                            "amount_score"
                        ],
                    "field_score":
                        candidate[
                            "field_score"
                        ],
                    "date_score":
                        candidate[
                            "date_score"
                        ],
                    "score":
                        candidate[
                            "score"
                        ],
                    "evidence":
                        candidate[
                            "evidence"
                        ],
                }
            )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    results_df = pd.DataFrame(
        results
    )

    audit_df = pd.DataFrame(
        audit
    )

    results_df.to_excel(
        MATCH_OUTPUT,
        index=False
    )

    audit_df.to_excel(
        AUDIT_OUTPUT,
        index=False
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 120)
    print("FINAL MATCHING SUMMARY")
    print("=" * 120)

    print(
        "POP transactions :",
        len(pop_df)
    )

    print(
        "BANK transactions:",
        len(bank_df)
    )

    counts = (
        results_df["status"]
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
                0
            )
        )

        pct = (
            count / len(results_df) * 100
            if len(results_df)
            else 0
        )

        print(
            f"{status:<20}"
            f"{count:>5}"
            f" ({pct:6.2f}%)"
        )

    print()
    print(
        "Unique bank rows locked:",
        len(locked_bank_rows)
    )

    print()
    print("=" * 120)
    print("MATCHED CASES")
    print("=" * 120)

    matched = results_df[
        results_df["status"].eq(
            "MATCHED"
        )
    ]

    if matched.empty:

        print(
            "No MATCHED rows."
        )

    else:

        print(
            matched[
                [
                    "case_number",
                    "status",
                    "match_reason",
                    "pop_amount",
                    "bank_amount",
                    "amount_difference",
                    "date_difference",
                    "bank_name",
                    "source_file",
                    "evidence",
                ]
            ].to_string(
                index=False
            )
        )

    print()
    print("=" * 120)
    print("OUTPUT FILES")
    print("=" * 120)

    print(
        "MATCH RESULTS :",
        MATCH_OUTPUT
    )

    print(
        "CANDIDATE AUDIT:",
        AUDIT_OUTPUT
    )

    print()
    print("ENGINE COMPLETED.")


if __name__ == "__main__":
    main()
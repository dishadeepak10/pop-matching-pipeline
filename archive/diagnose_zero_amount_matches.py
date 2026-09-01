from pathlib import Path
import pandas as pd
import numpy as np
import re


# ============================================================
# CONFIG
# ============================================================

BANK_FILE = Path(
    r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
)

POP_FILE = Path(
    r"D:\Disha_Workarea\pop_process\data\output\POP_email_merged_final.xlsx"
)

# All cases that had ZERO amount candidates in the matcher
ZERO_CASES = [
    84373,
    84375,
    84401,
    84696,
    84725,
]

# Diagnostic tolerance only.
# We are NOT changing the actual matcher yet.
AMOUNT_TOLERANCE = 1.00


# ============================================================
# HELPERS
# ============================================================

def clean_amount(value):
    if pd.isna(value):
        return np.nan

    try:
        return float(value)
    except Exception:
        try:
            value = str(value).replace(",", "").strip()
            return float(value)
        except Exception:
            return np.nan


def normalize_text(value):
    if pd.isna(value):
        return ""

    value = str(value).upper()

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def get_bank_amount(row):
    """
    Prefer credit because PoP payments are normally
    incoming bank transactions.

    Fall back to debit if no credit exists.
    """

    credit = clean_amount(
        row.get("credit_amount")
    )

    debit = clean_amount(
        row.get("debit_amount")
    )

    if not pd.isna(credit) and credit > 0:
        return credit

    if not pd.isna(debit) and debit > 0:
        return debit

    return np.nan


def parse_pop_date(value):
    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    if not value:
        return pd.NaT

    # First try day-first because the POP data contains
    # DD/MM/YYYY-style values.
    parsed = pd.to_datetime(
        value,
        errors="coerce",
        dayfirst=True,
    )

    if not pd.isna(parsed):
        return parsed

    return pd.to_datetime(
        value,
        errors="coerce",
    )


def sender_token_overlap(sender, candidate):
    sender_text = normalize_text(sender)
    candidate_text = normalize_text(candidate)

    if not sender_text or not candidate_text:
        return []

    tokens = [
        token
        for token in sender_text.split()
        if len(token) >= 4
    ]

    return [
        token
        for token in tokens
        if token in candidate_text
    ]


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 110)
print("ZERO-CASE AMOUNT MATCH DIAGNOSTIC")
print("=" * 110)

bank = pd.read_excel(BANK_FILE)
pop = pd.read_excel(POP_FILE)

print()
print("BANK SHAPE :", bank.shape)
print("POP SHAPE  :", pop.shape)
print()


# ============================================================
# VALIDATE POP COLUMNS
# ============================================================

required_pop_columns = [
    "case_number",
    "sender_name",
    "transaction_date",
    "amount",
    "currency",
    "reference_number",
    "email_created_date",
    "email_receipt_amount",
    "pop_amount",
    "pop_currency",
    "pop_original_amount",
    "pop_original_currency",
    "pop_exchange_rate",
]

missing_pop_columns = [
    col
    for col in required_pop_columns
    if col not in pop.columns
]

if missing_pop_columns:
    raise ValueError(
        "Missing required POP columns:\n"
        + "\n".join(missing_pop_columns)
    )

print("CASE COLUMN   : case_number")
print("AMOUNT COLUMNS:")
print("  - email_receipt_amount")
print("  - pop_amount")
print("  - amount")
print("  - pop_original_amount")
print()


# ============================================================
# PREP BANK DATA
# ============================================================

bank["date"] = pd.to_datetime(
    bank["date"],
    errors="coerce",
    dayfirst=True,
)

for col in [
    "debit_amount",
    "credit_amount",
]:
    bank[col] = pd.to_numeric(
        bank[col],
        errors="coerce",
    )

bank["_bank_amount"] = bank.apply(
    get_bank_amount,
    axis=1,
)

bank["_description_clean"] = bank[
    "description"
].apply(normalize_text)

bank["_reference_clean"] = bank[
    "reference"
].apply(normalize_text)

bank["_customer_reference_clean"] = bank[
    "customer_reference"
].apply(normalize_text)


# ============================================================
# DIAGNOSE EACH ZERO CASE
# ============================================================

for case_id in ZERO_CASES:

    print()
    print("-" * 110)
    print(f"CASE : {case_id}")
    print("-" * 110)

    # --------------------------------------------------------
    # FIND POP CASE
    # --------------------------------------------------------

    case_rows = pop[
        pop["case_number"].astype(str).str.strip()
        == str(case_id).strip()
    ]

    if case_rows.empty:
        print("!!! CASE NOT FOUND IN POP FILE !!!")
        continue

    row = case_rows.iloc[0]

    # --------------------------------------------------------
    # POP INFORMATION
    # --------------------------------------------------------

    sender = row.get(
        "sender_name"
    )

    reference = row.get(
        "reference_number"
    )

    transaction_date = row.get(
        "transaction_date"
    )

    email_created_date = row.get(
        "email_created_date"
    )

    currency = row.get(
        "currency"
    )

    email_receipt_amount = clean_amount(
        row.get("email_receipt_amount")
    )

    pop_amount = clean_amount(
        row.get("pop_amount")
    )

    general_amount = clean_amount(
        row.get("amount")
    )

    original_amount = clean_amount(
        row.get("pop_original_amount")
    )

    original_currency = row.get(
        "pop_original_currency"
    )

    exchange_rate = row.get(
        "pop_exchange_rate"
    )

    print(f"SENDER              : {sender}")
    print(f"TRANSACTION DATE    : {transaction_date}")
    print(f"EMAIL CREATED DATE  : {email_created_date}")
    print(f"REFERENCE           : {reference}")
    print(f"CURRENCY            : {currency}")
    print(f"EMAIL RECEIPT AMT   : {email_receipt_amount}")
    print(f"POP AMOUNT          : {pop_amount}")
    print(f"GENERAL AMOUNT      : {general_amount}")
    print(f"ORIGINAL AMOUNT     : {original_amount}")
    print(f"ORIGINAL CURRENCY   : {original_currency}")
    print(f"EXCHANGE RATE       : {exchange_rate}")

    # --------------------------------------------------------
    # BUILD ALL POP AMOUNTS
    # --------------------------------------------------------

    pop_amounts = []

    amount_sources = [
        (
            email_receipt_amount,
            "email_receipt_amount",
        ),
        (
            pop_amount,
            "pop_amount",
        ),
        (
            general_amount,
            "amount",
        ),
        (
            original_amount,
            "pop_original_amount",
        ),
    ]

    for amount, source in amount_sources:

        if pd.isna(amount):
            continue

        amount = abs(float(amount))

        if amount == 0:
            continue

        pop_amounts.append(
            {
                "amount": amount,
                "source": source,
            }
        )

    # Remove duplicate numerical amounts
    unique_amounts = {}

    for item in pop_amounts:

        key = round(
            item["amount"],
            2,
        )

        if key not in unique_amounts:
            unique_amounts[key] = item

    pop_amounts = list(
        unique_amounts.values()
    )

    print()
    print(
        "POP AMOUNT VARIANTS:"
    )

    if not pop_amounts:
        print("  NONE")
        continue

    for item in pop_amounts:
        print(
            f"  {item['amount']:.2f}"
            f"  <- {item['source']}"
        )

    # --------------------------------------------------------
    # POP DATE
    # --------------------------------------------------------

    pop_date = parse_pop_date(
        transaction_date
    )

    if pd.isna(pop_date):
        pop_date = parse_pop_date(
            email_created_date
        )

    print()
    print(
        f"MATCH DATE USED     : {pop_date}"
    )

    # ========================================================
    # SEARCH EACH POP AMOUNT
    # ========================================================

    for amount_info in pop_amounts:

        target_amount = amount_info[
            "amount"
        ]

        amount_source = amount_info[
            "source"
        ]

        print()
        print("=" * 100)
        print(
            f"AMOUNT CHECK: "
            f"{target_amount:.2f}"
            f" ({amount_source})"
        )
        print("=" * 100)

        # ----------------------------------------------------
        # EXACT
        # ----------------------------------------------------

        exact = bank[
            bank["_bank_amount"].notna()
            &
            np.isclose(
                bank["_bank_amount"],
                target_amount,
                atol=0.001,
            )
        ].copy()

        print()
        print(
            f"EXACT AMOUNT MATCHES: "
            f"{len(exact)}"
        )

        if exact.empty:

            print(
                "  -> NO EXACT AMOUNT MATCHES"
            )

        else:

            display_cols = [
                "date",
                "_bank_amount",
                "description",
                "reference",
                "customer_reference",
                "debit_amount",
                "credit_amount",
                "bank_name",
                "source_file",
            ]

            print(
                exact[
                    display_cols
                ]
                .sort_values("date")
                .to_string(
                    index=False
                )
            )

        # ----------------------------------------------------
        # NEAR
        # ----------------------------------------------------

        bank["_amount_difference"] = (
            bank["_bank_amount"]
            - target_amount
        ).abs()

        near = bank[
            bank["_amount_difference"].notna()
            &
            (
                bank["_amount_difference"]
                <= AMOUNT_TOLERANCE
            )
        ].copy()

        print()
        print(
            f"NEAR AMOUNT MATCHES "
            f"(<= {AMOUNT_TOLERANCE:.2f}): "
            f"{len(near)}"
        )

        if near.empty:

            print(
                "  -> NO NEAR AMOUNT MATCHES"
            )

        else:

            display_cols = [
                "date",
                "_bank_amount",
                "_amount_difference",
                "description",
                "reference",
                "customer_reference",
                "debit_amount",
                "credit_amount",
                "bank_name",
                "source_file",
            ]

            print(
                near[
                    display_cols
                ]
                .sort_values(
                    [
                        "_amount_difference",
                        "date",
                    ]
                )
                .head(20)
                .to_string(
                    index=False
                )
            )

        # ----------------------------------------------------
        # EXACT / NEAR + DATE
        # ----------------------------------------------------

        if not exact.empty and not pd.isna(
            pop_date
        ):

            exact["_date_difference_days"] = (
                exact["date"]
                - pop_date
            ).abs().dt.days

            print()
            print(
                "BEST EXACT-AMOUNT "
                "CANDIDATES BY DATE:"
            )

            display_cols = [
                "date",
                "_date_difference_days",
                "_bank_amount",
                "description",
                "reference",
                "customer_reference",
                "bank_name",
                "source_file",
            ]

            print(
                exact[
                    display_cols
                ]
                .sort_values(
                    "_date_difference_days"
                )
                .head(10)
                .to_string(
                    index=False
                )
            )

        if not near.empty and not pd.isna(
            pop_date
        ):

            near["_date_difference_days"] = (
                near["date"]
                - pop_date
            ).abs().dt.days

            print()
            print(
                "BEST NEAR-AMOUNT "
                "CANDIDATES BY DATE:"
            )

            display_cols = [
                "date",
                "_date_difference_days",
                "_bank_amount",
                "_amount_difference",
                "description",
                "reference",
                "customer_reference",
                "bank_name",
                "source_file",
            ]

            print(
                near[
                    display_cols
                ]
                .sort_values(
                    [
                        "_amount_difference",
                        "_date_difference_days",
                    ]
                )
                .head(10)
                .to_string(
                    index=False
                )
            )

        # ----------------------------------------------------
        # SENDER TOKEN CHECK
        # ----------------------------------------------------

        sender_text = normalize_text(
            sender
        )

        sender_tokens = [
            token
            for token in sender_text.split()
            if len(token) >= 4
        ]

        if sender_tokens and not near.empty:

            print()
            print(
                "SENDER TOKEN CHECK "
                "ON NEAR-AMOUNT CANDIDATES:"
            )

            for _, candidate in (
                near.head(10).iterrows()
            ):

                combined_text = " ".join(
                    [
                        normalize_text(
                            candidate.get(
                                "description"
                            )
                        ),
                        normalize_text(
                            candidate.get(
                                "reference"
                            )
                        ),
                        normalize_text(
                            candidate.get(
                                "customer_reference"
                            )
                        ),
                    ]
                )

                matched_tokens = [
                    token
                    for token in sender_tokens
                    if token in combined_text
                ]

                print()
                print(
                    f"DATE       : "
                    f"{candidate.get('date')}"
                )
                print(
                    f"BANK       : "
                    f"{candidate.get('bank_name')}"
                )
                print(
                    f"AMOUNT     : "
                    f"{candidate.get('_bank_amount')}"
                )
                print(
                    f"DIFFERENCE : "
                    f"{candidate.get('_amount_difference')}"
                )
                print(
                    f"TOKENS     : "
                    f"{matched_tokens}"
                )
                print(
                    f"DESCRIPTION: "
                    f"{candidate.get('description')}"
                )
                print(
                    f"REFERENCE  : "
                    f"{candidate.get('reference')}"
                )
                print(
                    f"CUSTOMER REF: "
                    f"{candidate.get('customer_reference')}"
                )
                print(
                    f"SOURCE     : "
                    f"{candidate.get('source_file')}"
                )


print()
print("=" * 110)
print("END ZERO-CASE AMOUNT DIAGNOSTIC")
print("=" * 110)
import re
from pathlib import Path

import numpy as np
import pandas as pd
from difflib import SequenceMatcher


# ============================================================
# AUGUST POP -> BANK GLOBAL MATCHING ENGINE
# ============================================================
#
# MATCHING PRINCIPLE
# ------------------
# 1. Exact bank
# 2. Exact source account
# 3. Exact credit amount
# 4. Date within +/- 10 days preferred
# 5. Reference/customer text used only as supporting evidence
# 6. One bank transaction can belong to ONE POP case only
# 7. Global assignment maximizes number of valid matches
# 8. Among possible assignments, closest date wins
# 9. NEVER force a wrong-account match
#
# HARD RULE:
# A MATCHED row must satisfy:
#   bank == POP bank
#   source_account == POP account
#   credit_amount == POP amount (tolerance 0.01)
#   date difference <= 10 days
#
# ============================================================


BASE = Path.cwd()

POP_PATH = BASE / "data" / "output" / "POP_AUG_MASTER.xlsx"

BANK_PATH = Path(
    r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
)

OUT_MATCH = BASE / "data" / "output" / "POP_AUG_MATCHES_DIRECT.xlsx"
OUT_CAND = BASE / "data" / "output" / "POP_AUG_CANDIDATES_DIRECT.xlsx"
OUT_DIAG = BASE / "data" / "output" / "POP_AUG_MATCHING_DIAGNOSTIC.xlsx"


DATE_WINDOW_DAYS = 10
AMOUNT_TOLERANCE = 0.01


# ============================================================
# HELPERS
# ============================================================

def norm_text(x):
    if pd.isna(x):
        return ""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(x).upper()
    )


def norm_account(x):
    if pd.isna(x):
        return ""

    s = str(x).strip()

    # Excel may turn account numbers into x.0
    s = re.sub(r"\.0$", "", s)

    # Keep digits only
    return re.sub(r"\D", "", s)


def similarity(a, b):
    a = norm_text(a)
    b = norm_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def safe_float(x):
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


# ============================================================
# BANK NAME NORMALIZATION
# ============================================================

BANK_MAP = {
    "First Abu Dhabi Bank": "FAB",
    "Commercial Bank Of Dubai": "CBD",
    "Commercial Bank of Dubai": "CBD",
    "Ajman Bank": "AJMAN",
    "National Bank of Fujairah": "NBF",
    "United Arab Bank": "UAB",
    "United Bank Limited": "UBL",
    "Mashreq": "MASHREQ",
    "Mashreqbank": "MASHREQ",
    "Abu Dhabi Commercial Bank": "ADCB",
    "Abu Dhabi Islamic Bank": "ADIB",
    "Al Hilal Bank": "ALHILAL",
    "Al Maryah Community Bank": "MASHREQ",
    "National Bank of Ras Al Khaimah": "NBRAK",
    "National Bank of Bahrain": "NBB",
    "Al Ahli Bank of Kuwait": "ABK",
    "Invest Bank": "INVEST BANK",
}


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 110)
print("AUGUST POP -> BANK GLOBAL MATCHING ENGINE")
print("=" * 110)

print("\nPOP FILE:")
print(POP_PATH)

print("\nBANK FILE:")
print(BANK_PATH)


pop = pd.read_excel(POP_PATH)
bank = pd.read_excel(BANK_PATH)


print("\nINPUT SUMMARY")
print("-" * 110)
print("POP ROWS :", len(pop))
print("BANK ROWS:", len(bank))


# ============================================================
# VALIDATE REQUIRED COLUMNS
# ============================================================

required_pop = [
    "case_number",
    "receipt_amount",
    "pop_date",
    "bank_name",
    "bank_account_number",
    "customer_name",
    "receipt_reference",
]

required_bank = [
    "date",
    "description",
    "reference",
    "customer_reference",
    "credit_amount",
    "bank_name",
    "source_file",
]


missing_pop = [c for c in required_pop if c not in pop.columns]
missing_bank = [c for c in required_bank if c not in bank.columns]


if missing_pop:
    raise ValueError(
        f"POP file missing required columns: {missing_pop}"
    )

if missing_bank:
    raise ValueError(
        f"BANK file missing required columns: {missing_bank}"
    )


# ============================================================
# NORMALIZE POP
# ============================================================

pop["bank_code"] = pop["bank_name"].map(BANK_MAP)

# Fallback: if already a short bank code
pop["bank_code"] = pop["bank_code"].fillna(
    pop["bank_name"].astype(str).str.upper().str.strip()
)

pop["account_norm"] = (
    pop["bank_account_number"]
    .apply(norm_account)
)

pop["pop_date_norm"] = pd.to_datetime(
    pop["pop_date"],
    errors="coerce"
)

pop["amount_norm"] = pd.to_numeric(
    pop["receipt_amount"],
    errors="coerce"
).round(2)

pop["customer_norm"] = (
    pop["customer_name"]
    .fillna("")
    .astype(str)
)

pop["reference_norm"] = (
    pop["receipt_reference"]
    .fillna("")
    .astype(str)
)


# ============================================================
# NORMALIZE BANK
# ============================================================

bank["date_norm"] = pd.to_datetime(
    bank["date"],
    errors="coerce"
)

bank["credit_norm"] = pd.to_numeric(
    bank["credit_amount"],
    errors="coerce"
).round(2)


bank["source_text"] = (
    bank["description"]
    .fillna("")
    .astype(str)
    + " "
    + bank["reference"]
    .fillna("")
    .astype(str)
    + " "
    + bank["customer_reference"]
    .fillna("")
    .astype(str)
)


# ============================================================
# EXTRACT ACCOUNT FROM SOURCE FILE
# ============================================================

bank["source_account"] = (
    bank["source_file"]
    .fillna("")
    .astype(str)
    .str.extract(
        r"(\d{8,20})(?:\.[A-Za-z0-9]+)?$",
        expand=False
    )
    .fillna("")
    .apply(norm_account)
)


print("\nBANK ACCOUNT EXTRACTION")
print("-" * 110)

print(
    "Rows with source account:",
    (bank["source_account"] != "").sum()
)

print(
    "Rows without source account:",
    (bank["source_account"] == "").sum()
)


print("\nBANKS")
print(
    bank["bank_name"]
    .value_counts(dropna=False)
    .to_string()
)


# ============================================================
# CREATE UNIQUE BANK ROW ID
# ============================================================

# IMPORTANT:
# Never use the dataframe index as ownership identity.
# Create a permanent unique bank row ID.

bank = bank.reset_index(drop=True)

bank["bank_row_id"] = np.arange(len(bank))


# ============================================================
# HARD-EVIDENCE DIAGNOSTIC
# ============================================================

print("\n")
print("=" * 110)
print("HARD-EVIDENCE DIAGNOSTIC")
print("=" * 110)


diagnostic_rows = []


for _, p in pop.iterrows():

    case = p["case_number"]
    pop_amount = safe_float(p["amount_norm"])
    pop_date = p["pop_date_norm"]
    pop_bank = p["bank_code"]
    pop_account = p["account_norm"]

    same_bank = bank[
        bank["bank_name"].astype(str).str.upper().eq(
            str(pop_bank).upper()
        )
    ]

    same_bank_amount = same_bank[
        same_bank["credit_norm"].notna()
        & np.isclose(
            same_bank["credit_norm"].astype(float),
            pop_amount,
            atol=AMOUNT_TOLERANCE
        )
    ]

    correct_account = same_bank_amount[
        same_bank_amount["source_account"].eq(
            pop_account
        )
    ]

    date_supported = correct_account.copy()

    if (
        not correct_account.empty
        and pd.notna(pop_date)
    ):
        date_supported = correct_account[
            correct_account["date_norm"].notna()
            & (
                (
                    correct_account["date_norm"]
                    - pop_date
                ).abs().dt.days
                <= DATE_WINDOW_DAYS
            )
        ]

    other_bank_amount = bank[
        bank["credit_norm"].notna()
        & np.isclose(
            bank["credit_norm"].astype(float),
            pop_amount,
            atol=AMOUNT_TOLERANCE
        )
        & ~bank["bank_name"].astype(str).str.upper().eq(
            str(pop_bank).upper()
        )
    ]

    if not same_bank_amount.empty:

        if not correct_account.empty:

            if not date_supported.empty:
                classification = (
                    "VALID_ACCOUNT_AMOUNT_DATE_SUPPORTED"
                )

            else:
                classification = (
                    "VALID_ACCOUNT_AMOUNT_NO_DATE_SUPPORT"
                )

        else:
            classification = (
                "AMOUNT_FOUND_SAME_BANK_WRONG_ACCOUNT"
            )

    elif not other_bank_amount.empty:

        classification = "AMOUNT_FOUND_OTHER_BANK"

    else:

        classification = "AMOUNT_NOT_FOUND_ANYWHERE"

    diagnostic_rows.append({
        "case_number": case,
        "pop_bank": pop_bank,
        "pop_account": pop_account,
        "pop_amount": pop_amount,
        "pop_date": pop_date,
        "same_bank_amount_rows": len(same_bank_amount),
        "exact_account_amount_rows": len(correct_account),
        "date_supported_rows": len(date_supported),
        "other_bank_amount_rows": len(other_bank_amount),
        "classification": classification,
    })


diagnostic = pd.DataFrame(diagnostic_rows)


print(
    diagnostic["classification"]
    .value_counts(dropna=False)
    .to_string()
)


# ============================================================
# BUILD ONLY VALID MATCH CANDIDATES
# ============================================================
#
# CRITICAL:
#
# We ONLY create a candidate when:
#
#   BANK EXACT
#   ACCOUNT EXACT
#   AMOUNT EXACT
#   DATE <= 10 DAYS
#
# This means wrong-account transactions can NEVER become matches.
# ============================================================

candidate_rows = []


for _, p in pop.iterrows():

    case = p["case_number"]

    pop_amount = safe_float(
        p["amount_norm"]
    )

    pop_date = p["pop_date_norm"]

    pop_bank = str(
        p["bank_code"]
    ).upper().strip()

    pop_account = p["account_norm"]

    pop_name = p["customer_norm"]

    pop_ref = p["reference_norm"]


    # --------------------------------------------------------
    # Exact BANK
    # --------------------------------------------------------

    x = bank[
        bank["bank_name"]
        .astype(str)
        .str.upper()
        .str.strip()
        .eq(pop_bank)
    ].copy()


    # --------------------------------------------------------
    # Exact ACCOUNT
    # --------------------------------------------------------

    x = x[
        x["source_account"].eq(
            pop_account
        )
    ].copy()


    # --------------------------------------------------------
    # Exact CREDIT AMOUNT
    # --------------------------------------------------------

    x = x[
        x["credit_norm"].notna()
        & np.isclose(
            x["credit_norm"].astype(float),
            pop_amount,
            atol=AMOUNT_TOLERANCE
        )
    ].copy()


    if x.empty:
        continue


    # --------------------------------------------------------
    # DATE WINDOW
    # --------------------------------------------------------

    if pd.notna(pop_date):

        x["date_difference_days"] = (
            x["date_norm"] - pop_date
        ).abs().dt.days

        x = x[
            x["date_difference_days"].notna()
            & (
                x["date_difference_days"]
                <= DATE_WINDOW_DAYS
            )
        ].copy()

    else:

        x["date_difference_days"] = 999


    if x.empty:
        continue


    # --------------------------------------------------------
    # SCORE CANDIDATES
    # --------------------------------------------------------

    for _, b in x.iterrows():

        bank_text = b["source_text"]

        name_sim = similarity(
            pop_name,
            bank_text
        )

        ref_sim = similarity(
            pop_ref,
            bank_text
        )

        date_diff = int(
            b["date_difference_days"]
        )


        # ----------------------------------------------------
        # QUALITY SCORE
        # ----------------------------------------------------
        #
        # Bank/account/amount/date are HARD evidence.
        #
        # Text is only supporting evidence.
        # ----------------------------------------------------

        score = 0

        # Exact bank
        score += 1000

        # Exact account
        score += 1000

        # Exact amount
        score += 1000

        # Date quality
        if date_diff == 0:
            score += 500

        elif date_diff <= 2:
            score += 400

        elif date_diff <= 5:
            score += 300

        else:
            score += 100

        # Supporting evidence
        if name_sim >= 0.75:
            score += 20

        if ref_sim >= 0.75:
            score += 20


        candidate_rows.append({

            "case_number": case,

            "bank_row_id": int(
                b["bank_row_id"]
            ),

            "pop_amount": pop_amount,

            "pop_date": pop_date,

            "pop_bank": p["bank_name"],

            "pop_account": pop_account,

            "pop_customer": pop_name,

            "pop_reference": pop_ref,

            "bank_amount": b["credit_norm"],

            "bank_date": b["date_norm"],

            "date_difference_days": date_diff,

            "bank_name": b["bank_name"],

            "source_file": b["source_file"],

            "source_account": b["source_account"],

            "bank_description": b["description"],

            "bank_reference": b["reference"],

            "bank_customer_reference": b[
                "customer_reference"
            ],

            "name_similarity": round(
                name_sim,
                3
            ),

            "reference_similarity": round(
                ref_sim,
                3
            ),

            "score": score,

        })


candidates = pd.DataFrame(
    candidate_rows
)


print("\nGLOBAL ASSIGNMENT INPUT")
print("-" * 110)

print(
    "POP CASES WITH VALID CANDIDATES:",
    candidates["case_number"].nunique()
    if not candidates.empty
    else 0
)

print(
    "UNIQUE BANK CANDIDATE ROWS:",
    candidates["bank_row_id"].nunique()
    if not candidates.empty
    else 0
)

print(
    "TOTAL CANDIDATE EDGES:",
    len(candidates)
)


# ============================================================
# GLOBAL ONE-TO-ONE ASSIGNMENT
# ============================================================
#
# We use a maximum-cardinality bipartite matching.
#
# This is the critical part.
#
# We first maximize the NUMBER of matched POP cases.
# Only after that do we use score/date ordering.
#
# Therefore:
#
#   40 possible valid matches
#   30 bank rows
#
# => at most 30 POP cases will be matched.
#
# No bank row can ever be assigned twice.
# ============================================================


if candidates.empty:

    assignments = {}

else:

    # --------------------------------------------------------
    # Candidate dictionary
    # --------------------------------------------------------

    case_to_edges = {}

    for _, row in candidates.iterrows():

        case = row["case_number"]
        bank_id = int(
            row["bank_row_id"]
        )

        case_to_edges.setdefault(
            case,
            []
        ).append(row)


    # --------------------------------------------------------
    # Sort candidates:
    #
    # 1. Higher score
    # 2. Smaller date difference
    # 3. Smaller bank row ID
    #
    # This gives deterministic results.
    # --------------------------------------------------------

    for case in case_to_edges:

        case_to_edges[case].sort(
            key=lambda r: (
                -r["score"],
                r["date_difference_days"],
                r["bank_row_id"],
            )
        )


    # --------------------------------------------------------
    # Kuhn maximum bipartite matching
    # --------------------------------------------------------

    bank_owner = {}

    case_owner = {}


    def try_assign(case, visited):

        for row in case_to_edges.get(
            case,
            []
        ):

            bank_id = int(
                row["bank_row_id"]
            )

            if bank_id in visited:
                continue

            visited.add(bank_id)

            current_case = bank_owner.get(
                bank_id
            )

            if current_case is None:

                bank_owner[
                    bank_id
                ] = case

                case_owner[
                    case
                ] = bank_id

                return True


            if current_case == case:
                return True


            if try_assign(
                current_case,
                visited
            ):

                bank_owner[
                    bank_id
                ] = case

                case_owner[
                    case
                ] = bank_id

                return True


        return False


    # --------------------------------------------------------
    # Important:
    #
    # Cases with fewer choices are attempted first.
    #
    # This prevents flexible cases from stealing the only
    # transaction available to a constrained case.
    # --------------------------------------------------------

    ordered_cases = sorted(
        case_to_edges.keys(),
        key=lambda c: (
            len(case_to_edges[c]),
            -max(
                r["score"]
                for r in case_to_edges[c]
            ),
            c,
        )
    )


    for case in ordered_cases:

        try_assign(
            case,
            set()
        )


    assignments = case_owner


print("\nGLOBAL ASSIGNMENT RESULT")
print("-" * 110)

print(
    "VALID GLOBAL ASSIGNMENTS:",
    len(assignments)
)


# ============================================================
# BUILD FINAL RESULTS
# ============================================================

results = []


# ------------------------------------------------------------
# Lookup selected candidate by (case, bank row)
# ------------------------------------------------------------

selected_lookup = {}


for case, bank_id in assignments.items():

    matches = candidates[
        (candidates["case_number"] == case)
        & (
            candidates["bank_row_id"]
            == bank_id
        )
    ]

    if matches.empty:
        continue

    # There should only be one.
    selected_lookup[
        (case, bank_id)
    ] = matches.iloc[0]


# ============================================================
# FINAL CASE-BY-CASE OUTPUT
# ============================================================

for _, p in pop.iterrows():

    case = p["case_number"]

    pop_amount = safe_float(
        p["amount_norm"]
    )

    pop_date = p["pop_date_norm"]

    pop_bank = p["bank_name"]

    pop_account = p["account_norm"]

    pop_customer = p["customer_norm"]

    pop_reference = p["reference_norm"]


    # --------------------------------------------------------
    # MATCHED
    # --------------------------------------------------------

    if case in assignments:

        bank_id = assignments[case]

        selected = selected_lookup.get(
            (case, bank_id)
        )

        if selected is None:
            raise ValueError(
                f"Internal error: assignment exists "
                f"but candidate does not: "
                f"case={case}, bank={bank_id}"
            )


        results.append({

            "case_number": case,

            "status": "MATCHED",

            "match_reason": (
                "Exact bank + exact source account + "
                "exact credit amount + date within "
                f"+/- {DATE_WINDOW_DAYS} days"
            ),

            "pop_date": pop_date,

            "pop_amount": pop_amount,

            "pop_bank": pop_bank,

            "pop_account": pop_account,

            "pop_customer": pop_customer,

            "pop_reference": pop_reference,

            "bank_date": selected[
                "bank_date"
            ],

            "bank_amount": selected[
                "bank_amount"
            ],

            "bank_name": selected[
                "bank_name"
            ],

            "source_file": selected[
                "source_file"
            ],

            "source_account": selected[
                "source_account"
            ],

            "bank_row_id": selected[
                "bank_row_id"
            ],

            "bank_description": selected[
                "bank_description"
            ],

            "bank_reference": selected[
                "bank_reference"
            ],

            "bank_customer_reference": selected[
                "bank_customer_reference"
            ],

            "date_difference_days": selected[
                "date_difference_days"
            ],

            "name_similarity": selected[
                "name_similarity"
            ],

            "reference_similarity": selected[
                "reference_similarity"
            ],

            "score": selected[
                "score"
            ],

            "candidate_count": len(
                case_to_edges.get(
                    case,
                    []
                )
            ),

        })

        continue


    # --------------------------------------------------------
    # UNMATCHED
    # --------------------------------------------------------

    diag_row = diagnostic[
        diagnostic["case_number"]
        == case
    ]

    classification = (
        diag_row.iloc[0]["classification"]
        if not diag_row.empty
        else ""
    )


    if classification == (
        "AMOUNT_FOUND_SAME_BANK_WRONG_ACCOUNT"
    ):

        reason = (
            "Exact amount exists in same bank, "
            "but no transaction exists for the "
            "POP source account. Wrong-account "
            "transactions were intentionally rejected."
        )

        status = "NO_MATCH"


    elif classification == (
        "VALID_ACCOUNT_AMOUNT_NO_DATE_SUPPORT"
    ):

        reason = (
            "Exact bank + exact account + exact "
            "amount exists, but no transaction "
            f"falls within +/- {DATE_WINDOW_DAYS} days."
        )

        status = "NO_MATCH"


    elif classification == (
        "AMOUNT_FOUND_OTHER_BANK"
    ):

        reason = (
            "Amount exists in another bank, "
            "but exact POP bank requirement "
            "was not satisfied."
        )

        status = "NO_MATCH"


    elif classification == (
        "AMOUNT_NOT_FOUND_ANYWHERE"
    ):

        reason = (
            "POP amount not found in bank credit "
            "transactions."
        )

        status = "NO_MATCH"


    else:

        reason = (
            "Valid candidate existed but was not "
            "selected by global one-to-one assignment."
        )

        status = "NO_MATCH"


    results.append({

        "case_number": case,

        "status": status,

        "match_reason": reason,

        "pop_date": pop_date,

        "pop_amount": pop_amount,

        "pop_bank": pop_bank,

        "pop_account": pop_account,

        "pop_customer": pop_customer,

        "pop_reference": pop_reference,

        "bank_date": pd.NaT,

        "bank_amount": np.nan,

        "bank_name": "",

        "source_file": "",

        "source_account": "",

        "bank_row_id": np.nan,

        "bank_description": "",

        "bank_reference": "",

        "bank_customer_reference": "",

        "date_difference_days": np.nan,

        "name_similarity": np.nan,

        "reference_similarity": np.nan,

        "score": np.nan,

        "candidate_count": len(
            case_to_edges.get(
                case,
                []
            )
        ) if not candidates.empty else 0,

    })


result = pd.DataFrame(results)


# ============================================================
# FINAL VALIDATION
# ============================================================

print("\n")
print("=" * 110)
print("FINAL HARD-EVIDENCE VALIDATION")
print("=" * 110)


matched = result[
    result["status"] == "MATCHED"
].copy()


# ------------------------------------------------------------
# 1. No duplicate POP cases
# ------------------------------------------------------------

duplicate_pop = (
    matched["case_number"]
    .duplicated()
    .sum()
)


print(
    "DUPLICATE POP CASE ASSIGNMENTS:",
    duplicate_pop
)


if duplicate_pop != 0:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "same POP case assigned more than once."
    )


# ------------------------------------------------------------
# 2. No duplicate BANK rows
# ------------------------------------------------------------

duplicate_bank = (
    matched["bank_row_id"]
    .dropna()
    .duplicated()
    .sum()
)


print(
    "DUPLICATE BANK TRANSACTION ASSIGNMENTS:",
    duplicate_bank
)


if duplicate_bank != 0:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "same bank transaction assigned to "
        "multiple POP cases."
    )


# ------------------------------------------------------------
# 3. Exact amount validation
# ------------------------------------------------------------

invalid_amount = matched[
    ~np.isclose(
        matched["pop_amount"].astype(float),
        matched["bank_amount"].astype(float),
        atol=AMOUNT_TOLERANCE
    )
]


print(
    "INVALID AMOUNT MATCHES:",
    len(invalid_amount)
)


if not invalid_amount.empty:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "invalid amount match."
    )

# ------------------------------------------------------------
# 4. Exact bank validation
# ------------------------------------------------------------

# Canonical bank-name mapping.
# POP uses full bank names while normalized bank data
# uses short bank codes such as FAB, CBD, AJMAN.
BANK_CANONICAL = {
    "FIRST ABU DHABI BANK": "FAB",
    "FAB": "FAB",

    "COMMERCIAL BANK OF DUBAI": "CBD",
    "COMMERCIAL BANK OF DUBAI PJSC": "CBD",
    "CBD": "CBD",

    "AJMAN BANK": "AJMAN",
    "AJMAN": "AJMAN",

    "NATIONAL BANK OF FUJAIRAH": "NBF",
    "NBF": "NBF",

    "UNITED BANK LIMITED": "UBL",
    "UBL": "UBL",

    "UNITED ARAB BANK": "UAB",
    "UAB": "UAB",

    "MASHREQ": "MASHREQ",
    "MASHREQ BANK": "MASHREQ",

    "ABU DHABI COMMERCIAL BANK": "ADCB",
    "ADCB": "ADCB",

    "NATIONAL BANK OF RAS AL KHAIMAH": "NBRAK",
    "NATIONAL BANK OF RAS AL-KHAIMAH": "NBRAK",
    "NBRAK": "NBRAK",

    "ABU DHABI ISLAMIC BANK": "ADIB",
    "ADIB": "ADIB",

    "AL AHLI BANK OF KUWAIT": "ABK",
    "ABK": "ABK",

    "NATIONAL BANK OF BAHRAIN": "NBB",
    "NBB": "NBB",

    "INVEST BANK": "INVEST BANK",
}


def canonical_bank(x):
    """
    Convert POP/bank bank names into one canonical bank code
    for exact validation.
    """
    if pd.isna(x):
        return ""

    value = str(x).upper().strip()

    return BANK_CANONICAL.get(value, value)


matched = matched.copy()

matched["pop_bank_canonical"] = (
    matched["pop_bank"]
    .apply(canonical_bank)
)

matched["bank_name_canonical"] = (
    matched["bank_name"]
    .apply(canonical_bank)
)

invalid_bank = matched[
    matched["pop_bank_canonical"]
    !=
    matched["bank_name_canonical"]
]

print(
    "INVALID BANK MATCHES:",
    len(invalid_bank)
)

if not invalid_bank.empty:

    print("\nINVALID BANK DETAILS:")

    print(
        invalid_bank[
            [
                "case_number",
                "pop_bank",
                "pop_bank_canonical",
                "bank_name",
                "bank_name_canonical",
                "pop_account",
                "source_account",
                "pop_amount",
                "bank_amount",
            ]
        ].to_string(index=False)
    )

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "invalid bank match."
    )
# ------------------------------------------------------------
# 5. Exact account validation
# ------------------------------------------------------------

invalid_account = matched[
    matched["pop_account"]
    .astype(str)
    !=
    matched["source_account"]
    .astype(str)
]


print(
    "INVALID ACCOUNT MATCHES:",
    len(invalid_account)
)


if not invalid_account.empty:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "invalid account match."
    )


# ------------------------------------------------------------
# 6. Date validation
# ------------------------------------------------------------

invalid_date = matched[
    matched["date_difference_days"]
    > DATE_WINDOW_DAYS
]


print(
    "INVALID DATE MATCHES:",
    len(invalid_date)
)


if not invalid_date.empty:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "date outside permitted window."
    )


# ------------------------------------------------------------
# 7. Every matched row has a bank row ID
# ------------------------------------------------------------

missing_bank_id = matched[
    matched["bank_row_id"].isna()
]


print(
    "MATCHES WITHOUT BANK ROW ID:",
    len(missing_bank_id)
)


if not missing_bank_id.empty:

    raise ValueError(
        "FINAL VALIDATION FAILED: "
        "matched row has no bank transaction ID."
    )


print("\nALL FINAL VALIDATIONS PASSED.")


# ============================================================
# SAVE CANDIDATES
# ============================================================

if not candidates.empty:

    candidates = candidates.sort_values(
        [
            "case_number",
            "date_difference_days",
            "bank_row_id",
        ]
    )

else:

    candidates = pd.DataFrame()


candidates.to_excel(
    OUT_CAND,
    index=False
)


# ============================================================
# SAVE MATCH RESULTS
# ============================================================

result = result.sort_values(
    "case_number"
)

result.to_excel(
    OUT_MATCH,
    index=False
)


# ============================================================
# SAVE DIAGNOSTIC
# ============================================================

diagnostic = diagnostic.sort_values(
    "case_number"
)

diagnostic.to_excel(
    OUT_DIAG,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 110)
print("FINAL AUGUST MATCHING RESULT")
print("=" * 110)

print("\nSTATUS:")

print(
    result["status"]
    .value_counts(dropna=False)
    .to_string()
)


print(
    "\nTOTAL POP CASES:",
    len(pop)
)

print(
    "MATCHED:",
    len(matched)
)

print(
    "NOT MATCHED:",
    len(
        result[
            result["status"] != "MATCHED"
        ]
    )
)

print(
    "UNIQUE BANK TRANSACTIONS USED:",
    matched["bank_row_id"].nunique()
)


# ============================================================
# MATCHED CASES
# ============================================================

print("\n")
print("=" * 110)
print("MATCHED CASES")
print("=" * 110)

if matched.empty:

    print("NONE")

else:

    print(
        matched[
            [
                "case_number",
                "pop_date",
                "pop_amount",
                "pop_bank",
                "pop_account",
                "bank_date",
                "bank_amount",
                "bank_name",
                "source_file",
                "date_difference_days",
                "score",
            ]
        ]
        .to_string(index=False)
    )


# ============================================================
# NO MATCH CASES
# ============================================================

print("\n")
print("=" * 110)
print("NO MATCH CASES")
print("=" * 110)

no_match = result[
    result["status"] != "MATCHED"
]


if no_match.empty:

    print("NONE")

else:

    print(
        no_match[
            [
                "case_number",
                "pop_date",
                "pop_amount",
                "pop_bank",
                "pop_account",
                "candidate_count",
                "match_reason",
            ]
        ]
        .to_string(index=False)
    )


# ============================================================
# OUTPUT FILES
# ============================================================

print("\n")
print("=" * 110)
print("OUTPUT FILES")
print("=" * 110)

print("MATCHES:")
print(OUT_MATCH)

print("\nCANDIDATES:")
print(OUT_CAND)

print("\nDIAGNOSTIC:")
print(OUT_DIAG)

print("\nDONE.")
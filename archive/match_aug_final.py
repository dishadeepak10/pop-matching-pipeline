import re
from pathlib import Path
from difflib import SequenceMatcher

import numpy as np
import pandas as pd


# ============================================================
# AUGUST POP -> BANK FINAL MATCHER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

POP_FILE = BASE_DIR / "data" / "output" / "POP_AUG_MASTER.xlsx"
BANK_FILE = Path(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

OUTPUT_DIR = BASE_DIR / "data" / "output"
MATCH_FILE = OUTPUT_DIR / "POP_AUG_MATCHES_FINAL.xlsx"
CANDIDATE_FILE = OUTPUT_DIR / "POP_AUG_CANDIDATES_FINAL.xlsx"

DATE_WINDOW_DAYS = 15
NEAR_AMOUNT_TOLERANCE = 1.00

BANK_MAP = {
    "First Abu Dhabi Bank": "FAB",
    "Commercial Bank Of Dubai": "CBD",
    "Ajman Bank": "AJMAN",
}


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def norm_text(x):
    if pd.isna(x):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(x).upper())


def norm_account(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    s = re.sub(r"\.0$", "", s)
    return re.sub(r"[^0-9]", "", s)


def similarity(a, b):
    a = norm_text(a)
    b = norm_text(b)

    if not a or not b:
        return 0.0

    if a in b or b in a:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


def extract_account_from_source(source):
    if pd.isna(source):
        return ""

    s = str(source)

    # Account is normally the final 8-20 digit block in the filename.
    matches = re.findall(r"(?<!\d)(\d{8,20})(?!\d)", s)

    if not matches:
        return ""

    return matches[-1]


def best_date_difference(pop_date, bank_date, value_date):
    differences = []

    if pd.notna(pop_date) and pd.notna(bank_date):
        differences.append(abs((bank_date - pop_date).days))

    if pd.notna(pop_date) and pd.notna(value_date):
        differences.append(abs((value_date - pop_date).days))

    if not differences:
        return np.nan

    return min(differences)


# ============================================================
# LOAD DATA
# ============================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 110)
print("AUGUST FINAL POP -> BANK MATCHING ENGINE")
print("=" * 110)

print("\nLoading POP:")
print(POP_FILE)

pop = pd.read_excel(POP_FILE)

print("\nLoading normalized bank statements:")
print(BANK_FILE)

bank = pd.read_excel(BANK_FILE)


# ============================================================
# VALIDATE INPUTS
# ============================================================

required_pop = [
    "case_number",
    "pop_date",
    "receipt_reference",
    "receipt_amount",
    "bank_name",
    "customer_name",
    "bank_account_number",
]

required_bank = [
    "date",
    "value_date",
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
    raise ValueError(f"Missing POP columns: {missing_pop}")

if missing_bank:
    raise ValueError(f"Missing bank columns: {missing_bank}")


# ============================================================
# PREPARE POP
# ============================================================

pop["pop_date"] = pd.to_datetime(pop["pop_date"], errors="coerce")
pop["receipt_amount"] = pd.to_numeric(
    pop["receipt_amount"], errors="coerce"
)

pop["bank_code"] = pop["bank_name"].map(BANK_MAP)
pop["account_norm"] = pop["bank_account_number"].apply(norm_account)
pop["reference_norm"] = pop["receipt_reference"].apply(norm_text)
pop["customer_norm"] = pop["customer_name"].apply(norm_text)

print("\nPOP rows:", len(pop))


# ============================================================
# PREPARE BANK
# ============================================================

bank["date"] = pd.to_datetime(bank["date"], errors="coerce")
bank["value_date"] = pd.to_datetime(bank["value_date"], errors="coerce")
bank["credit_amount"] = pd.to_numeric(
    bank["credit_amount"], errors="coerce"
)

bank["source_account"] = bank["source_file"].apply(
    extract_account_from_source
)

bank["description_norm"] = bank["description"].apply(norm_text)
bank["reference_norm"] = bank["reference"].apply(norm_text)
bank["customer_reference_norm"] = bank["customer_reference"].apply(norm_text)

# Only credit transactions are relevant to POP receipts.
bank_credit = bank[
    bank["credit_amount"].notna()
    & (bank["credit_amount"] > 0)
].copy()

print("Total bank rows:", len(bank))
print("Credit transactions:", len(bank_credit))


# ============================================================
# CANDIDATE GENERATION
# ============================================================

candidate_rows = []

print("\nGenerating candidates...")


for _, p in pop.iterrows():

    case = p["case_number"]
    pop_amount = p["receipt_amount"]
    pop_date = p["pop_date"]
    pop_bank = p["bank_code"]
    pop_account = p["account_norm"]

    if pd.isna(pop_amount) or not pop_bank or not pop_account:
        continue

    # --------------------------------------------------------
    # HARD IDENTITY FILTER
    # --------------------------------------------------------

    candidates = bank_credit[
        (bank_credit["bank_name"] == pop_bank)
        &
        (bank_credit["source_account"] == pop_account)
    ].copy()

    if candidates.empty:
        continue

    # --------------------------------------------------------
    # AMOUNT FILTER
    # --------------------------------------------------------

    candidates["amount_difference"] = (
        candidates["credit_amount"] - float(pop_amount)
    ).abs()

    candidates = candidates[
        candidates["amount_difference"]
        <= NEAR_AMOUNT_TOLERANCE
    ].copy()

    if candidates.empty:
        continue

    candidates["amount_mode"] = np.where(
        candidates["amount_difference"] <= 0.01,
        "EXACT",
        "NEAR",
    )

    # --------------------------------------------------------
    # DATE EVIDENCE
    # --------------------------------------------------------

    candidates["date_difference_days"] = candidates.apply(
        lambda x: best_date_difference(
            pop_date,
            x["date"],
            x["value_date"],
        ),
        axis=1,
    )

    candidates = candidates[
        candidates["date_difference_days"].notna()
        &
        (
            candidates["date_difference_days"]
            <= DATE_WINDOW_DAYS
        )
    ].copy()

    if candidates.empty:
        continue

    # --------------------------------------------------------
    # SCORE EVIDENCE
    # --------------------------------------------------------

    for _, b in candidates.iterrows():

        ref_similarity = max(
            similarity(
                p["receipt_reference"],
                b["reference"],
            ),
            similarity(
                p["receipt_reference"],
                b["customer_reference"],
            ),
            similarity(
                p["receipt_reference"],
                b["description"],
            ),
        )

        customer_similarity = max(
            similarity(
                p["customer_name"],
                b["description"],
            ),
            similarity(
                p["customer_name"],
                b["customer_reference"],
            ),
        )

        # Base evidence:
        # exact bank + exact account + exact amount
        score = 70.0

        if b["amount_difference"] <= 0.01:
            score += 10
        else:
            score -= 5

        if b["date_difference_days"] == 0:
            score += 15
        elif b["date_difference_days"] <= 2:
            score += 10
        elif b["date_difference_days"] <= 5:
            score += 5

        if ref_similarity >= 0.90:
            score += 15
        elif ref_similarity >= 0.70:
            score += 8
        elif ref_similarity >= 0.50:
            score += 4

        if customer_similarity >= 0.90:
            score += 10
        elif customer_similarity >= 0.70:
            score += 6
        elif customer_similarity >= 0.50:
            score += 3

        candidate_rows.append({
            "case_number": case,
            "pop_date": pop_date,
            "pop_amount": pop_amount,
            "pop_bank": p["bank_name"],
            "pop_bank_code": pop_bank,
            "pop_account": pop_account,
            "pop_customer": p["customer_name"],
            "pop_reference": p["receipt_reference"],

            "bank_date": b["date"],
            "bank_value_date": b["value_date"],
            "bank_amount": b["credit_amount"],
            "amount_difference": b["amount_difference"],
            "amount_mode": b["amount_mode"],

            "bank_name": b["bank_name"],
            "bank_account": b["source_account"],
            "source_file": b["source_file"],
            "bank_description": b["description"],
            "bank_reference": b["reference"],
            "bank_customer_reference": b["customer_reference"],

            "date_difference_days": b["date_difference_days"],
            "reference_similarity": round(ref_similarity, 3),
            "customer_similarity": round(customer_similarity, 3),

            "score": round(score, 2),
            "bank_row_index": b.name,
        })


candidates = pd.DataFrame(candidate_rows)


# ============================================================
# NO CANDIDATE CASES
# ============================================================

if candidates.empty:
    raise ValueError(
        "No candidates were generated. "
        "Check bank/account/amount/date filters."
    )


# ============================================================
# RANK CANDIDATES
# ============================================================

candidates = candidates.sort_values(
    [
        "case_number",
        "score",
        "amount_difference",
        "date_difference_days",
        "reference_similarity",
        "customer_similarity",
    ],
    ascending=[
        True,
        False,
        True,
        True,
        False,
        False,
    ],
)

candidates["candidate_rank"] = (
    candidates.groupby("case_number").cumcount() + 1
)

candidate_counts = (
    candidates.groupby("case_number")
    .size()
    .rename("candidate_count")
)

candidates = candidates.merge(
    candidate_counts,
    on="case_number",
    how="left",
)


# ============================================================
# FINAL DECISION
# ============================================================

final_rows = []

for case, group in candidates.groupby("case_number"):

    group = group.sort_values(
        [
            "score",
            "amount_difference",
            "date_difference_days",
            "reference_similarity",
            "customer_similarity",
        ],
        ascending=[
            False,
            True,
            True,
            False,
            False,
        ],
    ).reset_index(drop=True)

    best = group.iloc[0]

    best_score = float(best["score"])

    if len(group) > 1:
        second_score = float(group.iloc[1]["score"])
        score_gap = best_score - second_score
    else:
        second_score = np.nan
        score_gap = np.nan

    # --------------------------------------------------------
    # DECISION RULES
    # --------------------------------------------------------

    if best["amount_mode"] == "NEAR":

        if (
            best_score >= 95
            and (
                len(group) == 1
                or score_gap >= 10
            )
        ):
            status = "NEAR_AMOUNT"
            reason = (
                "Near amount with strong "
                "account/date/reference/customer evidence"
            )
        else:
            status = "AMBIGUOUS"
            reason = "Near amount requires stronger separation"

    else:

        # Exact amount + exact bank + exact source account
        if len(group) == 1:
            status = "MATCHED"
            reason = (
                "Unique exact bank + source-account + "
                "credit amount candidate"
            )

        elif score_gap >= 12:
            status = "MATCHED"
            reason = (
                "Clear highest-scoring exact-amount "
                "candidate with sufficient separation"
            )

        else:
            status = "AMBIGUOUS"
            reason = (
                "Multiple exact-amount candidates "
                "without sufficient score separation"
            )

    final_rows.append({
        "case_number": case,
        "status": status,
        "match_reason": reason,

        "candidate_count": len(group),
        "score": best_score,
        "score_gap": score_gap,

        "pop_date": best["pop_date"],
        "pop_amount": best["pop_amount"],
        "pop_bank": best["pop_bank"],
        "pop_account": best["pop_account"],
        "pop_customer": best["pop_customer"],
        "pop_reference": best["pop_reference"],

        "bank_date": best["bank_date"],
        "bank_value_date": best["bank_value_date"],
        "bank_amount": best["bank_amount"],
        "amount_difference": best["amount_difference"],
        "amount_mode": best["amount_mode"],

        "bank_name": best["bank_name"],
        "bank_account": best["bank_account"],
        "source_file": best["source_file"],
        "bank_description": best["bank_description"],
        "bank_reference": best["bank_reference"],
        "bank_customer_reference": best["bank_customer_reference"],

        "date_difference_days": best["date_difference_days"],
        "reference_similarity": best["reference_similarity"],
        "customer_similarity": best["customer_similarity"],

        "bank_row_index": best["bank_row_index"],
    })


final = pd.DataFrame(final_rows)


# ============================================================
# CASES WITH ZERO CANDIDATES
# ============================================================

matched_cases = set(candidates["case_number"])

for _, p in pop.iterrows():

    case = p["case_number"]

    if case in matched_cases:
        continue

    final_rows.append({
        "case_number": case,
        "status": "NO_MATCH",
        "match_reason": (
            "No bank transaction satisfied "
            "bank + account + amount + date criteria"
        ),
        "candidate_count": 0,
        "score": np.nan,
        "score_gap": np.nan,

        "pop_date": p["pop_date"],
        "pop_amount": p["receipt_amount"],
        "pop_bank": p["bank_name"],
        "pop_account": p["account_norm"],
        "pop_customer": p["customer_name"],
        "pop_reference": p["receipt_reference"],

        "bank_date": pd.NaT,
        "bank_value_date": pd.NaT,
        "bank_amount": np.nan,
        "amount_difference": np.nan,
        "amount_mode": np.nan,

        "bank_name": np.nan,
        "bank_account": np.nan,
        "source_file": np.nan,
        "bank_description": np.nan,
        "bank_reference": np.nan,
        "bank_customer_reference": np.nan,

        "date_difference_days": np.nan,
        "reference_similarity": np.nan,
        "customer_similarity": np.nan,
        "bank_row_index": np.nan,
    })


final = pd.DataFrame(final_rows)

final = final.sort_values("case_number").reset_index(drop=True)


# ============================================================
# CANDIDATE OUTPUT
# ============================================================

candidates = candidates.sort_values(
    ["case_number", "candidate_rank"]
).reset_index(drop=True)

candidates.to_excel(
    CANDIDATE_FILE,
    index=False,
)


# ============================================================
# FINAL OUTPUT
# ============================================================

final.to_excel(
    MATCH_FILE,
    index=False,
)


# ============================================================
# SUMMARY
# ============================================================

print("\n")
print("=" * 110)
print("AUGUST FINAL MATCHING COMPLETE")
print("=" * 110)

print("\nPOP ROWS:", len(pop))
print("CASES WITH CANDIDATES:", candidates["case_number"].nunique())
print("TOTAL CANDIDATES:", len(candidates))

print("\nFINAL STATUS:")
print(
    final["status"]
    .value_counts()
    .sort_index()
    .to_string()
)

print("\nMATCHED CASES:")
print(
    final[
        final["status"].eq("MATCHED")
    ][
        [
            "case_number",
            "pop_amount",
            "pop_bank",
            "pop_account",
            "bank_amount",
            "bank_name",
            "source_file",
            "date_difference_days",
            "score",
            "candidate_count",
        ]
    ].to_string(index=False)
)

print("\nAMBIGUOUS CASES:")
print(
    final[
        final["status"].eq("AMBIGUOUS")
    ][
        [
            "case_number",
            "pop_amount",
            "pop_bank",
            "pop_account",
            "bank_amount",
            "bank_name",
            "source_file",
            "score",
            "score_gap",
            "candidate_count",
        ]
    ].to_string(index=False)
)

print("\nNO MATCH CASES:")
print(
    final[
        final["status"].eq("NO_MATCH")
    ][
        [
            "case_number",
            "pop_amount",
            "pop_bank",
            "pop_account",
            "match_reason",
        ]
    ].to_string(index=False)
)

print("\n")
print("=" * 110)
print("OUTPUT FILES")
print("=" * 110)
print(MATCH_FILE)
print(CANDIDATE_FILE)

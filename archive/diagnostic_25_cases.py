import pandas as pd


# ============================================================
# AUGUST — 25 CASE ACCOUNT / AMOUNT INVESTIGATION
# ============================================================

POP_PATH = r"D:\Disha_Workarea\pop_process\data\output\POP_AUG_MASTER.xlsx"
BANK_PATH = r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"


print("=" * 110)
print("AUGUST 25 CASE ACCOUNT / AMOUNT INVESTIGATION")
print("=" * 110)


# ============================================================
# LOAD POP
# ============================================================

pop = pd.read_excel(POP_PATH)

pop = pop.rename(
    columns={
        "bank_name": "pop_bank_raw",
        "bank_account_number": "pop_account",
        "receipt_amount": "pop_amount",
    }
)

BANK_MAP = {
    "FIRST ABU DHABI BANK": "FAB",
    "COMMERCIAL BANK OF DUBAI": "CBD",
    "AJMAN BANK": "AJMAN",
}

pop["pop_bank"] = (
    pop["pop_bank_raw"]
    .astype(str)
    .str.upper()
    .str.strip()
    .map(BANK_MAP)
)

pop["pop_account"] = (
    pop["pop_account"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.lstrip("0")
)

pop["pop_amount"] = pd.to_numeric(
    pop["pop_amount"],
    errors="coerce"
)

pop["pop_date"] = pd.to_datetime(
    pop["pop_date"],
    errors="coerce"
)


# ============================================================
# LOAD BANK
# ============================================================

bank = pd.read_excel(BANK_PATH)

bank["effective_bank"] = (
    bank["bank_name"]
    .astype(str)
    .str.upper()
    .str.strip()
)

bank["source_account"] = (
    bank["source_file"]
    .astype(str)
    .str.extract(r"(\d{8,})", expand=False)
)

bank["source_account"] = (
    bank["source_account"]
    .astype("string")
    .str.replace(r"^0+", "", regex=True)
)

bank["amount"] = pd.to_numeric(
    bank["credit_amount"],
    errors="coerce"
)

bank["date"] = pd.to_datetime(
    bank["date"],
    errors="coerce"
)

bank = bank[bank["amount"].notna()].copy()


# ============================================================
# FIND THE 25 CASES
# ============================================================

exact = pop.merge(
    bank[
        [
            "effective_bank",
            "source_account",
            "amount",
        ]
    ],
    left_on=[
        "pop_bank",
        "pop_account",
        "pop_amount",
    ],
    right_on=[
        "effective_bank",
        "source_account",
        "amount",
    ],
    how="inner",
)

cases = pop[
    ~pop["case_number"].isin(exact["case_number"])
].copy()


print(f"\n25-CASE EXCEPTIONS FOUND: {len(cases)}")


# ============================================================
# INVESTIGATE EACH CASE
# ============================================================

results = []

for _, r in cases.iterrows():

    same_bank = bank[
        (bank["effective_bank"] == r["pop_bank"]) &
        (bank["amount"] == r["pop_amount"])
    ].copy()

    exact_account = same_bank[
        same_bank["source_account"] == r["pop_account"]
    ].copy()

    any_bank = bank[
        bank["amount"] == r["pop_amount"]
    ].copy()

    same_bank_accounts = sorted(
        same_bank["source_account"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    same_bank_dates = sorted(
        same_bank["date"]
        .dropna()
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )

    results.append(
        {
            "case_number": r["case_number"],
            "pop_date": r["pop_date"].strftime("%Y-%m-%d"),
            "pop_amount": r["pop_amount"],
            "pop_bank": r["pop_bank"],
            "pop_account": r["pop_account"],
            "same_bank_amount_rows": len(same_bank),
            "exact_account_amount_rows": len(exact_account),
            "same_bank_accounts": " | ".join(same_bank_accounts),
            "same_bank_dates": " | ".join(same_bank_dates),
            "any_bank_amount_rows": len(any_bank),
        }
    )


result = pd.DataFrame(results)


# ============================================================
# CLASSIFICATION
# ============================================================

def classify(row):

    if row["exact_account_amount_rows"] > 0:
        return "EXACT_ACCOUNT_AMOUNT_FOUND"

    if row["same_bank_amount_rows"] > 0:
        return "AMOUNT_FOUND_SAME_BANK_WRONG_ACCOUNT"

    if row["any_bank_amount_rows"] > 0:
        return "AMOUNT_FOUND_OTHER_BANK"

    return "AMOUNT_NOT_FOUND_ANYWHERE"


result["classification"] = result.apply(
    classify,
    axis=1
)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 110)
print("CLASSIFICATION SUMMARY")
print("=" * 110)

print(
    result["classification"]
    .value_counts()
    .to_string()
)


# ============================================================
# FULL 25-CASE TABLE
# ============================================================

print("\n" + "=" * 110)
print("FULL 25-CASE INVESTIGATION")
print("=" * 110)

print(
    result[
        [
            "case_number",
            "pop_date",
            "pop_amount",
            "pop_bank",
            "pop_account",
            "same_bank_amount_rows",
            "exact_account_amount_rows",
            "same_bank_accounts",
            "same_bank_dates",
            "any_bank_amount_rows",
            "classification",
        ]
    ].to_string(index=False)
)


# ============================================================
# SAVE RESULT
# ============================================================

OUTPUT = r"D:\Disha_Workarea\pop_process\data\output\POP_AUG_25_CASE_ACCOUNT_DIAGNOSTIC.xlsx"

result.to_excel(
    OUTPUT,
    index=False
)

print("\n" + "=" * 110)
print("OUTPUT")
print("=" * 110)

print(OUTPUT)

print("\n" + "=" * 110)
print("DIAGNOSTIC COMPLETE")
print("=" * 110)
from pathlib import Path
import pandas as pd

INPUT_FILE = Path(
    r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
)

df = pd.read_excel(INPUT_FILE)

print("=" * 100)
print("NORMALIZED DATA QUALITY AUDIT")
print("=" * 100)

print(f"\nSHAPE: {df.shape}")

# ============================================================
# 1. BANK COUNTS
# ============================================================

print("\n" + "=" * 100)
print("ROWS BY BANK")
print("=" * 100)

print(
    df["bank_name"]
    .value_counts()
    .to_string()
)

# ============================================================
# 2. MISSING VALUES
# ============================================================

print("\n" + "=" * 100)
print("MISSING VALUES")
print("=" * 100)

print(
    df.isna()
    .sum()
    .to_string()
)

# ============================================================
# 3. MISSING VALUES BY BANK
# ============================================================

print("\n" + "=" * 100)
print("MISSING VALUES BY BANK")
print("=" * 100)

for bank, group in df.groupby("bank_name"):
    print(f"\n--- {bank} ({len(group)} rows) ---")
    print(
        group.isna()
        .sum()
        .to_string()
    )

# ============================================================
# 4. DEBIT / CREDIT PATTERNS
# ============================================================

debit_present = df["debit_amount"].notna()
credit_present = df["credit_amount"].notna()

both = debit_present & credit_present
debit_only = debit_present & ~credit_present
credit_only = ~debit_present & credit_present
neither = ~debit_present & ~credit_present

print("\n" + "=" * 100)
print("DEBIT / CREDIT PATTERNS")
print("=" * 100)

print(f"DEBIT ONLY : {debit_only.sum()}")
print(f"CREDIT ONLY: {credit_only.sum()}")
print(f"BOTH       : {both.sum()}")
print(f"NEITHER    : {neither.sum()}")

# ============================================================
# 5. DEBIT / CREDIT PATTERNS BY BANK
# ============================================================

print("\n" + "=" * 100)
print("DEBIT / CREDIT PATTERNS BY BANK")
print("=" * 100)

for bank, group in df.groupby("bank_name"):
    d = group["debit_amount"].notna()
    c = group["credit_amount"].notna()

    print(
        f"{bank:15} "
        f"debit_only={int((d & ~c).sum()):6} "
        f"credit_only={int((~d & c).sum()):6} "
        f"both={int((d & c).sum()):6} "
        f"neither={int((~d & ~c).sum()):6}"
    )

# ============================================================
# 6. MISSING DATE
# ============================================================

print("\n" + "=" * 100)
print("DATE QUALITY")
print("=" * 100)

date_missing = df["date"].isna()
value_date_missing = df["value_date"].isna()

print(f"DATE MISSING       : {date_missing.sum()}")
print(f"VALUE DATE MISSING : {value_date_missing.sum()}")
print(
    f"BOTH DATE MISSING  : "
    f"{(date_missing & value_date_missing).sum()}"
)

# ============================================================
# 7. MISSING DESCRIPTION
# ============================================================

print("\n" + "=" * 100)
print("TEXT FIELD QUALITY")
print("=" * 100)

for col in [
    "description",
    "reference",
    "customer_reference",
    "transaction_type",
]:
    missing = (
        df[col].isna()
        | df[col].astype(str).str.strip().eq("")
    )

    print(
        f"{col:25} {missing.sum()}"
    )

# ============================================================
# 8. DUPLICATES
# ============================================================

print("\n" + "=" * 100)
print("DUPLICATE CHECK")
print("=" * 100)

duplicate_columns = [
    "date",
    "value_date",
    "description",
    "reference",
    "customer_reference",
    "debit_amount",
    "credit_amount",
    "balance",
    "bank_name",
]

duplicates = df.duplicated(
    subset=duplicate_columns,
    keep=False,
)

print(
    f"POTENTIAL DUPLICATE ROWS: "
    f"{duplicates.sum()}"
)

if duplicates.any():
    print("\nDUPLICATES BY BANK:")
    print(
        df.loc[duplicates, "bank_name"]
        .value_counts()
        .to_string()
    )

# ============================================================
# 9. BALANCE MISSING
# ============================================================

print("\n" + "=" * 100)
print("BALANCE QUALITY")
print("=" * 100)

print(
    f"MISSING BALANCE: "
    f"{df['balance'].isna().sum()}"
)

# ============================================================
# 10. SUSPICIOUS TRANSACTIONS
# ============================================================

suspicious = (
    df["date"].isna()
    |
    (
        df["debit_amount"].isna()
        &
        df["credit_amount"].isna()
    )
)

print("\n" + "=" * 100)
print("SUSPICIOUS ROWS")
print("=" * 100)

print(
    f"SUSPICIOUS ROWS: "
    f"{suspicious.sum()}"
)

if suspicious.any():
    print("\nSUSPICIOUS ROW PREVIEW:")
    print(
        df.loc[
            suspicious
        ].head(30).to_string(index=False)
    )

print("\n" + "=" * 100)
print("AUDIT COMPLETE")
print("=" * 100)
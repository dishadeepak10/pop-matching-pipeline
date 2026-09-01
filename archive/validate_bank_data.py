from pathlib import Path
import pandas as pd
import normalize_bank_statements as nbs


root = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

files = [
    p
    for p in root.iterdir()
    if p.is_file()
    and p.suffix.lower() in {".xls", ".xlsx"}
    and p.name.upper().startswith(("ADCB", "FAB", "CBD"))
]

required = [
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

issues = []
total_rows = 0

print("=" * 100)
print("DATA VALIDATION")
print("=" * 100)
print("FILES:", len(files))

for i, path in enumerate(files, 1):

    print(f"\n[{i}/{len(files)}] {path.name}")

    try:
        df = nbs.process_file(path)

        if df is None:
            issues.append(
                (path.name, "Returned None")
            )
            continue

        total_rows += len(df)

        print("  ROWS:", len(df))

        # ------------------------------------------------
        # REQUIRED COLUMNS
        # ------------------------------------------------

        for column in required:
            if column not in df.columns:
                issues.append(
                    (
                        path.name,
                        f"MISSING COLUMN: {column}",
                    )
                )

        # ------------------------------------------------
        # DATE VALIDATION
        # ------------------------------------------------

        for column in ["date", "value_date"]:

            if column not in df.columns:
                continue

            parsed = pd.to_datetime(
                df[column],
                errors="coerce",
            )

            bad = (
                df[column].notna()
                & parsed.isna()
            )

            if bad.any():
                issues.append(
                    (
                        path.name,
                        f"INVALID {column}: {bad.sum()}",
                    )
                )

        # ------------------------------------------------
        # NUMERIC VALIDATION
        # ------------------------------------------------

        for column in [
            "debit_amount",
            "credit_amount",
            "balance",
        ]:

            if column not in df.columns:
                continue

            numeric = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            bad = (
                df[column].notna()
                & numeric.isna()
            )

            if bad.any():
                issues.append(
                    (
                        path.name,
                        f"NON-NUMERIC {column}: {bad.sum()}",
                    )
                )

        # ------------------------------------------------
        # BANK NAME
        # ------------------------------------------------

        if "bank_name" in df.columns:

            missing_bank = df["bank_name"].isna()

            if missing_bank.any():
                issues.append(
                    (
                        path.name,
                        f"MISSING bank_name: {missing_bank.sum()}",
                    )
                )

        # ------------------------------------------------
        # SOURCE FILE
        # ------------------------------------------------

        if "source_file" in df.columns:

            missing_source = df["source_file"].isna()

            if missing_source.any():
                issues.append(
                    (
                        path.name,
                        f"MISSING source_file: {missing_source.sum()}",
                    )
                )

    except Exception as exc:

        issues.append(
            (
                path.name,
                f"PROCESSING ERROR: {repr(exc)}",
            )
        )


print("\n")
print("=" * 100)
print("FINAL DATA VALIDATION SUMMARY")
print("=" * 100)

print("FILES CHECKED:", len(files))
print("TOTAL TRANSACTION ROWS:", total_rows)
print("ISSUES FOUND:", len(issues))

if issues:

    print("\nISSUES:")

    for filename, issue in issues:
        print(
            f"  {filename} -> {issue}"
        )

else:

    print("\nNO DATA-LEVEL ISSUES FOUND.")
from pathlib import Path
import pandas as pd
import normalize_bank_statements as nbs

BASE = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

EXPECTED_COLUMNS = [
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

files = [
    p for p in sorted(BASE.iterdir())
    if p.is_file()
    and p.suffix.lower() in nbs.SUPPORTED_EXTENSIONS
    and p.name.lower() not in {
    "normalized_bank_statements.xlsx",
    "source_inventory.xlsx",
    "zero_file_diagnosis.xlsx",
    "batch_validation_results.xlsx",
   }
]

print("=" * 120)
print("BATCH DATA VALIDATION")
print("=" * 120)
print(f"TOTAL FILES: {len(files)}")

results = []

for i, file in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {file.name}")

    try:
        df = nbs.process_file(file)

        errors = []

        # --------------------------------------------------
        # 1. SCHEMA
        # --------------------------------------------------
        missing_columns = [
            c for c in EXPECTED_COLUMNS
            if c not in df.columns
        ]

        extra_columns = [
            c for c in df.columns
            if c not in EXPECTED_COLUMNS
        ]

        if missing_columns:
            errors.append(
                f"missing columns={missing_columns}"
            )

        if extra_columns:
            errors.append(
                f"unexpected columns={extra_columns}"
            )

        # --------------------------------------------------
        # 2. DATE VALIDATION
        # --------------------------------------------------
        invalid_date_rows = 0

        if "date" in df.columns and not df.empty:
            parsed_dates = pd.to_datetime(
                df["date"],
                errors="coerce"
            )

            invalid_date_rows = int(
            (
                parsed_dates.isna()
                & df["date"].notna()
            ).sum()
        )

            if invalid_date_rows:
                errors.append(
                    f"invalid date rows={invalid_date_rows}"
                )

            # --------------------------------------------------
            # 3. VALUE DATE VALIDATION
            # --------------------------------------------------
            invalid_value_date_rows = 0

            if "value_date" in df.columns and not df.empty:
                parsed_value_dates = pd.to_datetime(
                    df["value_date"],
                    errors="coerce"
                )

                invalid_value_date_rows = int(
                    (
                        parsed_value_dates.isna()
                        & df["value_date"].notna()
                    ).sum()
                )

                if invalid_value_date_rows:
                    errors.append(
                        f"invalid value_date rows={invalid_value_date_rows}"
                    )
        # --------------------------------------------------
        # 4. AMOUNT VALIDATION
        # --------------------------------------------------
        invalid_debit = 0
        invalid_credit = 0
        invalid_balance = 0

        if not df.empty:

            if "debit_amount" in df.columns:
                debit_numeric = pd.to_numeric(
                    df["debit_amount"],
                    errors="coerce"
                )

                invalid_debit = int(
                    (
                        debit_numeric.isna()
                        & df["debit_amount"].notna()
                    ).sum()
                )

            if "credit_amount" in df.columns:
                credit_numeric = pd.to_numeric(
                    df["credit_amount"],
                    errors="coerce"
                )

                invalid_credit = int(
                    (
                        credit_numeric.isna()
                        & df["credit_amount"].notna()
                    ).sum()
                )

            if "balance" in df.columns:
                balance_numeric = pd.to_numeric(
                    df["balance"],
                    errors="coerce"
                )

                invalid_balance = int(
                    (
                        balance_numeric.isna()
                        & df["balance"].notna()
                    ).sum()
                )

        if invalid_debit:
            errors.append(
                f"invalid debit_amount rows={invalid_debit}"
            )

        if invalid_credit:
            errors.append(
                f"invalid credit_amount rows={invalid_credit}"
            )

        if invalid_balance:
            errors.append(
                f"invalid balance rows={invalid_balance}"
                    ) 
        # --------------------------------------------------
        # 5. DEBIT + CREDIT BOTH POPULATED
        # --------------------------------------------------
        both_debit_credit = 0

        if not df.empty:
            debit_numeric = pd.to_numeric(
                df["debit_amount"],
                errors="coerce"
            )

            credit_numeric = pd.to_numeric(
                df["credit_amount"],
                errors="coerce"
            )

            both_debit_credit = int(
                (
                    debit_numeric.notna()
                    & credit_numeric.notna()
                    & debit_numeric.ne(0)
                    & credit_numeric.ne(0)
                ).sum()
            )

        if both_debit_credit:
            errors.append(
                f"both debit+credit populated={both_debit_credit}"
            )

        # --------------------------------------------------
        # 6. BANK NAME
        # --------------------------------------------------
        bad_bank_name = 0

        if "bank_name" in df.columns and not df.empty:
            bad_bank_name = int(
                df["bank_name"].isna().sum()
            )

            if bad_bank_name:
                errors.append(
                    f"missing bank_name rows={bad_bank_name}"
                )

        # --------------------------------------------------
        # 7. SOURCE FILE
        # --------------------------------------------------
        bad_source_file = 0

        if "source_file" in df.columns and not df.empty:
            bad_source_file = int(
                (df["source_file"] != file.name).sum()
            )

            if bad_source_file:
                errors.append(
                    f"wrong source_file rows={bad_source_file}"
                )
        # --------------------------------------------------
        # RESULT
        # --------------------------------------------------
        status = "PASS" if not errors else "FAIL"

        results.append({
            "file": file.name,
            "status": status,
            "rows": len(df),
            "errors": " | ".join(errors),
        })

        print(
            f"  {status} | rows={len(df)}"
            + (
                f" | {' | '.join(errors)}"
                if errors
                else ""
            )
        )

    except Exception as exc:
        results.append({
            "file": file.name,
            "status": "PROCESSING_ERROR",
            "rows": 0,
            "errors": repr(exc),
        })

        print(
            f"  PROCESSING_ERROR | {repr(exc)}"
        )
# ============================================================
# FINAL SUMMARY
# ============================================================

result_df = pd.DataFrame(results)

print("\n")
print("=" * 120)
print("FINAL VALIDATION SUMMARY")
print("=" * 120)

print(
    f"TOTAL FILES      : {len(result_df)}"
)

print(
    f"PASS             : "
    f"{(result_df['status'] == 'PASS').sum()}"
)

print(
    f"FAIL             : "
    f"{(result_df['status'] == 'FAIL').sum()}"
)

print(
    f"PROCESSING ERROR : "
    f"{(result_df['status'] == 'PROCESSING_ERROR').sum()}"
)

print("\n")

failures = result_df[
    result_df["status"] != "PASS"
]

if failures.empty:
    print("ALL DATA VALIDATION CHECKS PASSED.")
else:
    print("FAILURES:")
    print(
        failures.to_string(index=False)
    )

output = BASE / "batch_validation_results.xlsx"

result_df.to_excel(
    output,
    index=False
)

print("\nRESULT FILE:")
print(output)
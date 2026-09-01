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

issues = []
checked_rows = 0
checked_balance_rows = 0


print("=" * 100)
print("TRANSACTION INTEGRITY VALIDATION")
print("=" * 100)
print("FILES:", len(files))


for i, path in enumerate(files, 1):

    print(f"\n[{i}/{len(files)}] {path.name}")

    try:
        df = nbs.process_file(path)

        if df is None or df.empty:
            print("  ROWS: 0")
            continue

        checked_rows += len(df)

        # Convert numeric columns
        debit = pd.to_numeric(
            df["debit_amount"],
            errors="coerce",
        ).fillna(0)

        credit = pd.to_numeric(
            df["credit_amount"],
            errors="coerce",
        ).fillna(0)

        balance = pd.to_numeric(
            df["balance"],
            errors="coerce",
        )

        # ------------------------------------------------
        # BOTH DEBIT AND CREDIT
        # ------------------------------------------------

        both = (
            (debit != 0)
            & (credit != 0)
        )

        if both.any():

            issues.append(
                (
                    path.name,
                    f"{both.sum()} rows have BOTH debit and credit",
                )
            )

        # ------------------------------------------------
        # NEITHER DEBIT NOR CREDIT
        # ------------------------------------------------

        neither = (
            (debit == 0)
            & (credit == 0)
        )

        if neither.any():

            issues.append(
                (
                    path.name,
                    f"{neither.sum()} rows have neither debit nor credit",
                )
            )
        # ------------------------------------------------
        # RUNNING BALANCE CHECK
        # ------------------------------------------------

        # Detect the balance convention used by this statement.
        # Some FAB statements decrease balance for credits,
        # while others use the standard:
        # previous + credit - debit
        #
        # Infer the convention from the actual statement instead
        # of assuming one universal formula.

        balance_delta = balance.diff()

        standard_matches = (
            (balance_delta - credit + debit).abs() <= 0.01
        ).sum()

        credit_decrease_matches = (
            (balance_delta + credit - debit).abs() <= 0.01
        ).sum()

        if credit_decrease_matches > standard_matches:
            balance_mode = "CREDIT_DECREASE"
        else:
            balance_mode = "STANDARD"

        for j in range(1, len(df)):

            previous_balance = balance.iloc[j - 1]
            current_balance = balance.iloc[j]

            if pd.isna(previous_balance):
                continue

            if pd.isna(current_balance):
                continue

            if balance_mode == "CREDIT_DECREASE":
                expected = (
                    previous_balance
                    - credit.iloc[j]
                    + debit.iloc[j]
                )
            else:
                expected = (
                    previous_balance
                    + credit.iloc[j]
                    - debit.iloc[j]
                )

            if abs(expected - current_balance) > 0.01:

                issues.append(
                    (
                        path.name,
                        (
                            f"Balance mismatch at row {j}: "
                            f"previous={previous_balance}, "
                            f"debit={debit.iloc[j]}, "
                            f"credit={credit.iloc[j]}, "
                            f"actual={current_balance}, "
                            f"expected={expected}, "
                            f"mode={balance_mode}"
                        ),
                    )
                )

                # Don't report thousands of mismatches
                # from the same file.
                if sum(
                    1
                    for x in issues
                    if x[0] == path.name
                ) >= 10:
                    break

            checked_balance_rows += 1
        print("  ROWS:", len(df))

    except Exception as exc:

        issues.append(
            (
                path.name,
                f"PROCESSING ERROR: {repr(exc)}",
            )
        )


print("\n")
print("=" * 100)
print("FINAL TRANSACTION INTEGRITY SUMMARY")
print("=" * 100)

print("FILES CHECKED:", len(files))
print("TRANSACTION ROWS CHECKED:", checked_rows)
print("BALANCE ROWS CHECKED:", checked_balance_rows)
print("ISSUES FOUND:", len(issues))


if issues:

    print("\nISSUES:")

    for filename, issue in issues:
        print(
            f"  {filename} -> {issue}"
        )

else:

    print("\nNO TRANSACTION INTEGRITY ISSUES FOUND.")
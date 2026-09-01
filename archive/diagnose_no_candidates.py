import pandas as pd

POP_FILE = r"data\output\POP_email_merged_final.xlsx"
BANK_FILE = r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"

CASES = [84373, 84375, 84401, 84696, 84725]

pop = pd.read_excel(POP_FILE)
bank = pd.read_excel(BANK_FILE)

bank["date"] = pd.to_datetime(
    bank["date"],
    errors="coerce",
    dayfirst=True,
)

print("=" * 120)
print("NO-CANDIDATE BANK DIAGNOSTIC")
print("=" * 120)

for case in CASES:

    pop_row = pop.loc[
        pop["case_number"] == case
    ].iloc[0]

    amounts = []

    for col in [
        "email_receipt_amount",
        "pop_amount",
        "pop_original_amount",
    ]:
        value = pop_row.get(col)

        if pd.notna(value):
            try:
                amounts.append(float(value))
            except Exception:
                pass

    print("\n" + "=" * 120)
    print(f"CASE {case}")
    print("=" * 120)

    print("\nPOP:")
    print(
        pop.loc[
            pop["case_number"] == case,
            [
                "case_number",
                "sender_name",
                "transaction_date",
                "email_receipt_amount",
                "pop_amount",
                "pop_original_amount",
                "pop_original_currency",
                "pop_exchange_rate",
                "reference_number",
            ],
        ].to_string(index=False)
    )

    print("\nPOP AMOUNT VARIANTS:")
    print(amounts)

    if not amounts:
        print("\nNO NUMERIC POP AMOUNT")
        continue

    # Find bank rows within +/- 5 AED of ANY POP amount.
    mask = pd.Series(False, index=bank.index)

    for amount in amounts:
        debit_diff = (
            bank["debit_amount"].abs() - amount
        ).abs()

        credit_diff = (
            bank["credit_amount"].abs() - amount
        ).abs()

        mask |= (
            (debit_diff <= 5)
            | (credit_diff <= 5)
        )

    matches = bank.loc[
        mask,
        [
            "date",
            "description",
            "reference",
            "customer_reference",
            "transaction_type",
            "debit_amount",
            "credit_amount",
            "bank_name",
            "source_file",
        ],
    ].copy()

    print(
        f"\nBANK ROWS WITH AMOUNT WITHIN +/-5: {len(matches)}"
    )

    if len(matches):
        print(
            matches
            .head(50)
            .to_string(index=False)
        )
    else:
        print("NONE")

    # Also search by reference.
    reference = pop_row.get("reference_number")

    if pd.notna(reference):
        reference = str(reference).strip()

        print(
            f"\nBANK ROWS CONTAINING REFERENCE '{reference}':"
        )

        text = (
            bank[
                [
                    "description",
                    "reference",
                    "customer_reference",
                ]
            ]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
        )

        ref_mask = text.str.contains(
            reference,
            case=False,
            regex=False,
        )

        ref_matches = bank.loc[
            ref_mask,
            [
                "date",
                "description",
                "reference",
                "customer_reference",
                "debit_amount",
                "credit_amount",
                "bank_name",
                "source_file",
            ],
        ]

        if len(ref_matches):
            print(
                ref_matches
                .head(30)
                .to_string(index=False)
            )
        else:
            print("NONE")

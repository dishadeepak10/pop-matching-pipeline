import pandas as pd
import re

BANK = r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
POP = r"D:\Disha_Workarea\pop_process\data\output\POP_email_merged_final.xlsx"

b = pd.read_excel(BANK)
p = pd.read_excel(POP)

b["date"] = pd.to_datetime(b["date"], errors="coerce")

TEXT_COLS = ["description", "reference", "customer_reference"]

for c in TEXT_COLS:
    b[c] = b[c].fillna("").astype(str)

b["search_text"] = (
    b[TEXT_COLS]
    .agg(" | ".join, axis=1)
    .str.upper()
)

cases = [84373, 84696, 84725]

print("=" * 150)
print("ZERO-CASE SENDER / REFERENCE DIAGNOSTIC")
print("=" * 150)

for case_no in cases:

    r = p[p["case_number"] == case_no].iloc[0]

    sender = str(r["sender_name"])
    reference = str(r["reference_number"])

    print("\n")
    print("-" * 150)
    print(f"CASE       : {case_no}")
    print(f"SENDER     : {sender}")
    print(f"POP DATE   : {r['transaction_date']}")
    print(f"EMAIL DATE : {r['email_created_date']}")
    print(f"REFERENCE  : {reference}")
    print("-" * 150)

    # --------------------------------------------------------
    # 1. FULL SENDER NAME SEARCH
    # --------------------------------------------------------

    sender_upper = sender.upper().strip()

    x = b[b["search_text"].str.contains(
        re.escape(sender_upper),
        regex=True,
        na=False
    )].copy()

    print(f"\nFULL SENDER NAME MATCHES: {len(x)}")

    if len(x):
        print(
            x[
                [
                    "date",
                    "description",
                    "reference",
                    "customer_reference",
                    "debit_amount",
                    "credit_amount",
                    "bank_name",
                    "source_file",
                ]
            ].to_string(index=False)
        )

    # --------------------------------------------------------
    # 2. DISTINCTIVE SENDER TOKENS
    # --------------------------------------------------------

    tokens = [
        t for t in re.findall(r"[A-Z0-9]+", sender_upper)
        if len(t) >= 5
    ]

    print("\nSENDER TOKEN SEARCH:")

    for token in tokens:

        x = b[b["search_text"].str.contains(
            re.escape(token),
            regex=True,
            na=False
        )].copy()

        print(f"\nTOKEN [{token}] -> {len(x)} matches")

        if len(x):
            print(
                x[
                    [
                        "date",
                        "description",
                        "reference",
                        "customer_reference",
                        "debit_amount",
                        "credit_amount",
                        "bank_name",
                        "source_file",
                    ]
                ].to_string(index=False)
            )

    # --------------------------------------------------------
    # 3. REFERENCE SEARCH
    # --------------------------------------------------------

    if reference and reference.lower() != "nan":

        ref_upper = reference.upper().strip()

        x = b[b["search_text"].str.contains(
            re.escape(ref_upper),
            regex=True,
            na=False
        )].copy()

        print(f"\nREFERENCE [{reference}] MATCHES: {len(x)}")

        if len(x):
            print(
                x[
                    [
                        "date",
                        "description",
                        "reference",
                        "customer_reference",
                        "debit_amount",
                        "credit_amount",
                        "bank_name",
                        "source_file",
                    ]
                ].to_string(index=False)
            )

    print("\n")

print("=" * 150)
print("END DIAGNOSTIC")
print("=" * 150)

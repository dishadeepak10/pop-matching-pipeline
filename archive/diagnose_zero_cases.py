import pandas as pd

bank_path = r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"

b = pd.read_excel(bank_path)

b["search_text"] = (
    b[["description", "reference", "customer_reference"]]
    .fillna("")
    .astype(str)
    .agg(" | ".join, axis=1)
    .str.upper()
)

queries = [
    (84373, [189000, 50000], "T033", "AYAN BARDAI NURUDDIN BARDAI", "2026-06-13"),
    (84696, [50000], "T033", "AYAN BARDAI NURUDDIN BARDAI", "2026-06-13"),
    (84725, [200000], "R-1645046", "SYED MUHAMMAD MUHAMMAD ASLAM", "2026-02-16"),
]

print("=" * 140)
print("BANK DIAGNOSTIC SEARCH")
print("=" * 140)

for case, amounts, ref, sender, pop_date in queries:

    print()
    print("-" * 140)
    print(f"CASE {case}")
    print(f"Amounts : {amounts}")
    print(f"Reference: {ref}")
    print(f"Sender   : {sender}")
    print(f"POP date : {pop_date}")
    print("-" * 140)

    ref_mask = b["search_text"].str.contains(ref.upper(), regex=False)
    sender_mask = b["search_text"].str.contains(sender.upper(), regex=False)

    amount_mask = pd.Series(False, index=b.index)

    for amount in amounts:
        amount_mask |= (
            b["debit_amount"].sub(amount).abs().le(0.01)
            | b["credit_amount"].sub(amount).abs().le(0.01)
        )

    x = b[ref_mask | sender_mask | amount_mask].copy()

    print("ROWS FOUND:", len(x))

    if len(x):
        cols = [
            "date",
            "value_date",
            "description",
            "reference",
            "customer_reference",
            "debit_amount",
            "credit_amount",
            "bank_name",
            "source_file",
        ]

        print(
            x[cols]
            .sort_values(["date", "bank_name"], na_position="last")
            .to_string(index=False)
        )
    else:
        print("NO ROWS")

print()
print("=" * 140)

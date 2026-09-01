import pandas as pd

BANK = r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
POP = r"D:\Disha_Workarea\pop_process\data\output\POP_email_merged_final.xlsx"

b = pd.read_excel(BANK)
p = pd.read_excel(POP)

b["date"] = pd.to_datetime(b["date"], errors="coerce")

cases = {
    84373: [189000, 50000],
    84696: [50000],
    84725: [200000],
}

print("=" * 150)
print("ZERO-CASE JULY CANDIDATE DIAGNOSTIC")
print("=" * 150)

for case, amounts in cases.items():

    r = p[p["case_number"] == case].iloc[0]

    mask = (
        b["credit_amount"].isin(amounts)
        | b["debit_amount"].isin(amounts)
    )

    x = b[
        mask
        & b["date"].between("2026-07-01", "2026-07-31")
    ].copy()

    print()
    print("-" * 150)
    print(
        f"CASE {case} | "
        f"sender={r['sender_name']} | "
        f"POP_DATE={r['transaction_date']} | "
        f"EMAIL_DATE={r['email_created_date']} | "
        f"REF={r['reference_number']} | "
        f"AMOUNTS={amounts}"
    )
    print("-" * 150)
    print("JULY EXACT-AMOUNT ROWS:", len(x))

    cols = [
        "date",
        "description",
        "reference",
        "customer_reference",
        "debit_amount",
        "credit_amount",
        "bank_name",
        "source_file",
    ]

    print(x[cols].to_string(index=False))

print()
print("=" * 150)

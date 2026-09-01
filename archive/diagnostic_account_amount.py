import match_aug_final_v2 as m
import pandas as pd

pop = m.load_pop()
bank = m.load_bank()

rows = []

for _, p in pop.iterrows():

    x = bank[
        bank["source_account"].astype(str).str.strip().eq(str(p["pop_account"]).strip())
        & bank["bank_amount"].notna()
        & bank["effective_bank"].eq(p["pop_bank"])
    ].copy()

    exact = x[
        (x["bank_amount"] - p["pop_amount"]).abs()
        <= m.AMOUNT_TOLERANCE
    ]

    rows.append({
        "case": p["case_number"],
        "pop_amount": p["pop_amount"],
        "pop_bank": p["pop_bank"],
        "pop_account": p["pop_account"],
        "account_bank_credit_rows": len(x),
        "exact_amount_in_account": len(exact),
        "matching_amounts": sorted(x["bank_amount"].dropna().unique().tolist())[:20]
    })

result = pd.DataFrame(rows)

print("=" * 120)
print("POP ACCOUNT + BANK ACCOUNT + AMOUNT DIAGNOSTIC")
print("=" * 120)

print()
print("CASES WITH EXACT AMOUNT IN CORRECT ACCOUNT:",
      (result["exact_amount_in_account"] > 0).sum())

print("CASES WITHOUT EXACT AMOUNT IN CORRECT ACCOUNT:",
      (result["exact_amount_in_account"] == 0).sum())

print()
print(
    result[
        result["exact_amount_in_account"].eq(0)
    ][
        [
            "case",
            "pop_amount",
            "pop_bank",
            "pop_account",
            "account_bank_credit_rows"
        ]
    ].to_string(index=False)
)

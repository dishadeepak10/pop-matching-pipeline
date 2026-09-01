import match_aug_final_v2 as m
import pandas as pd


pop = m.load_pop()
bank = m.load_bank()

bank_credit = bank[bank["bank_amount"].notna()].copy()

print("=" * 120)
print("26 ACCOUNT-FAIL CASES: AMOUNT SEARCH ACROSS POP BANK")
print("=" * 120)

for _, p in pop.iterrows():

    # Bank-wide amount matches
    bank_matches = bank_credit[
        bank_credit["effective_bank"].eq(p["pop_bank"])
        & (
            (bank_credit["bank_amount"] - p["pop_amount"]).abs()
            <= m.AMOUNT_TOLERANCE
        )
    ]

    # Exact account + bank + amount matches
    account_matches = bank_matches[
        bank_matches["source_account"]
        .astype(str)
        .str.strip()
        .eq(str(p["pop_account"]).strip())
    ]

    # Only investigate cases where the account has no exact amount
    if len(account_matches) > 0:
        continue

    print()
    print(
        f"CASE {p['case_number']} | "
        f"POP BANK={p['pop_bank']} | "
        f"POP ACCOUNT={p['pop_account']} | "
        f"AMOUNT={p['pop_amount']}"
    )

    if len(bank_matches) == 0:
        print("  NO AMOUNT MATCH ANYWHERE IN THIS BANK")
        continue

    grouped = (
        bank_matches
        .groupby(["source_account", "source_file"])
        .size()
        .reset_index(name="rows")
        .sort_values(
            ["rows", "source_account"],
            ascending=[False, True]
        )
    )

    print("  AMOUNT FOUND IN THESE BANK ACCOUNTS/FILES:")
    print(grouped.to_string(index=False))
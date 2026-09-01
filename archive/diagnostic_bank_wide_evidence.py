import match_aug_final_v2 as m
import pandas as pd


pop = m.load_pop()
bank = m.load_bank()

bank_credit = bank[bank["bank_amount"].notna()].copy()

print("=" * 120)
print("ACCOUNT-FAIL CASES — BANK-WIDE AMOUNT + DATE EVIDENCE")
print("=" * 120)

for _, p in pop.iterrows():

    account_matches = bank_credit[
        bank_credit["effective_bank"].eq(p["pop_bank"])
        & bank_credit["source_account"].astype(str).str.strip().eq(
            str(p["pop_account"]).strip()
        )
        & (
            (bank_credit["bank_amount"] - p["pop_amount"]).abs()
            <= m.AMOUNT_TOLERANCE
        )
    ]

    if len(account_matches) > 0:
        continue

    amount_matches = bank_credit[
        bank_credit["effective_bank"].eq(p["pop_bank"])
        & (
            (bank_credit["bank_amount"] - p["pop_amount"]).abs()
            <= m.AMOUNT_TOLERANCE
        )
    ].copy()

    print()
    print(
        f"CASE {p['case_number']} | "
        f"POP DATE={p['pop_date'].date()} | "
        f"BANK={p['pop_bank']} | "
        f"ACCOUNT={p['pop_account']} | "
        f"AMOUNT={p['pop_amount']}"
    )

    if len(amount_matches) == 0:
        print("  NO AMOUNT MATCH ANYWHERE IN EXPECTED BANK")
        continue

    amount_matches["date_diff_days"] = (
        amount_matches["date"] - p["pop_date"]
    ).abs().dt.days

    nearby = amount_matches[
        amount_matches["date_diff_days"] <= m.DATE_WINDOW_DAYS
    ].copy()

    if len(nearby) == 0:
        print(
            f"  AMOUNT EXISTS IN BANK, BUT NO MATCH WITHIN "
            f"{m.DATE_WINDOW_DAYS}-DAY DATE WINDOW"
        )
        continue

    display_cols = [
        "date",
        "date_diff_days",
        "source_account",
        "source_file",
        "bank_amount",
        "reference",
        "customer_reference",
        "description",
    ]

    print(
        nearby[
            [c for c in display_cols if c in nearby.columns]
        ]
        .sort_values(["date_diff_days", "source_account"])
        .head(20)
        .to_string(index=False)
    )
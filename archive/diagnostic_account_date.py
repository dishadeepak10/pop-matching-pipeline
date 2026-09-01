import match_aug_final_v2 as m
import pandas as pd

pop = m.load_pop()
bank = m.load_bank()

DATE_WINDOW_DAYS = 10

print("=" * 110)
print("26 ACCOUNT-FAIL CASES — CORRECT ACCOUNT + DATE EVIDENCE")
print("=" * 110)

for _, p in pop.iterrows():

    account = str(p["pop_account"]).strip()

    x = bank[
        bank["source_account"].astype(str).str.strip().eq(account)
        & bank["effective_bank"].eq(p["pop_bank"])
        & bank["bank_amount"].notna()
    ].copy()

    exact_amount = x[
        (x["bank_amount"] - p["pop_amount"]).abs()
        <= m.AMOUNT_TOLERANCE
    ]

    # Only cases where amount is absent from the correct account
    if len(exact_amount) > 0:
        continue

    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    pop_date = pd.to_datetime(p["pop_date"])

    x["date_diff_days"] = (
        x["date"] - pop_date
    ).abs().dt.days

    nearby = x[
        x["date_diff_days"] <= DATE_WINDOW_DAYS
    ].copy()

    nearby = nearby.sort_values(
        ["date_diff_days", "date"]
    )

    print()
    print(
        f"CASE {p['case_number']} | "
        f"POP DATE={pop_date.date()} | "
        f"BANK={p['pop_bank']} | "
        f"ACCOUNT={account} | "
        f"POP AMOUNT={p['pop_amount']}"
    )

    print(
        f"CORRECT ACCOUNT TRANSACTIONS: {len(x)} | "
        f"WITHIN ±{DATE_WINDOW_DAYS} DAYS: {len(nearby)}"
    )

    if len(nearby) == 0:
        print("NO TRANSACTIONS WITHIN DATE WINDOW")
        continue

    cols = [
        "date",
        "date_diff_days",
        "bank_amount",
        "reference",
        "customer_reference",
        "description",
        "transaction_type",
        "source_file"
    ]

    print(
        nearby[cols].head(30).to_string(index=False)
    )
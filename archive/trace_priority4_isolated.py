import sys
sys.path.insert(0, "src")
import pandas as pd
from email_log_parser import load_email_log_rows
import matching
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)

# Pick a real row, then synthetically clear BOTH its bank name AND its
# account number - this is required to truly isolate Priority 4, since
# Priority 2 (account match) will short-circuit the chain if the real
# account number is left in place (as happened last time: 413 rows
# matched via account before Priority 4 was ever reached).
pop_row = dict(rows[0])
print(f"Testing with case {pop_row['case_number']} (bank name AND account forced empty)")
print(f"  original email_bank_name: {rows[0].get('email_bank_name')!r}")
print(f"  original email_bank_account: {rows[0].get('email_bank_account')!r}")
pop_row["email_bank_name"] = ""
pop_row["email_bank_account"] = ""

print(f"  pop_amount: {pop_row.get('pop_amount')!r}")
print(f"  pop_value_date: {pop_row.get('pop_value_date')!r}")
print()

bank_df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

pop_source_file = str(pop_row.get("bank_source_file") or "").strip().upper()
print(f"Priority 1 (bank_source_file): {'present' if pop_source_file else 'SKIPPED (empty)'}")

mask = bank_df.apply(lambda row: matching.bank_account_matches_pop(pop_row, row), axis=1)
account_rows = bank_df[mask]
print(f"Priority 2 (account match): {len(account_rows)} rows matched -> {'SKIPPED (empty account, as expected)' if account_rows.empty else 'UNEXPECTED: still matched'}")

pop_bank = matching.normalize_alnum(pop_row.get("email_bank_name"))
print(f"Priority 3 (bank name match): normalized={pop_bank!r} -> {'SKIPPED (empty, as expected)' if not pop_bank else 'UNEXPECTED: attempted'}")

pop_has_date = pop_row.get("pop_value_date") not in (None, "", float("nan"))
print(f"Priority 4 (full master) eligible: {pop_has_date}")
print()

candidates = matching.generate_candidates(pop_row, bank_df)
print(f"generate_candidates() returned {len(candidates)} candidates, no crash.")

if candidates:
    top = candidates[0]
    print()
    print("Top candidate (from full-master Priority 4 path):")
    print(f"  bank_row_index: {top['bank_row_index']}")
    print(f"  bank_name: {top['bank_name']!r}")
    print(f"  source_file: {top['source_file']!r}")
    print(f"  amount_difference: {top['amount_difference']}")
    print(f"  date_difference: {top['date_difference']}")
    print(f"  score: {top['score']} (amount={top['amount_score']}, field={top['field_score']}, date={top['date_score']})")

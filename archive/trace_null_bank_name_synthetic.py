import sys
sys.path.insert(0, "src")
import pandas as pd
from email_log_parser import load_email_log_rows
import matching
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)

# Pick a real row, then synthetically clear its bank name to force the
# null-bank-name path - this only exists to test the fallback CHAIN,
# not to produce a real match result.
pop_row = dict(rows[0])
print(f"Testing with case {pop_row['case_number']} (bank name forced empty)")
print(f"  original email_bank_name: {rows[0].get('email_bank_name')!r}")
pop_row["email_bank_name"] = ""

print(f"  pop_amount: {pop_row.get('pop_amount')!r}")
print(f"  pop_value_date: {pop_row.get('pop_value_date')!r}")
print()

bank_df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

pop_source_file = str(pop_row.get("bank_source_file") or "").strip().upper()
print(f"Priority 1 (bank_source_file): {'present' if pop_source_file else 'SKIPPED (empty)'}")

mask = bank_df.apply(lambda row: matching.bank_account_matches_pop(pop_row, row), axis=1)
account_rows = bank_df[mask]
print(f"Priority 2 (account match): {len(account_rows)} rows matched")

pop_bank = matching.normalize_alnum(pop_row.get("email_bank_name"))
print(f"Priority 3 (bank name match): normalized={pop_bank!r} -> {'SKIPPED (empty, as expected)' if not pop_bank else 'UNEXPECTED: attempted'}")

pop_has_date = pop_row.get("pop_value_date") not in (None, "", float("nan"))
print(f"Priority 4 (full master) eligible: {pop_has_date}")
print()

candidates = matching.generate_candidates(pop_row, bank_df)
print(f"generate_candidates() returned {len(candidates)} candidates, no crash.")

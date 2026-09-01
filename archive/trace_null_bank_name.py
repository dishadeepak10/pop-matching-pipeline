import sys, json
sys.path.insert(0, "src")
import pandas as pd
from pop_row_builder import build_pop_row
from matching import bank_account_matches_pop, normalize_alnum, _apply_amount_filter if False else None
import matching

case_number = "00084596"
with open(f"data/output/{case_number}_POP_Document/normalized.json", "r", encoding="utf-8") as f:
    normalized_data = json.load(f)
pop_row = build_pop_row(case_number, normalized_data)

print("pop_row summary:")
print(f"  email_bank_account: {pop_row.get('email_bank_account')!r}")
print(f"  email_bank_name: {pop_row.get('email_bank_name')!r}")
print(f"  pop_amount: {pop_row.get('pop_amount')!r}")
print(f"  pop_value_date: {pop_row.get('pop_value_date')!r}")
print()

bank_df = pd.read_excel(r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx")

# Trace Stage 1 manually, mirroring generate_candidates()
pop_source_file = str(pop_row.get("bank_source_file") or "").strip().upper()
print(f"Priority 1 (bank_source_file): {'present -> ' + pop_source_file if pop_source_file else 'SKIPPED (empty)'}")

mask = bank_df.apply(lambda row: matching.bank_account_matches_pop(pop_row, row), axis=1)
account_rows = bank_df[mask]
print(f"Priority 2 (account match): {len(account_rows)} rows matched")

pop_bank = matching.normalize_alnum(pop_row.get("email_bank_name"))
print(f"Priority 3 (bank name match): pop_bank normalized = {pop_bank!r} -> {'SKIPPED (empty)' if not pop_bank else 'would attempt'}")

pop_has_date = pop_row.get("pop_value_date") not in (None, "", float("nan"))
print(f"Priority 4 (full master) eligible: {pop_has_date}")
print()

candidates = matching.generate_candidates(pop_row, bank_df)
print(f"Final candidate count from generate_candidates(): {len(candidates)}")
if candidates:
    print(f"Top candidate score: {candidates[0][\"score\"]}, evidence: {candidates[0][\"evidence\"]}")

import sys, json
sys.path.insert(0, "src")
import pandas as pd
from pop_row_builder import build_pop_row
from email_log_parser import load_email_log_rows
import matching
from pathlib import Path

# Check 1: currency extraction still correct + defaults working
print("=== Currency extraction check ===")
for case in ["00084501", "00084379"]:
    matches = list(Path("data/output").glob(f"{case}*/normalized.json"))
    if matches:
        with open(matches[0], "r", encoding="utf-8") as f:
            normalized = json.load(f)
        row = build_pop_row(case, normalized)
        print(f"{case}: pop_currency={row['pop_currency']!r}")

email_rows = load_email_log_rows(Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx"))
email_currencies = set(r["pop_currency"] for r in email_rows)
print(f"August email cases: all now = {email_currencies}")

# Check 2: does 00084501 actually get excluded by the gate now?
print()
print("=== Gate check: case 00084501 (GBP) ===")
matches = list(Path("data/output").glob("00084501*/normalized.json"))
with open(matches[0], "r", encoding="utf-8") as f:
    normalized = json.load(f)
pop_row = build_pop_row("00084501", normalized)
bank_df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")
result, candidates, error = matching.match_one_pop(pop_row, bank_df, set())
print(f"status={result['status']}, match_reason={result['match_reason']}, candidate_count={result['candidate_count']}")

# Check 3: spot-check a normal AED case still matches fine (no regression)
print()
print("=== Regression check: case 85663 (AED, real data) ===")
real_row = dict(email_rows[0])
result2, candidates2, error2 = matching.match_one_pop(real_row, bank_df, set())
print(f"case={result2['case_number']}, status={result2['status']}, match_reason={result2['match_reason']}, candidate_count={result2['candidate_count']}")

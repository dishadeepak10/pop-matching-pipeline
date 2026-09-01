import sys
sys.path.insert(0, "src")
import pandas as pd
from email_log_parser import load_email_log_rows
import matching
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)
bank_df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

risky_cases = []

for r in rows:
    pop_row = dict(r)
    pop_row["email_bank_name"] = ""
    pop_row["email_bank_account"] = ""

    candidates = matching.generate_candidates(pop_row, bank_df)
    decision = matching.decide(candidates)

    if decision["status"] == "MATCHED":
        selected = decision["selected"]
        if selected["field_score"] == 0:
            risky_cases.append({
                "case_number": pop_row.get("case_number"),
                "pop_amount": pop_row.get("pop_amount"),
                "match_reason": decision["match_reason"],
                "bank_name": selected["bank_name"],
                "date_diff": selected["date_difference"],
            })

print(f"Total cases tested: {len(rows)}")
print(f"Cases where Priority-4-only + zero field evidence still produced MATCHED: {len(risky_cases)}")
print()
for c in risky_cases:
    print(c)

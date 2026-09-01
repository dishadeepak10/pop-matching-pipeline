import sys
sys.path.insert(0, "src")
import pandas as pd
from email_log_parser import load_email_log_rows
import matching
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)

pop_row = dict(rows[0])
pop_row["email_bank_name"] = ""
pop_row["email_bank_account"] = ""

bank_df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

candidates = matching.generate_candidates(pop_row, bank_df)
print(f"Total candidates: {len(candidates)}")
print()
for i, c in enumerate(candidates[:5]):
    print(f"#{i+1}: score={c['score']} (amount={c['amount_score']}, field={c['field_score']}, date={c['date_score']}) "
          f"bank={c['bank_name']!r} amount_diff={c['amount_difference']} date_diff={c['date_difference']} "
          f"evidence={c['evidence']!r}")

print()
decision = matching.decide(candidates)
print(f"FINAL DECISION: status={decision['status']}, reason={decision['match_reason']}, "
      f"score={decision['score']}, score_gap={decision['score_gap']}")

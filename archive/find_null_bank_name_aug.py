import sys
sys.path.insert(0, "src")
from email_log_parser import load_email_log_rows
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)

for r in rows:
    if not r.get("email_bank_name"):
        has_date = bool(r.get("pop_value_date"))
        print(f"{r['case_number']}: bank_name empty, has_date={has_date}")

import sys
sys.path.insert(0, "src")
from email_log_parser import load_email_log_rows
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)
print(f"Total rows: {len(rows)}")
print("First 5 case numbers:")
for r in rows[:5]:
    print(f"  {r['case_number']}")

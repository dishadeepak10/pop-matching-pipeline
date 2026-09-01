import sys
sys.path.insert(0, "src")
from email_log_parser import load_email_log_rows
from pathlib import Path
from collections import Counter

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
rows = load_email_log_rows(path)

counts = Counter(r.get("pop_currency") or "(blank)" for r in rows)
print(f"Total cases: {len(rows)}")
for currency, count in counts.most_common():
    print(f"  {currency}: {count}")

print()
blanks = [r["case_number"] for r in rows if not r.get("pop_currency")]
print(f"Blank cases ({len(blanks)}): {blanks}")

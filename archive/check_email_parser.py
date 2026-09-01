import sys
sys.path.insert(0, "src")
from email_log_parser import load_email_log_rows

rows = load_email_log_rows(
    r"D:\Disha_Workarea\pop_process\data\input\AUG_2026\EMAIL_LOG\_POP_EmailsLog_2.xlsx"
)

print(f"Total rows parsed: {len(rows)}")
usable = sum(1 for r in rows if r["pop_amount"] is not None)
has_account = sum(1 for r in rows if r["email_bank_account"])
print(f"Rows with amount: {usable}")
print(f"Rows with account: {has_account}")

for r in rows[:5]:
    print(r)

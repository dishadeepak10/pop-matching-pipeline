import sys
sys.path.insert(0, "src")
import pandas as pd
from pathlib import Path

path = Path("data/input/AUG_2026/EMAIL_LOG/_POP_EmailsLog_2.xlsx")
df = pd.read_excel(path, sheet_name="POP_attachments")

# Grab the first 3 real email bodies, full raw text
count = 0
for _, r in df.iterrows():
    if pd.isna(r.get("Case Number")):
        continue
    print(f"=== Case {r.get('Case Number')} ===")
    print(r.get("EmailBody"))
    print()
    print("-" * 80)
    print()
    count += 1
    if count >= 3:
        break

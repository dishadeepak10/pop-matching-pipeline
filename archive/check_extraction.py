import json
from pathlib import Path
import sys

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row

usable = 0
total = 0

for folder in sorted(Path("data/output").glob("*_POP_Document")):
    f = folder / "normalized.json"
    if not f.exists():
        continue
    total += 1
    data = json.load(open(f, encoding="utf-8"))
    case = folder.name.split("_")[0]
    row = build_pop_row(case, data)
    ok = row["pop_amount"] is not None and row["email_bank_account"]
    if ok:
        usable += 1
    status = "OK" if ok else "MISSING"
    print(f"{case}: amount={row['pop_amount']} date={row['pop_value_date']} account={row['email_bank_account']!r} {status}")

print(f"\n{usable}/{total} usable rows")

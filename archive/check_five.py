import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row

check_cases = ["00084285", "00084741", "00084742", "00084360", "00084362"]

for case in check_cases:
    f = Path(f"data/output/{case}_POP_Document/normalized.json")
    data = json.load(open(f, encoding="utf-8"))
    row = build_pop_row(case, data)
    print(f"{case}: amount={row[chr(39)+'pop_amount'+chr(39)] if False else row['pop_amount']} "
          f"date={row['pop_value_date']} account={row['email_bank_account']!r}")

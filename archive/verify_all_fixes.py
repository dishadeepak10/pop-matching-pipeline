import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row

# 84379 = new fix; 84501/84572 = previously verified, must still work
cases = ["00084379", "00084501", "00084572", "00084772", "00084851"]

for case in cases:
    path = Path(f"data/output/{case}_POP_Document/normalized.json")
    with open(path, "r", encoding="utf-8") as f:
        normalized_data = json.load(f)
    row = build_pop_row(case, normalized_data)
    print(f"{case}: pop_amount={row['pop_amount']}  pop_value_date={row['pop_value_date']}")

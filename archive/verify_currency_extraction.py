import sys, json
sys.path.insert(0, "src")
from pop_row_builder import build_pop_row
from pathlib import Path

test_cases = ["00084501", "00084379"]

for case in test_cases:
    matches = list(Path("data/output").glob(f"{case}*/normalized.json"))
    if not matches:
        print(f"{case}: no cached normalized.json found, skipping")
        continue
    with open(matches[0], "r", encoding="utf-8") as f:
        normalized = json.load(f)
    row = build_pop_row(case, normalized)
    print(f"{case}: pop_currency={row['pop_currency']!r}  pop_amount={row['pop_amount']!r}")

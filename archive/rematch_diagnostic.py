import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row
from matching import match_one_pop
import storage

BANK_MASTER_FILE = Path(
    r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
)

print("Loading bank master...")
bank_df = pd.read_excel(BANK_MASTER_FILE)
print(f"Bank rows: {len(bank_df)}")

locked_bank_rows = set()  # fresh lock state for this diagnostic re-run

results_summary = []

for folder in sorted(Path("data/output").glob("*_POP_Document")):
    f = folder / "normalized.json"
    if not f.exists():
        continue

    case = folder.name.split("_")[0]
    data = json.load(open(f, encoding="utf-8"))
    row = build_pop_row(case, data)

    result, candidates, error = match_one_pop(row, bank_df, locked_bank_rows)

    if error:
        print(f"{case}: INVALID - {error}")
        continue

    storage.append_candidate_audit(case, candidates, row.get("pop_value_date"))

    print(f"{case}: {result['status']:<12} {result['match_reason']:<35} candidates={result['candidate_count']}")
    results_summary.append(result["status"])

print()
print("Summary:")
from collections import Counter
for status, count in Counter(results_summary).items():
    print(f"  {status}: {count}")

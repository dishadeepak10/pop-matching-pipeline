import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row

cases = ["00084375", "00084379", "00084501", "00084572", "00084879", "00084922"]
output_dir = Path("data/output")

for case in cases:
    matches = list(output_dir.glob(f"{case}*"))
    if not matches:
        print(f"{case}: no output folder found")
        continue
    norm_file = matches[0] / "normalized.json"
    if not norm_file.exists():
        print(f"{case}: no normalized.json found")
        continue
    normalized_data = json.loads(norm_file.read_text(encoding="utf-8"))
    row = build_pop_row(case, normalized_data)
    print(f"{case}: pop_value_date = {row['pop_value_date']}")

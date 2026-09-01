import sys, json
sys.path.insert(0, "src")
from pop_row_builder import build_pop_row
from pathlib import Path

output_dir = Path("data/output")
for case_dir in sorted(output_dir.iterdir()):
    if not case_dir.name.endswith("_POP_Document"):
        continue
    normalized_path = case_dir / "normalized.json"
    if not normalized_path.exists():
        continue
    case_number = case_dir.name.split("_")[0]
    with open(normalized_path, "r", encoding="utf-8") as f:
        normalized_data = json.load(f)
    row = build_pop_row(case_number, normalized_data)
    if not row.get("email_bank_name"):
        print(f"{case_number}: bank_name is empty/null, has date={bool(row.get('pop_value_date'))}")

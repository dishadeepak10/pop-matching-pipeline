import json
from pathlib import Path
import sys

sys.path.insert(0, "src")
from pop_row_builder import _find_field, ACCOUNT_GROUPS, ACCOUNT_EXCLUDE

bad_cases = ["00084283", "00084285", "00084362", "00084373", "00084384",
             "00084401", "00084501", "00084572", "00084596", "00084670",
             "00084696", "00084725", "00084741", "00084742", "00084822",
             "00084360", "00084879", "00084826", "00084851"]

for folder in sorted(Path("data/output").glob("*_POP_Document")):
    case = folder.name.split("_")[0]
    if case not in bad_cases:
        continue
    f = folder / "normalized.json"
    if not f.exists():
        continue
    data = json.load(open(f, encoding="utf-8"))
    fields = data.get("fields", {})
    key, value = _find_field(fields, ACCOUNT_GROUPS, ACCOUNT_EXCLUDE)
    print(f"{case}: matched_field={key!r} raw_value={value!r}")

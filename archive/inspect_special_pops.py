import json
from pathlib import Path

base = Path("data/output")

cases = [
    "00084596_POP_Document",
    "00084826_POP_Document",
    "00084922_POP_Document",
]

for case in cases:
    file = base / case / "normalized.json"

    print()
    print("=" * 100)
    print(case)
    print("=" * 100)

    data = json.load(open(file, encoding="utf-8"))

    print()
    print("OVERALL CONFIDENCE:", data.get("overall_confidence"))
    print()

    for field_name, field_data in data.get("fields", {}).items():
        print(f"{field_name} = {field_data.get('value')}")

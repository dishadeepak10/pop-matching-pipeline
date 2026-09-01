import json
from pathlib import Path

output_dir = Path("data/output")

for json_file in sorted(output_dir.glob("*/extracted.json")):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    fields = data.get("fields", {})

    confidences = [
        field.get("confidence")
        for field in fields.values()
        if isinstance(field, dict)
        and isinstance(field.get("confidence"), (int, float))
    ]

    calculated = (
        sum(confidences) / len(confidences)
        if confidences
        else None
    )

    existing = data.get("overall_confidence")

    print(
        f"{json_file.parent.name:<35} "
        f"Fields={len(confidences):<3} "
        f"Calculated={calculated:.2f} "
        f"Existing={existing} "
        f"Difference={(existing - calculated):.2f}"
        if calculated is not None and isinstance(existing, (int, float))
        else f"{json_file.parent.name:<35} No confidence data"
    )

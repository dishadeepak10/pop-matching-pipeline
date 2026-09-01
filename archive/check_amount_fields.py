import json
from pathlib import Path

cases = ["00084772", "00084851"]
output_dir = Path("data/output")
for case in cases:
    matches = list(output_dir.glob(f"{case}*"))
    for m in matches:
        f = m / "normalized.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            fields = data.get("fields", {})
            print("=" * 60)
            print("CASE", case, "- all field names:")
            for k, v in fields.items():
                val = v.get("value")
                print("  ", k, ":", val)

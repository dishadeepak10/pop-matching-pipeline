import sys, json
sys.path.insert(0, "src")
from pathlib import Path

case = "00084501"
matches = list(Path("data/output").glob(f"{case}*/normalized.json"))
if not matches:
    print(f"{case}: no cached normalized.json found")
else:
    with open(matches[0], "r", encoding="utf-8") as f:
        normalized = json.load(f)
    fields = normalized.get("fields", {}) or {}
    print(f"{case}: {len(fields)} fields total")
    print()
    for key, entry in sorted(fields.items()):
        if not entry:
            continue
        value = entry.get("value")
        original = entry.get("original_value")
        # Only show fields that might plausibly relate to currency/amount
        if any(x in key.lower() for x in ["currency", "amount", "gbp", "aed", "usd", "wire", "total"]):
            print(f"  {key!r}: value={value!r}, original_value={original!r}")

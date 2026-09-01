import json
from pathlib import Path

base = Path("data/output")
files = sorted(base.rglob("normalized.json"))

keywords = [
    "amount", "betrag", "currency", "valuta",
    "date", "datum", "time",
    "reference", "receipt", "transaction", "payment",
    "customer", "beneficiary", "recipient", "sender",
    "bank", "status"
]

print("=" * 100)
print("POP FIELD VALUES FOR RECONCILIATION")
print("=" * 100)

for file in files:
    data = json.load(open(file, encoding="utf-8"))

    print()
    print("-" * 100)
    print(file.parent.name)
    print("-" * 100)

    for field_name, field_data in data.get("fields", {}).items():
        if any(keyword in field_name.lower() for keyword in keywords):
            print(f"{field_name} = {field_data.get('value')}")

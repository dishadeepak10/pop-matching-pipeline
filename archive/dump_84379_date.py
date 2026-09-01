import json

path = r"data\output\00084379_POP_Document\normalized.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

fields = data.get("fields", {})
print(f"Total fields: {len(fields)}")
print()
print("--- Fields with 'date' in the name ---")
for key, value in fields.items():
    if "date" in key.lower():
        print(f"  KEY: {key!r}")
        print(f"    VALUE: {value!r}")
print()
print("--- ALL field names ---")
for key in fields.keys():
    print(f"  {key}")

import json

cases = ["00084772", "00084851"]

for case in cases:
    path = rf"D:\Disha_Workarea\pop_process\data\output\{case}_POP_Document\normalized.json"
    print("=" * 60)
    print(f"CASE: {case}")
    print("=" * 60)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fields = data.get("fields", {})
    print(f"Total field count: {len(fields)}")
    print()

    print("--- Fields with 'amount' OR 'figure' OR 'word' in the name ---")
    for key, value in fields.items():
        key_lower = key.lower()
        if "amount" in key_lower or "figure" in key_lower or "word" in key_lower:
            print(f"  KEY: {key!r}")
            print(f"    VALUE: {value!r}")
    print()

    print("--- ALL field names (just keys, for full context) ---")
    for key in fields.keys():
        print(f"  {key}")
    print()

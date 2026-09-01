import json

cases = ["00084772", "00084851"]

for case in cases:
    path = rf"D:\Disha_Workarea\pop_process\data\output\{case}_POP_Document\normalized.json"
    print("=" * 60)
    print(f"CASE: {case}")
    print("=" * 60)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Top-level type:", type(data))
    if isinstance(data, dict):
        print("Top-level keys:", list(data.keys()))
    elif isinstance(data, list):
        print("List length:", len(data))
        if data:
            print("First item type:", type(data[0]))
            if isinstance(data[0], dict):
                print("First item keys:", list(data[0].keys()))
    print()

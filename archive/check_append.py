import re
with open("src/storage.py", encoding="utf-8") as f:
    c = f.read()
m = re.search(r"def _append_row_to_csv\(.*?\n(?:    .*\n)*", c)
print(m.group(0) if m else "not found")

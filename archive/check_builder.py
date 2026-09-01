import re
with open("src/pop_row_builder.py", encoding="utf-8") as f:
    c = f.read()
m = re.search(r"def build_pop_row\(.*?\n(?:    .*\n)*", c)
print(m.group(0) if m else "not found")

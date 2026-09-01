import re
with open("src/storage.py", encoding="utf-8") as f:
    lines = f.readlines()
start = None
for i, line in enumerate(lines):
    if line.startswith("def _append_row_to_csv"):
        start = i
        break
end = start + 1
for i in range(start + 1, len(lines)):
    if lines[i].startswith("def ") or (lines[i].strip() == "" and i + 1 < len(lines) and lines[i+1].startswith("def ")):
        end = i
        break
    end = i + 1
print("".join(lines[start:end]))

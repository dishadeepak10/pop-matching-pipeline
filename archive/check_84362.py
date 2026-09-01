import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from pop_row_builder import build_pop_row

data = json.load(open("data/output/00084362_POP_Document/normalized.json", encoding="utf-8"))
row = build_pop_row("00084362", data)
print("email_bank_name:", repr(row["email_bank_name"]))
print("pop_amount:", row["pop_amount"])
print("pop_value_date:", row["pop_value_date"])

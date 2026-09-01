import pandas as pd
from pathlib import Path

df = pd.read_csv(r"data\pop_master\pop_master_input.csv", dtype=str)
missing_date = df["pop_value_date"].isna() | (df["pop_value_date"].astype(str).str.strip() == "")
missing_cases = df[missing_date]["case_number"].tolist()

output_dir = Path(r"data\output")
for case in missing_cases:
    matches = list(output_dir.glob(f"{case}*"))
    for m in matches:
        ocr_file = m / "ocr.txt"
        if ocr_file.exists():
            print(f"\n{'='*70}\nCASE {case} — {ocr_file}\n{'='*70}")
            text = ocr_file.read_text(encoding="utf-8", errors="ignore")
            print(text[:1500])
        else:
            print(f"\nCASE {case}: no ocr.txt found at {m}")

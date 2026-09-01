from pathlib import Path
import pandas as pd
from normalize_bank_statements import process_file

BASE = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

normalized = pd.read_excel(BASE / "normalized_bank_statements.xlsx")
processed = set(normalized["source_file"].dropna().unique())

files = [
    p for p in BASE.iterdir()
    if p.is_file()
    and p.name != "normalized_bank_statements.xlsx"
    and p.name not in processed
]

print("=" * 100)
print("ZERO-ROW FILE DIAGNOSIS")
print("=" * 100)
print(f"FILES TO DIAGNOSE: {len(files)}")

results = []

for i, path in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {path.name}")

    try:
        df = process_file(path)

        rows = 0 if df is None else len(df)

        results.append({
            "source_file": path.name,
            "status": "ZERO_ROWS" if rows == 0 else "HAS_ROWS",
            "rows": rows,
            "error": ""
        })

        print(f"RESULT: {rows} rows")

    except Exception as e:
        results.append({
            "source_file": path.name,
            "status": "ERROR",
            "rows": 0,
            "error": repr(e)
        })

        print(f"ERROR: {repr(e)}")

result_df = pd.DataFrame(results)

result_df.to_excel(BASE / "zero_file_diagnosis.xlsx", index=False)

print("\n" + "=" * 100)
print("DIAGNOSIS COMPLETE")
print("=" * 100)
print(result_df.to_string(index=False))
print(f"\nOUTPUT: {BASE / 'zero_file_diagnosis.xlsx'}")
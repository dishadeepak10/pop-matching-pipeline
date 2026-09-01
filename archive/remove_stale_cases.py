import pandas as pd
from pathlib import Path
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
cases_to_remove = ["00084772", "00084851"]

files = [
    Path("data/pop_master/pop_master_input.csv"),
    Path("data/output/failed_pops.csv"),
]

for file_path in files:
    if not file_path.exists():
        print(f"SKIP (not found): {file_path}")
        continue

    df = pd.read_csv(file_path, dtype=str)
    case_col = "case_number" if "case_number" in df.columns else df.columns[0]

    mask = df[case_col].isin(cases_to_remove)
    affected = df[mask]

    print(f"--- {file_path} ---")
    print(f"Rows to remove: {len(affected)}")
    if len(affected) > 0:
        print(affected.to_string())
    print()

    if len(affected) > 0:
        backup_path = file_path.with_name(f"{file_path.stem}_BACKUP_{timestamp}{file_path.suffix}")
        df.to_csv(backup_path, index=False)
        print(f"Backed up to: {backup_path}")

        cleaned = df[~mask]
        cleaned.to_csv(file_path, index=False)
        print(f"Removed. New row count: {len(cleaned)} (was {len(df)})")
    print()

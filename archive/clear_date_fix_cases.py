import pandas as pd
import shutil
from datetime import datetime

path = r"data\pop_master\pop_master_input.csv"
backup_path = path.replace(".csv", f"_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
shutil.copy2(path, backup_path)
print(f"Backup saved: {backup_path}")

fix_cases = ["00084501", "00084572"]

df = pd.read_csv(path, dtype=str)
print(f"Rows before: {len(df)}")
mask = df["case_number"].astype(str).isin(fix_cases)
print(f"Rows to remove (will be re-extracted with the fix): {mask.sum()}")

df_cleaned = df[~mask]
df_cleaned.to_csv(path, index=False)

check = pd.read_csv(path, dtype=str)
print(f"Rows after: {len(check)}")

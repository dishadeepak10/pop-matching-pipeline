import pandas as pd
import shutil
from datetime import datetime

path = r"data\pop_master\pop_master_input.csv"
backup_path = path.replace(".csv", f"_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
shutil.copy2(path, backup_path)
print(f"Backup saved: {backup_path}")

july_cases = ["00084283","00084285","00084308","00084323","00084360","00084362",
"00084373","00084375","00084379","00084384","00084401","00084501","00084572",
"00084596","00084670","00084696","00084725","00084741","00084742","00084772",
"00084822","00084826","00084851","00084879","00084922"]

df = pd.read_csv(path, dtype=str)
print(f"Rows before: {len(df)}")

mask = df["case_number"].astype(str).isin(july_cases)
print(f"Rows to remove: {mask.sum()}")

df_cleaned = df[~mask]
df_cleaned.to_csv(path, index=False)

check = pd.read_csv(path, dtype=str)
print(f"Rows after: {len(check)}")
print(f"Remaining July rows (should be 0): {check['case_number'].astype(str).isin(july_cases).sum()}")

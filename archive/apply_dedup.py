import pandas as pd
import re
import shutil
from datetime import datetime

path = r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
backup_path = path.replace(".xlsx", f"_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
shutil.copy2(path, backup_path)
print(f"Backup saved: {backup_path}")

df = pd.read_excel(path)
print(f"Rows before: {len(df)}")

df["base_file"] = df["source_file"].apply(lambda x: re.sub(r"_(11AUG|19AUG)(?=\.\w+$)", "", str(x)))
print(f"Unique base_file values: {df['base_file'].nunique()} (expect ~87, half of 174)")

key_cols = ["base_file", "date", "reference", "customer_reference", "debit_amount", "credit_amount", "balance"]
dupe_count = df.duplicated(subset=key_cols, keep=False).sum()
drop_count = df.duplicated(subset=key_cols, keep="first").sum()
print(f"Rows in duplicate groups: {dupe_count}")
print(f"Rows to be dropped: {drop_count}")
print(f"Rows remaining after dedup: {len(df) - drop_count}")

deduped = df.drop_duplicates(subset=key_cols, keep="first").drop(columns=["base_file"])
deduped.to_excel(path, index=False)

check = pd.read_excel(path)
print(f"\nVerified rows after save: {len(check)}")
print("\nbank_name distribution after dedup:")
print(check["bank_name"].value_counts(dropna=False).to_string())

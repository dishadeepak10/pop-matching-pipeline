import pandas as pd
import os

path = r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"

print(f"Reading: {path}")
print(f"File exists: {os.path.exists(path)}")
print(f"Last modified: {pd.Timestamp(os.path.getmtime(path), unit='s')}")

df = pd.read_excel(path)
print(f"\nTotal rows loaded: {len(df)}")
print(f"Columns: {list(df.columns)}")

key_cols = ["base_file", "date", "reference", "customer_reference", "debit_amount", "credit_amount", "balance"]
missing = [c for c in key_cols if c not in df.columns]
if missing:
    print(f"\nWARNING - these key columns are missing from the file: {missing}")
    print("Cannot compute duplicate stats until column names are confirmed.")
else:
    dupe_mask_all = df.duplicated(subset=key_cols, keep=False)
    dupe_mask_drop = df.duplicated(subset=key_cols, keep="first")

    print(f"\nRows involved in some duplicate group: {dupe_mask_all.sum()}")
    print(f"Rows that WOULD BE DROPPED (keep='first'): {dupe_mask_drop.sum()}")
    print(f"Rows that WOULD REMAIN after dedup: {len(df) - dupe_mask_drop.sum()}")

    if "bank_name" in df.columns:
        print("\nBank name distribution BEFORE dedup:")
        print(df["bank_name"].value_counts(dropna=False).to_string())
    else:
        print("\nWARNING - no 'bank_name' column found; check actual column name.")

    print("\n--- Sample duplicate group (first one found) ---")
    dupes = df[dupe_mask_all].sort_values(key_cols)
    if len(dupes) > 0:
        first_key = dupes.iloc[0][key_cols]
        sample = df[(df[key_cols] == first_key).all(axis=1)]
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        print(sample.to_string())
    else:
        print("No duplicate groups found with this key.")

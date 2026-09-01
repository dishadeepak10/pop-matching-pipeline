import pandas as pd
df = pd.read_excel(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")
print("Row count:", len(df))
print(df["bank_name"].value_counts())

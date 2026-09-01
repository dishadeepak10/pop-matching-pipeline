import pandas as pd
path = r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
df = pd.read_excel(path)
samples = df["source_file"].drop_duplicates().tolist()
print(f"Total unique source_file values: {len(samples)}")
for s in samples[:20]:
    print(s)

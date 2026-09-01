import pandas as pd

path = r"D:\bank_files\07-JUL-2026\31-07-2026\matching_diagnostic_top_candidates.xlsx"

df = pd.read_excel(path)

print("=" * 120)
print("TOP 50 MATCHING CANDIDATES")
print("=" * 120)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 300)
pd.set_option("display.max_colwidth", 40)

print(df.to_string(index=False))

print()
print("=" * 120)
print("SUMMARY")
print("=" * 120)

print("Total candidate rows:", len(df))
print("Unique cases:", df["case_number"].nunique())

print()
print("Cases:")
print(df["case_number"].unique().tolist())

print()
print("Score statistics:")
print(df["score"].describe())

print()
print("Date score distribution:")
print(df["date_score"].value_counts(dropna=False).sort_index())

print()
print("Reference score statistics:")
print(df["reference_score"].describe())

print()
print("Sender score statistics:")
print(df["sender_score"].describe())

print()
print("Amount score statistics:")
print(df["amount_score"].describe())


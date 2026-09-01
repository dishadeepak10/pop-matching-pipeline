import pandas as pd

df = pd.read_csv(r"data\pop_master\pop_master_input.csv", dtype=str)
missing_date = df["pop_value_date"].isna() | (df["pop_value_date"].astype(str).str.strip() == "")
print(f"Total cases: {len(df)}")
print(f"Missing pop_value_date: {missing_date.sum()}")
print()
print(df[missing_date][["case_number", "pop_value_date", "email_bank_name", "pop_amount"]].to_string())

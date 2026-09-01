import pandas as pd
july_cases = ["00084283","00084285","00084308","00084323","00084360","00084362",
"00084373","00084375","00084379","00084384","00084401","00084501","00084572",
"00084596","00084670","00084696","00084725","00084741","00084742","00084772",
"00084822","00084826","00084851","00084879","00084922"]

df = pd.read_csv(r"data\pop_master\pop_master_input.csv", dtype=str)
print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
mask = df["case_number"].astype(str).isin(july_cases)
print(f"Matching July rows: {mask.sum()}")
print(df[mask][["case_number"]].to_string())

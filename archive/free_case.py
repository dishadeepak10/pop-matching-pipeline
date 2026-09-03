import pandas as pd
case = "86672"
f = r"C:\Users\dvaranashi\OneDrive - Opteamix LLC\PopPipelineData\data\pop_master\pop_master_input.csv"
df = pd.read_csv(f, dtype=str)
print("Found before removal:", df[df["case_number"] == case]["case_number"].tolist())
before = len(df)
df = df[df["case_number"] != case]
df.to_csv(f, index=False)
print("REMOVED:", before - len(df), "rows")

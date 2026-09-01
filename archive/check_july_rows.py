import pandas as pd

july_cases = ["00084283","00084285","00084308","00084323","00084360","00084362",
"00084373","00084375","00084379","00084384","00084401","00084501","00084572",
"00084596","00084670","00084696","00084725","00084741","00084742","00084772",
"00084822","00084826","00084851","00084879","00084922"]
july_normalized = set(str(int(c)) for c in july_cases)  # strip leading zeros for safe comparison

for fname in ["data/output/pop_matched_results.csv", "data/output/pop_review_queue.csv"]:
    df = pd.read_csv(fname, dtype={"case_number": str})
    df["case_number"] = df["case_number"].astype(str)
    match_mask = df["case_number"].apply(lambda x: str(int(x)) in july_normalized if x.strip().lstrip("0").isdigit() or x.strip().isdigit() else False)
    print(f"\n{fname}: {len(df)} total rows, {match_mask.sum()} rows match July case list")
    if match_mask.sum() > 0:
        print(df[match_mask][["case_number"]].to_string())

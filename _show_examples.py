import pandas as pd

matched = pd.read_csv(r"data\output\pop_matched_results.csv", dtype=str)
review = pd.read_csv(r"data\output\pop_review_queue.csv", dtype=str)
failed = pd.read_csv(r"data\output\failed_pops.csv", dtype=str)

print("=== MATCHED ===")
print(matched.iloc[0]["case_number"])

for status in ["AMBIGUOUS", "NO_MATCH", "NEAR_AMOUNT"]:
    subset = review[review["status"] == status]
    print(f"=== {status} ===")
    print(subset.iloc[0]["case_number"] if not subset.empty else "(none found)")

print("=== FAILED ===")
print(failed.iloc[0]["case_number"] if not failed.empty else "(none found)")

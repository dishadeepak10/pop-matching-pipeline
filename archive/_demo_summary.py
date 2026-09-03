import pandas as pd

def safe_read(path):
    try:
        return pd.read_csv(path, dtype=str)
    except FileNotFoundError:
        return pd.DataFrame()

matched = safe_read(r"data\output\pop_matched_results.csv")
review = safe_read(r"data\output\pop_review_queue.csv")
failed = safe_read(r"data\output\failed_pops.csv")

print("=" * 70)
print("COMBINED PIPELINE RESULTS")
print("=" * 70)

print(f"\nTotal MATCHED:      {len(matched)}")
print(f"Total NEEDS REVIEW: {len(review)}")
print(f"Total FAILED:       {len(failed)}")

def show(df, case_number, label):
    row = df[df["case_number"].astype(str) == str(case_number)]
    print(f"\n--- {label}: case {case_number} ---")
    if row.empty:
        print("  (not found)")
        return
    cols = [c for c in ["case_number", "status", "match_reason", "score", "score_gap", "reason"] if c in row.columns]
    print(row.iloc[0][cols].to_string())

show(matched, "85695", "MATCHED example")
show(review, "85663", "AMBIGUOUS example")
show(review, "86229", "NO_MATCH example")
show(review, "86286", "NEAR_AMOUNT example")
show(failed, "00084772", "FAILED example")

print("\n" + "=" * 70)
print("Most recently added rows (from today's live run):")
print("=" * 70)
if not matched.empty:
    print("\nLatest MATCHED:")
    print(matched.tail(2).to_string(index=False))
if not review.empty:
    print("\nLatest REVIEW:")
    print(review.tail(2).to_string(index=False))
if not failed.empty:
    print("\nLatest FAILED:")
    print(failed.tail(2).to_string(index=False))

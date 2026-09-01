import sys
sys.path.insert(0, "src")
from email_log_parser import load_email_log_rows
from pathlib import Path
import pandas as pd
import glob, os

email_case_numbers = set(str(r["case_number"]) for r in load_email_log_rows(Path(r"data\input\AUG_2026\EMAIL_LOG\_POP_EmailsLog_2.xlsx")))
print(f"Clearing prior results for {len(email_case_numbers)} email-sourced cases...")

pm_path = r"data\pop_master\pop_master_input.csv"
if os.path.exists(pm_path):
    pm = pd.read_csv(pm_path, dtype=str)
    before = len(pm)
    pm = pm[~pm["case_number"].astype(str).isin(email_case_numbers)]
    pm.to_csv(pm_path, index=False)
    print(f"pop_master_input.csv: {before} -> {len(pm)} rows")

for fname in ["pop_matched_results.csv", "pop_review_queue.csv", "failed_pops.csv"]:
    fpath = os.path.join("data", "output", fname)
    if os.path.exists(fpath):
        d = pd.read_csv(fpath, dtype=str)
        if "case_number" in d.columns:
            before = len(d)
            d = d[~d["case_number"].astype(str).isin(email_case_numbers)]
            d.to_csv(fpath, index=False)
            print(f"{fname}: {before} -> {len(d)} rows")

for f in glob.glob(r"data\output\*\candidate_audit.csv"):
    d = pd.read_csv(f, dtype=str)
    if "case_number" in d.columns:
        before = len(d)
        d = d[~d["case_number"].astype(str).isin(email_case_numbers)]
        if len(d) != before:
            d.to_csv(f, index=False)
            print(f"{f}: {before} -> {len(d)} rows")

print("Cleared.")

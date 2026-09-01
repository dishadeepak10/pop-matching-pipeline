"""
run_pipeline_email_source.py — same per-POP pipeline as run_pipeline.py,
but sourcing rows from the Salesforce email log instead of raw documents.

For the 90 August cases where no raw POP document/image exists —
only a case-notification email with receipt info embedded in the body.

Reuses matching.py / storage.py completely unchanged. The only
difference from run_pipeline.py is the row source: email_log_parser
instead of Document Intelligence + GPT extraction.
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from email_log_parser import load_email_log_rows
from matching import match_one_pop
import storage

BANK_MASTER_FILE = Path(
    r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
)
EMAIL_LOG_FILE = (
    PROJECT_ROOT / "data" / "input" / "AUG_2026" / "EMAIL_LOG" / "_POP_EmailsLog_2.xlsx"
)


def ensure_bank_master():
    if not BANK_MASTER_FILE.exists():
        raise FileNotFoundError(
            "Bank master not found:\n"
            f"{BANK_MASTER_FILE}\n"
            "Run normalize_bank_statements.py first."
        )
    print(f"Bank master found: {BANK_MASTER_FILE}")


def process_one_row(pop_row, bank_df, locked_bank_rows):
    """
    Runs matching + storage for exactly one email-sourced POP row.
    Never raises - every failure is caught and recorded so the
    next row is never blocked.
    """
    case_number = pop_row["case_number"]

    print()
    print("=" * 70)
    print(f"CASE: {case_number} (email source)")
    print("=" * 70)

    if storage.is_case_already_processed(case_number):
        print("Already processed. Skipping.")
        return "SKIPPED"

    storage.append_pop_row(pop_row)

    try:
        result, candidates, error = match_one_pop(pop_row, bank_df, locked_bank_rows)
    except Exception as e:
        storage.record_failed_pop(case_number, f"MATCHING_ERROR:{e}", pop_row)
        print(f"FAILED (matching): {e}")
        return "FAILED"

    if error:
        storage.record_failed_pop(case_number, error, pop_row)
        print(f"SKIPPED (invalid POP data): {error}")
        return "INVALID"

    storage.append_match_result(result, pop_row.get("pop_value_date"))
    storage.append_candidate_audit(case_number, candidates, pop_row.get("pop_value_date"))

    print(f"Result: {result['status']} ({result['match_reason']})")
    return result["status"]


def main():
    print("=" * 70)
    print("POP PIPELINE - email-log source (August cases)")
    print("=" * 70)

    ensure_bank_master()

    bank_df = pd.read_excel(BANK_MASTER_FILE)
    print(f"Bank master loaded: {len(bank_df)} rows")

    locked_bank_rows = storage.load_locked_bank_rows()
    print(f"Resumed lock state: {len(locked_bank_rows)} bank rows already matched")

    if not EMAIL_LOG_FILE.exists():
        raise FileNotFoundError(f"Email log not found:\n{EMAIL_LOG_FILE}")

    pop_rows = load_email_log_rows(EMAIL_LOG_FILE)
    print(f"Email-log rows loaded: {len(pop_rows)}")

    summary = {}

    for index, pop_row in enumerate(pop_rows, start=1):
        print(f"\n[{index}/{len(pop_rows)}]", end=" ")
        status = process_one_row(pop_row, bank_df, locked_bank_rows)
        summary[status] = summary.get(status, 0) + 1

    print()
    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    for status, count in summary.items():
        print(f"{status:<10}: {count}")


if __name__ == "__main__":
    main()

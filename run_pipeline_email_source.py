"""
run_pipeline_email_source.py — same per-POP pipeline as run_pipeline.py,
but sourcing rows from the Salesforce email log instead of raw documents.

For the 90 August cases where no raw POP document/image exists —
only a case-notification email with receipt info embedded in the body.

Reuses matching.py / storage.py completely unchanged. The only
difference from run_pipeline.py is the row source: email_log_parser
instead of Document Intelligence + GPT extraction.

CHANGED THIS SESSION: bank master is no longer hardcoded to the
August file - now resolved via --month or --bank-master, exactly
mirroring run_pipeline.py's pattern (KNOWN_BANK_MASTERS dict below
is intentionally duplicated from run_pipeline.py rather than shared,
to avoid touching that already-working file under today's deadline -
flagged as a Phase 3 repo-cleanup item to move both into one shared
config module instead of keeping two copies in sync by hand).

Added --case to process exactly one case number from the email log,
instead of the whole log - the email-source equivalent of
run_pipeline.py's --file (there's no single "file" per case here,
so filtering by case number is the closest matching concept).

Also added E2 subscription-service logging (log_result), one call
per case actually processed this run (not for SKIPPED cases),
covering matching failures, invalid data, and successful match
results alike. There's no per-case file here, so case_number is
used as the attachment_name.

FIXED: email_data must be a JSON string, not a raw dict, per the
subscription service's ResultCreate schema (email_data:
Optional[str]). Now serialized with json.dumps(pop_row,
default=str) so non-JSON-native types (e.g. pandas Timestamp)
don't crash serialization. case_number forced to str() for the
same reason (schema expects Optional[str]).
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from email_log_parser import load_email_log_rows
from matching import match_one_pop
import storage
from config import KNOWN_BANK_MASTERS, resolve_bank_master
from logging_setup import configure_logging
from subscription_client import log_result

logger = configure_logging("run_pipeline_email_source")

# Duplicated from run_pipeline.py - see module docstring above.
# KNOWN_BANK_MASTERS now imported from config.py

EMAIL_LOG_FILE = (
    PROJECT_ROOT / "data" / "input" / "AUG_2026" / "EMAIL_LOG" / "_POP_EmailsLog_2.xlsx"
)



def process_one_row(pop_row, bank_df, locked_bank_rows):
    """
    Runs matching + storage for exactly one email-sourced POP row.
    Never raises - every failure is caught and recorded so the
    next row is never blocked.
    """
    case_number = pop_row["case_number"]

    logger.info("=" * 70)
    logger.info(f"CASE: {case_number} (email source)")
    logger.info("=" * 70)

    if storage.is_case_already_processed(case_number):
        logger.info("Already processed. Skipping.")
        return "SKIPPED"

    storage.append_pop_row(pop_row)

    try:
        result, candidates, error = match_one_pop(pop_row, bank_df, locked_bank_rows)
    except Exception as e:
        storage.record_failed_pop(case_number, f"MATCHING_ERROR:{e}", pop_row)
        log_result(
            str(case_number),
            "FAILED",
            email_data=json.dumps(pop_row, default=str),
            case_number=str(case_number),
        )
        logger.error(f"FAILED (matching): {e}")
        return "FAILED"

    if error:
        storage.record_failed_pop(case_number, error, pop_row)
        log_result(
            str(case_number),
            "INVALID",
            email_data=json.dumps(pop_row, default=str),
            case_number=str(case_number),
        )
        logger.warning(f"SKIPPED (invalid POP data): {error}")
        return "INVALID"

    storage.append_match_result(result, pop_row.get("pop_value_date"))
    storage.append_candidate_audit(case_number, candidates, pop_row.get("pop_value_date"))

    log_result(
        str(case_number),
        result["status"],
        score=result.get("score"),
        email_data=json.dumps(pop_row, default=str),
        case_number=str(case_number),
        fields_count=pop_row.get("fields_count"),
        confidence_score=pop_row.get("overall_confidence"),
        email_received_date=pop_row.get("email_received_date"),
    )

    logger.info(f"Result: {result['status']} ({result['match_reason']})")
    return result["status"]


def main():
    parser = argparse.ArgumentParser(description="POP pipeline - email-log source")
    parser.add_argument(
        "--case", type=str, default=None,
        help="Process exactly one case number from the email log, instead of all rows.",
    )
    parser.add_argument(
        "--month", type=str, default=None,
        help="Which bank master to use, e.g. JUL or AUG. Looked up in KNOWN_BANK_MASTERS.",
    )
    parser.add_argument(
        "--bank-master", type=str, default=None,
        help="Explicit path to a bank master .xlsx. Overrides --month.",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("POP PIPELINE - email-log source")
    logger.info("=" * 70)

    bank_master_path = resolve_bank_master(args.bank_master, args.month)
    logger.info(f"Bank master selected: {bank_master_path}")

    bank_df = pd.read_excel(bank_master_path)
    logger.info(f"Bank master loaded: {len(bank_df)} rows")

    locked_bank_rows = storage.load_locked_bank_rows()
    logger.info(f"Resumed lock state: {len(locked_bank_rows)} bank rows already matched")

    if not EMAIL_LOG_FILE.exists():
        raise FileNotFoundError(f"Email log not found:\n{EMAIL_LOG_FILE}")

    pop_rows = load_email_log_rows(EMAIL_LOG_FILE)

    if args.case:
        pop_rows = [r for r in pop_rows if str(r["case_number"]) == str(args.case)]
        if not pop_rows:
            raise ValueError(f"Case '{args.case}' not found in email log.")

    logger.info(f"Email-log rows loaded: {len(pop_rows)}")

    summary = {}

    for index, pop_row in enumerate(pop_rows, start=1):
        logger.info(f"[{index}/{len(pop_rows)}]")
        status = process_one_row(pop_row, bank_df, locked_bank_rows)
        summary[status] = summary.get(status, 0) + 1

    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    for status, count in summary.items():
        logger.info(f"{status:<10}: {count}")


if __name__ == "__main__":
    main()

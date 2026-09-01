"""
run_batch.py - folder-driven batch entry point for the exe deployment.
Discovers every month with pending work under pop_input/, auto-normalizes
that month's bank statements if new raw files are present, then processes
every POP under that month against that month's bank master. Month is
always decided by folder location - never guessed from an extracted date.
Reuses process_one_pop / process_one_row unchanged from
run_pipeline.py / run_pipeline_email_source.py.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from app_paths import get_data_root
DATA_ROOT = get_data_root()

from logging_setup import configure_logging
from batch_discovery import (
    discover_month_folders,
    discover_pop_files_for_month,
    bank_master_paths_for_month,
    needs_normalization,
)
from batch_normalize import normalize_month
import storage
from run_pipeline import process_one_pop
from run_pipeline_email_source import process_one_row
from email_log_parser import load_email_log_rows

logger = configure_logging("run_batch")


def process_month(month_name):
    logger.info("=" * 70)
    logger.info(f"MONTH: {month_name}")
    logger.info("=" * 70)

    raw_folder, normalized_path = bank_master_paths_for_month(month_name)

    if needs_normalization(month_name):
        logger.info(f"New/updated bank files detected in {raw_folder} - normalizing...")
        combined, file_count = normalize_month(raw_folder, normalized_path)
        logger.info(f"Normalized {file_count} bank file(s) -> {len(combined)} transaction rows")
    elif not normalized_path.exists():
        logger.warning(
            f"No normalized bank master for {month_name} and no raw files to "
            f"build one from ({raw_folder}). Skipping this month - refusing "
            f"to match against no data."
        )
        return {}
    else:
        logger.info(f"Bank master for {month_name} is already up to date.")

    bank_df = pd.read_excel(normalized_path)
    logger.info(f"Bank master loaded: {len(bank_df)} rows")

    locked_bank_rows = storage.load_locked_bank_rows()

    summary = {}

    pop_files = discover_pop_files_for_month(month_name)
    logger.info(f"POP documents to process: {len(pop_files)}")
    for pop_path in pop_files:
        status = process_one_pop(pop_path, bank_df, locked_bank_rows)
        summary[status] = summary.get(status, 0) + 1

    email_log_path = DATA_ROOT / "pop_input" / month_name / "email_log.xlsx"
    if email_log_path.exists():
        pop_rows = load_email_log_rows(email_log_path)
        logger.info(f"Email-log rows to process: {len(pop_rows)}")
        for pop_row in pop_rows:
            status = process_one_row(pop_row, bank_df, locked_bank_rows)
            summary[status] = summary.get(status, 0) + 1
    else:
        logger.info(f"No email_log.xlsx for {month_name} - skipping that source.")

    return summary


def main():
    logger.info("=" * 70)
    logger.info("POP BATCH PIPELINE - folder-driven, all months")
    logger.info("=" * 70)

    months = discover_month_folders()

    if not months:
        logger.warning("No month folders with POP files found under pop_input/. Nothing to do.")
        return

    logger.info(f"Months with pending POPs: {months}")

    grand_summary = {}
    for month_name in months:
        month_summary = process_month(month_name)
        for status, count in month_summary.items():
            grand_summary[status] = grand_summary.get(status, 0) + count

    logger.info("=" * 70)
    logger.info("BATCH COMPLETE - ALL MONTHS")
    logger.info("=" * 70)
    for status, count in grand_summary.items():
        logger.info(f"{status:<10}: {count}")


if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
   

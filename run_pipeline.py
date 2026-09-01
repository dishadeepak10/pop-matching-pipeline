"""
run_pipeline.py — single entry point for the per-POP pipeline.

Flow, per mentor's requirement:

    ensure bank master exists (does NOT re-normalize automatically)
    for each POP file, independently:
        extract (Document Intelligence + GPT)      <- existing src/main.py code
        normalize (in memory)                       <- existing src/main.py code
        build a flat row                             <- src/pop_row_builder.py
        skip if already processed (idempotent)       <- src/storage.py
        append row to the single POP master input    <- src/storage.py
        match against the bank master                <- src/matching.py
        append result to the date-wise output         <- src/storage.py
        on ANY failure for this POP: record it and continue with the next POP

This is a NEW entry point. The old src/main.py (extraction-only) and
match_pop_to_bank.py (batch matching) are left untouched and can be
retired later once this is verified in production use.

CHANGES (this session):
  - Bank master is no longer hardcoded to the August file. It is
    resolved per run via --bank-master, or auto-detected from
    known month folders below. This was found to be a real bug:
    July POPs were at risk of being matched against August's
    bank statements silently.
  - Added --file to process exactly one POP path (any location),
    instead of only scanning the default POP folder.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import main as extraction        # existing, untouched extraction code
from pop_row_builder import build_pop_row
from matching import match_one_pop
import storage
from config import KNOWN_BANK_MASTERS, resolve_bank_master
from logging_setup import configure_logging

logger = configure_logging("run_pipeline")

# Known bank master locations, by month. Add new months here as they
# come in — do NOT hardcode a single file, that caused a real bug
# where July POPs would have silently matched against August data.
# KNOWN_BANK_MASTERS now imported from config.py


def case_number_from_path(pop_path):
    match = re.match(r"(\d+)", pop_path.stem)
    return match.group(1) if match else pop_path.stem



def process_one_pop(pop_path, bank_df, locked_bank_rows):
    """
    Runs the full pipeline for exactly one POP file.
    Never raises — every failure is caught and recorded so the
    next POP is never blocked.
    """
    case_number = case_number_from_path(pop_path)

    logger.info("=" * 70)
    logger.info(f"POP: {pop_path.name}  (case {case_number})")
    logger.info("=" * 70)

    if storage.is_case_already_processed(case_number):
        logger.info("Already processed. Skipping.")
        return "SKIPPED"

    try:
        operation_location = extraction.submit_document(pop_path)
        azure_result = extraction.get_analyze_result(operation_location)
        ocr_text = extraction.extract_ocr_text(azure_result)
        structured_data = extraction.extract_structured_data(ocr_text)
        normalized_data = extraction.save_outputs(pop_path, ocr_text, structured_data)

        pop_row = build_pop_row(case_number, normalized_data)

    except Exception as e:
        storage.record_failed_pop(case_number, f"EXTRACTION_ERROR:{e}")
        logger.error(f"FAILED (extraction): {e}")
        return "FAILED"

    storage.append_pop_row(pop_row)

    try:
        result, candidates, error = match_one_pop(pop_row, bank_df, locked_bank_rows)
    except Exception as e:
        storage.record_failed_pop(case_number, f"MATCHING_ERROR:{e}", pop_row)
        logger.error(f"FAILED (matching): {e}")
        return "FAILED"

    if error:
        storage.record_failed_pop(case_number, error, pop_row)
        logger.warning(f"SKIPPED (invalid POP data): {error}")
        return "INVALID"

    storage.append_match_result(result, pop_row.get("pop_value_date"))
    storage.append_candidate_audit(case_number, candidates, pop_row.get("pop_value_date"))

    logger.info(f"Result: {result['status']} ({result['match_reason']})")
    return result["status"]


def main():
    parser = argparse.ArgumentParser(description="POP pipeline - per-POP processing")
    parser.add_argument(
        "--file", type=str, default=None,
        help="Process exactly one POP file at this path, instead of scanning the default folder.",
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
    logger.info("POP PIPELINE - per-POP processing")
    logger.info("=" * 70)

    extraction.check_configuration()

    bank_master_path = resolve_bank_master(args.bank_master, args.month)
    logger.info(f"Bank master selected: {bank_master_path}")

    bank_df = pd.read_excel(bank_master_path)
    logger.info(f"Bank master loaded: {len(bank_df)} rows")

    locked_bank_rows = storage.load_locked_bank_rows()
    logger.info(f"Resumed lock state: {len(locked_bank_rows)} bank rows already matched")

    if args.file:
        pop_files = [Path(args.file)]
        if not pop_files[0].exists():
            raise FileNotFoundError(f"--file path does not exist:\n{pop_files[0]}")
    else:
        pop_files = extraction.get_pop_documents()
    logger.info(f"POP files to process: {len(pop_files)}")

    summary = {}

    for index, pop_path in enumerate(pop_files, start=1):
        logger.info(f"[{index}/{len(pop_files)}]")
        status = process_one_pop(pop_path, bank_df, locked_bank_rows)
        summary[status] = summary.get(status, 0) + 1

    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    for status, count in summary.items():
        logger.info(f"{status:<10}: {count}")


if __name__ == "__main__":
    main()


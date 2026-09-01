"""
Handles all persistent, cumulative storage for the POP pipeline.

Design:
- ONE pop_master_input.csv - one row per POP, accumulates forever.
- ONE consolidated pop_matched_results.csv for all MATCHED results
  (any date/account/bank, all in one place - not split by date folder).
- ONE consolidated pop_review_queue.csv for everything that needs
  human review: AMBIGUOUS, NO_MATCH, NEAR_AMOUNT.
- Hard failures (extraction/matching errors, invalid POP data) stay
  in their own failed_pops.csv - a different category from "needs
  review" since these are broken inputs, not matching decisions.
- No per-POP intermediate files are ever created.
- Locking state is rebuilt from pop_matched_results.csv on startup,
  so it survives a restart without a separate lock file.
- _append_row_to_csv is schema-safe: if a row has a column the file
  doesn't have yet, the file is expanded (old rows get that column
  filled blank) instead of silently writing misaligned values.
"""

import re
from pathlib import Path

import pandas as pd

from app_paths import get_data_root
DATA_ROOT = get_data_root()

POP_MASTER_DIR = DATA_ROOT / "data" / "pop_master"
POP_MASTER_FILE = POP_MASTER_DIR / "pop_master_input.csv"

OUTPUT_ROOT = DATA_ROOT / "data" / "output"

MATCHED_RESULTS_FILE = OUTPUT_ROOT / "pop_matched_results.csv"
REVIEW_QUEUE_FILE = OUTPUT_ROOT / "pop_review_queue.csv"
FAILED_POP_FILE = OUTPUT_ROOT / "failed_pops.csv"

UNKNOWN_DATE_BUCKET = "UNKNOWN_DATE"


# ============================================================
# HELPERS
# ============================================================

def _safe_date_folder(pop_date):
    """
    Returns a safe folder name for the given POP date.
    Falls back to UNKNOWN_DATE_BUCKET if missing/unparseable.
    Still used by append_candidate_audit (diagnostic, per-date).
    """
    if not pop_date:
        return UNKNOWN_DATE_BUCKET

    text = str(pop_date).strip()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    return UNKNOWN_DATE_BUCKET


def _append_row_to_csv(path, row_dict):
    """
    Appends a single row (dict) to a CSV file, creating it with
    a header if it does not yet exist.

    Schema-safe: if row_dict has a key the existing file's header
    does not have, the ENTIRE file is expanded to include that
    column (old rows filled blank for it) before appending. This
    guarantees column meaning never drifts, even when different
    row producers (e.g. doc-extraction vs email-log) contribute
    slightly different field sets over time.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    row_df = pd.DataFrame([row_dict])

    if not path.exists():
        row_df.to_csv(path, mode="w", header=True, index=False)
        return

    existing_header = pd.read_csv(path, nrows=0).columns.tolist()
    new_columns = [c for c in row_dict.keys() if c not in existing_header]

    if new_columns:
        full_df = pd.read_csv(path, dtype=str)
        for col in new_columns:
            full_df[col] = ""

        combined_columns = existing_header + new_columns
        full_df = full_df.reindex(columns=combined_columns, fill_value="")
        row_df = row_df.reindex(columns=combined_columns, fill_value="")

        full_df = pd.concat([full_df, row_df], ignore_index=True)
        full_df.to_csv(path, mode="w", header=True, index=False)
    else:
        row_df = row_df.reindex(columns=existing_header, fill_value="")
        row_df.to_csv(path, mode="a", header=False, index=False)


# ============================================================
# POP MASTER INPUT
# ============================================================

def is_case_already_processed(case_number):
    """
    Idempotency check. Returns True if this case_number already
    has a row in the POP master input, so a re-run does not
    duplicate it.
    """
    if not POP_MASTER_FILE.exists():
        return False

    existing = pd.read_csv(
        POP_MASTER_FILE,
        usecols=["case_number"],
        dtype=str,
    )

    return str(case_number) in existing["case_number"].astype(str).values


def append_pop_row(row_dict):
    """
    Appends one normalized POP row to the single persistent
    POP master input. Skips silently if the case_number is
    already present (idempotent).
    """
    case_number = row_dict.get("case_number")

    if case_number is not None and is_case_already_processed(case_number):
        return False

    _append_row_to_csv(POP_MASTER_FILE, row_dict)
    return True


# ============================================================
# CONSOLIDATED MATCH RESULTS
# ============================================================

def append_match_result(result_dict, pop_date):
    """
    Appends one completed match result. Routes by status:

    - MATCHED  -> pop_matched_results.csv (the clean, final,
                  organized-by-date/account/bank output)
    - anything else (AMBIGUOUS, NO_MATCH, NEAR_AMOUNT)
                  -> pop_review_queue.csv

    pop_date is always attached explicitly as its own column so
    the output stays organized by date even though everything
    now lives in one file per status, not one folder per date.
    """
    entry = dict(result_dict)
    entry["pop_date"] = pop_date

    status = entry.get("status")

    if status == "MATCHED":
        _append_row_to_csv(MATCHED_RESULTS_FILE, entry)
    else:
        _append_row_to_csv(REVIEW_QUEUE_FILE, entry)

    return status


# ============================================================
# RESUMABLE LOCKING
# ============================================================

def load_locked_bank_rows():
    """
    Rebuilds the set of already-used bank_row_index values from
    pop_matched_results.csv. Only MATCHED rows are ever written
    there, so no extra status filtering is needed.
    """
    locked = set()

    if not MATCHED_RESULTS_FILE.exists():
        return locked

    try:
        df = pd.read_csv(MATCHED_RESULTS_FILE)
    except Exception:
        return locked

    if "bank_row_index" not in df.columns:
        return locked

    for value in df["bank_row_index"].dropna():
        locked.add(value)

    return locked


# ============================================================
# FAILED / INVALID POPS
# ============================================================

def record_failed_pop(case_number, reason, raw_row=None):
    """
    Records a POP that could not be processed (missing required
    fields, extraction error, matching error, etc.) into a single
    separate CSV. This must NEVER raise.
    """
    entry = {
        "case_number": case_number,
        "reason": reason,
    }

    if raw_row:
        for key, value in raw_row.items():
            entry.setdefault(f"raw_{key}", value)

    try:
        _append_row_to_csv(FAILED_POP_FILE, entry)
    except Exception:
        pass


# ============================================================
# CANDIDATE AUDIT (diagnostic - unchanged, still per date)
# ============================================================

def append_candidate_audit(case_number, candidates, pop_date):
    """
    Records every candidate considered for a POP (not just the
    winner), so matching quality can be diagnosed with real
    evidence. Left per-date-folder since this is diagnostic
    tooling, not the production output the mentor asked to
    consolidate.
    """
    folder = _safe_date_folder(pop_date)
    audit_path = OUTPUT_ROOT / folder / "candidate_audit.csv"

    for rank, candidate in enumerate(candidates[:10], start=1):
        entry = {"case_number": case_number, "rank": rank, **candidate}
        _append_row_to_csv(audit_path, entry)



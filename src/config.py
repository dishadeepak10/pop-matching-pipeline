"""
Shared configuration for both POP ingestion paths (document-extraction
and email-log). Single source of truth for which bank master file
backs which month - deduplicated from run_pipeline.py and
run_pipeline_email_source.py, which previously each had their own
identical copy.
"""

from pathlib import Path

KNOWN_BANK_MASTERS = {
    "AUG": Path(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"),
    "JUL": Path(r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"),
}


def resolve_bank_master(explicit_path, month_key):
    """
    Resolution order:
      1. --bank-master path, if given (explicit always wins)
      2. --month key, if given (looked up in KNOWN_BANK_MASTERS)
      3. hard failure - this pipeline will NEVER guess a bank
         master. Guessing wrong means matching against the wrong
         month's transactions, which is worse than not running.
    """
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"--bank-master path does not exist:\n{path}")
        return path

    if month_key:
        key = month_key.upper()
        if key not in KNOWN_BANK_MASTERS:
            raise ValueError(
                f"Unknown --month '{month_key}'. Known months: "
                f"{list(KNOWN_BANK_MASTERS.keys())}. "
                "Add it to KNOWN_BANK_MASTERS in src/config.py, "
                "or pass --bank-master with an explicit path."
            )
        path = KNOWN_BANK_MASTERS[key]
        if not path.exists():
            raise FileNotFoundError(f"Bank master for month '{key}' not found:\n{path}")
        return path

    raise ValueError(
        "No bank master specified. Pass --month (e.g. --month JUL) "
        "or --bank-master <path>. Refusing to guess - matching "
        "against the wrong month's bank data is a silent, hard-to-catch bug."
    )

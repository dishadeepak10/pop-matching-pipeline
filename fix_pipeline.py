"""
One-time fix script - deployment-readiness code-quality pass.
Run once: python fix_pipeline.py
"""
from pathlib import Path

def apply_fix(path, old, new, label):
    text = Path(path).read_text(encoding="utf-8")
    if old not in text:
        print(f"SKIP  ({label}): pattern not found - file may differ from what was reviewed. Needs manual check.")
        return
    count = text.count(old)
    if count > 1:
        print(f"WARN  ({label}): pattern found {count} times, expected 1 - applying to first occurrence only.")
    text = text.replace(old, new, 1)
    Path(path).write_text(text, encoding="utf-8")
    print(f"OK    ({label}): applied.")

# Fix 1: matching.py - pop_has_date NaN/NaT bug (Priority 4 gate)
apply_fix(
    "src/matching.py",
    'pop_has_date = pop.get("pop_value_date") not in (None, "", np.nan)',
    'pop_has_date = pd.notna(pop.get("pop_value_date")) and str(pop.get("pop_value_date")).strip() != ""',
    "matching.py: pop_has_date NaN/NaT bug",
)

# Fix 2: matching.py - remove dead REQUIRED_POP_FIELDS constant
apply_fix(
    "src/matching.py",
    'REQUIRED_POP_FIELDS = ["case_number", "pop_amount", "email_bank_account"]\n\n\ndef match_one_pop',
    'def match_one_pop',
    "matching.py: remove dead REQUIRED_POP_FIELDS",
)

# Fix 3: matching.py - surface pop_confidence in the final result dict
apply_fix(
    "src/matching.py",
    '"pop_source_file": pop_row.get("bank_source_file"),\n\n        "bank_row_index"',
    '"pop_source_file": pop_row.get("bank_source_file"),\n        "pop_confidence": pop_row.get("overall_confidence"),\n\n        "bank_row_index"',
    "matching.py: surface pop_confidence in output",
)

# Fix 4: main.py - remove duplicated file-write block in save_outputs()
apply_fix(
    "src/main.py",
    '''    print(
        f"Normalized JSON: {normalized_output_path}"
    )

    # --------------------------------------------------------
    # Save OCR text
    # --------------------------------------------------------

    ocr_output_path.write_text(
        ocr_text,
        encoding="utf-8"
    )


    # --------------------------------------------------------
    # Save structured JSON
    # --------------------------------------------------------

    json_output_path.write_text(
        json.dumps(
            structured_data,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    print()
    print("=" * 70)
    print("OUTPUT FILES SAVED")
    print("=" * 70)

    print(
        f"OCR text: {ocr_output_path}"
    )

    print(
        f"Structured JSON: {json_output_path}"
    )
    return normalized_data''',
    '''    print(
        f"Normalized JSON: {normalized_output_path}"
    )

    return normalized_data''',
    "main.py: remove duplicated save_outputs() write block",
)

# Fix 5: run_pipeline.py - remove local resolve_bank_master duplicate,
# use the one imported from config.py instead
apply_fix(
    "run_pipeline.py",
    '''def resolve_bank_master(explicit_path, month_key):
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
            raise FileNotFoundError(f"--bank-master path does not exist:\\n{path}")
        return path

    if month_key:
        key = month_key.upper()
        if key not in KNOWN_BANK_MASTERS:
            raise ValueError(
                f"Unknown --month '{month_key}'. Known months: "
                f"{list(KNOWN_BANK_MASTERS.keys())}. "
                "Add it to KNOWN_BANK_MASTERS in run_pipeline.py, "
                "or pass --bank-master with an explicit path."
            )
        path = KNOWN_BANK_MASTERS[key]
        if not path.exists():
            raise FileNotFoundError(f"Bank master for month '{key}' not found:\\n{path}")
        return path

    raise ValueError(
        "No bank master specified. Pass --month (e.g. --month JUL) "
        "or --bank-master <path>. Refusing to guess - matching "
        "against the wrong month's bank data is a silent, hard-to-catch bug."
    )


''',
    '',
    "run_pipeline.py: remove duplicate local resolve_bank_master (use config.py's)",
)

print()
print("Done. Review OK / WARN / SKIP lines above - any SKIP needs a manual look.")

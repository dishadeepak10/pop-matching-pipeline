"""
Per-month bank statement normalization for the batch/exe entry point.
Reuses the exact same processing functions as normalize_bank_statements.py
without modifying that file - only the input folder and output path are
parameterized instead of hardcoded to one fixed location.
"""

from pathlib import Path
import pandas as pd

import normalize_bank_statements as nb


def normalize_month(raw_folder, output_path):
    raw_folder = Path(raw_folder)
    output_path = Path(output_path)

    files = sorted(
        p for p in raw_folder.iterdir()
        if p.is_file()
        and not p.name.startswith("~$")
        and p.suffix.lower() in nb.SUPPORTED_EXTENSIONS
    )

    successful = []
    for path in files:
        df, error = nb.safe_process_file(path)
        if df is not None:
            successful.append(df)

    nonempty = [df for df in successful if df is not None and not df.empty]

    if nonempty:
        combined = pd.concat(nonempty, ignore_index=True, sort=False)
        combined = nb.final_cleanup(combined)
        combined = nb.deduplicate_transactions(combined)
        combined = combined[nb.STANDARD_COLUMNS]
    else:
        combined = pd.DataFrame(columns=nb.STANDARD_COLUMNS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_excel(output_path, index=False)

    return combined, len(files)

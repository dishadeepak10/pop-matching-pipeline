"""
Discovers POP files and bank masters organized by month folder, per
the exe deployment design: POPs arrive in daily bundles already
scoped to one month (pop_input/<MONTH>/<DATE>/...), and bank
statements are organized the same way (bank_statements/<MONTH>/).

Month is NEVER guessed from an extracted date - it is always the
folder a file physically sits in. This removes the OCR-date
reliability risk entirely from bank-master selection.
"""

from pathlib import Path

from app_paths import get_data_root
DATA_ROOT = get_data_root()

POP_INPUT_ROOT = DATA_ROOT / "pop_input"
BANK_STATEMENTS_ROOT = DATA_ROOT / "bank_statements"

SUPPORTED_POP_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def discover_month_folders():
    """
    Returns every month folder name found under pop_input/, e.g.
    ["AUG-2026", "JUL-2026"]. A month only counts if it actually
    has at least one POP file somewhere under it.
    """
    if not POP_INPUT_ROOT.exists():
        return []

    months = []
    for month_dir in sorted(POP_INPUT_ROOT.iterdir()):
        if not month_dir.is_dir():
            continue
        has_pop_file = any(
            p.suffix.lower() in SUPPORTED_POP_EXTENSIONS
            for p in month_dir.rglob("*")
            if p.is_file()
        )
        if has_pop_file:
            months.append(month_dir.name)
    return months


def discover_pop_files_for_month(month_name):
    """
    Returns every POP file under pop_input/<month_name>/, regardless
    of which date subfolder it's in.
    """
    month_dir = POP_INPUT_ROOT / month_name
    if not month_dir.exists():
        return []

    return sorted(
        p for p in month_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_POP_EXTENSIONS
    )


def bank_master_paths_for_month(month_name):
    """
    Returns (raw_folder, normalized_master_path) for a given month.
    Does NOT check existence - callers decide what to do if either
    is missing.
    """
    month_dir = BANK_STATEMENTS_ROOT / month_name
    raw_folder = month_dir / "raw"
    normalized_path = month_dir / "normalized_bank_statements.xlsx"
    return raw_folder, normalized_path


def needs_normalization(month_name):
    """
    True if there are raw bank files newer than the current
    normalized output (or no normalized output exists yet at all).
    This is what lets the exe auto-trigger normalization instead
    of requiring a manual run.
    """
    raw_folder, normalized_path = bank_master_paths_for_month(month_name)

    if not raw_folder.exists():
        return False

    raw_files = [p for p in raw_folder.iterdir() if p.is_file()]
    if not raw_files:
        return False

    if not normalized_path.exists():
        return True

    normalized_mtime = normalized_path.stat().st_mtime
    return any(p.stat().st_mtime > normalized_mtime for p in raw_files)


if __name__ == "__main__":
    months = discover_month_folders()
    print(f"Month folders found: {months}")
    for month in months:
        pops = discover_pop_files_for_month(month)
        raw, normalized = bank_master_paths_for_month(month)
        print(f"\n{month}:")
        print(f"  POP files: {len(pops)}")
        print(f"  Bank raw folder: {raw}  (exists: {raw.exists()})")
        print(f"  Normalized master: {normalized}  (exists: {normalized.exists()})")
        print(f"  Needs normalization: {needs_normalization(month)}")



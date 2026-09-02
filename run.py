r"""
run.py - single entry point for the POP matching pipeline.

Auto-detects whether the target is a POP document path (routes to
run_pipeline.py) or a case number (routes to run_pipeline_email_source.py),
and auto-detects the bank master month from today's date unless overridden
with --month or --bank-master.

Usage:
    python run.py <path-to-pop-document-or-case-number> [--month MONTH] [--bank-master PATH]

Examples:
    python run.py "data\input\Disha_Learning\Disha_Learning\00084379_POP_Document.pdf"
    python run.py 85663
    python run.py 85663 --month JUL
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from logging_setup import configure_logging
from subscription_client import check_subscription

logger = configure_logging("run")

# E1 - subscription gate. Must happen before any routing/processing.
# check_subscription() fails closed (returns False) on network error or
# inactive subscription, per subscription_client.py's own design.
if not check_subscription():
    logger.error("Subscription check failed or inactive - aborting before any processing.")
    sys.exit(1)

# Maps the current calendar month number to a KNOWN_BANK_MASTERS key.
# Extend this as new months come into scope (kept here, not in config.py,
# so config.py's resolve_bank_master keeps its explicit-only, no-guess rule).
MONTH_KEY_BY_NUMBER = {
    7: "JUL",
    8: "AUG",
}


def auto_month_key():
    now = datetime.now()
    key = MONTH_KEY_BY_NUMBER.get(now.month)
    if key is None:
        raise ValueError(
            f"No bank-master month mapping for the current month "
            f"({now.strftime('%B')}). Pass --month explicitly, or add "
            f"the mapping to MONTH_KEY_BY_NUMBER in run.py."
        )
    return key


def main():
    parser = argparse.ArgumentParser(
        description="Single entry point: routes a POP document path or a "
                     "case number to the correct pipeline."
    )
    parser.add_argument(
        "target",
        help="Path to a POP document, OR a case number (email-log source).",
    )
    parser.add_argument(
        "--month",
        help="Bank master month key (e.g. JUL, AUG). "
             "Auto-detected from today's date if omitted.",
    )
    parser.add_argument(
        "--bank-master",
        help="Explicit bank master path. Overrides --month if given.",
    )
    args = parser.parse_args()

    target_path = Path(args.target)
    is_document = target_path.exists() and target_path.is_file()

    month_key = args.month
    if not args.bank_master and not month_key:
        month_key = auto_month_key()
        logger.info(f"No --month given - auto-detected '{month_key}' from today's date.")

    if is_document:
        logger.info(f"Routing '{args.target}' to the document-extraction pipeline (run_pipeline.py).")
        cmd = [sys.executable, str(PROJECT_ROOT / "run_pipeline.py"), "--file", str(target_path)]
    else:
        logger.info(f"Routing '{args.target}' to the email-log pipeline (run_pipeline_email_source.py) as a case number.")
        cmd = [sys.executable, str(PROJECT_ROOT / "run_pipeline_email_source.py"), "--case", args.target]

    if args.bank_master:
        cmd += ["--bank-master", args.bank_master]
    elif month_key:
        cmd += ["--month", month_key]

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

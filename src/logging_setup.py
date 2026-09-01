"""
Shared logging setup for the POP pipeline.

Single source of truth for how every entry point logs: console output
(same visibility as the print() statements it replaces), a persistent
timestamped file under logs/ for every run (full detail, INFO+), and a
second timestamped file under errors/ for every run (WARNING+ only) -
so a client can spot problems at a glance without reading the full log.

Runs launched via run.py and the subprocess it spawns share ONE log
file (and one errors file) per invocation, coordinated via the
POP_RUN_ID environment variable (set here on first use, inherited by
any subprocess). Running run_pipeline.py or run_pipeline_email_source.py
directly still works standalone - it just generates its own run id.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from app_paths import get_project_root

PROJECT_ROOT = get_project_root()
LOG_DIR = PROJECT_ROOT / "logs"
ERROR_DIR = PROJECT_ROOT / "errors"


def _run_id():
    existing = os.environ.get("POP_RUN_ID")
    if existing:
        return existing
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.environ["POP_RUN_ID"] = run_id
    return run_id


def configure_logging(name):
    """
    Returns a logger that writes:
    - INFO+ to the console (same messages the print() calls it
      replaces used to show)
    - INFO+ to a persistent file per run at logs/<run_id>.log
    - WARNING+ to a persistent file per run at errors/<run_id>_errors.log

    Safe to call more than once per process or across the parent/child
    process pair run.py spawns - handlers are only attached once.
    """
    LOG_DIR.mkdir(exist_ok=True)
    ERROR_DIR.mkdir(exist_ok=True)
    run_id = _run_id()
    log_path = LOG_DIR / f"{run_id}.log"
    error_path = ERROR_DIR / f"{run_id}_errors.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        error_handler = logging.FileHandler(error_path, encoding="utf-8")
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

        logger.propagate = False

    return logger

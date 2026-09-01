"""
Shared path resolution that works identically whether running as
plain python (python run_batch.py) or as a frozen PyInstaller exe.

get_project_root(): the exe's own folder (or repo root when not frozen).
Used ONLY for logs/ and errors/ - things that must stay local, next to
the exe, and are safe for anyone to see.

get_data_root(): the OneDrive-synced data folder (.env, data/,
pop_input/, bank_statements/). Never sits next to the exe - resolved
via the OneDriveCommercial environment variable Windows sets for
business OneDrive accounts, falling back to OneDrive (personal
accounts) if that's not set. Raises a clear error if neither is found,
rather than silently falling back to something wrong.
"""
import os
import sys
from pathlib import Path

DATA_FOLDER_NAME = "PopPipelineData"


def get_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_data_root():
    onedrive = os.environ.get("OneDriveCommercial") or os.environ.get("OneDrive")
    if not onedrive:
        raise RuntimeError(
            "Could not find a OneDrive folder on this machine "
            "(OneDriveCommercial/OneDrive environment variable not set). "
            "Make sure OneDrive is installed and signed in."
        )
    data_root = Path(onedrive) / DATA_FOLDER_NAME
    if not data_root.exists():
        raise RuntimeError(
            f"Expected data folder not found: {data_root}\n"
            f"Make sure the '{DATA_FOLDER_NAME}' folder exists inside your "
            f"OneDrive and has finished syncing."
        )
    return data_root

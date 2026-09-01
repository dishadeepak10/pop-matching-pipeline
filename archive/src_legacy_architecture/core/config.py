from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

EMAIL_LOG = Path(
    r".\data\input\Disha_Learning\Disha_Learning\_POP_EmailsLog.xlsx"
)

OUTPUT_DIR = Path(r".\data\output")

OUTPUT_EXCEL = (
    OUTPUT_DIR / "POP_email_merged_final.xlsx"
)

import re
from pathlib import Path


def load_ocr(case_number, output_dir):
    ocr_path = (
        output_dir
        / f"{case_number}_POP_Document"
        / "ocr.txt"
    )

    if not ocr_path.exists():
        return ""

    return ocr_path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def extract_ocr_date(ocr_text):

    text = str(ocr_text or "")

    patterns = [

        # English
        r"\bDate\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        # Dutch document used by Rabobank
        r"\bDatum\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        # Generic transaction-date labels
        r"\bTransaction\s*Date\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        r"\bPayment\s*Date\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

    return None

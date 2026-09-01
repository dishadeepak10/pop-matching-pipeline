import json
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# BASIC VALUE CHECK
# ============================================================

def is_empty_value(value):
    return value is None or (
        isinstance(value, str)
        and value.strip() in ("", "N/A", "Not Applicable")
    )


# ============================================================
# CONFIDENCE VALIDATION
# ============================================================

def validate_confidence(confidence):

    if confidence is None:
        return "missing"

    if not isinstance(confidence, (int, float)):
        return "invalid"

    if not 0 <= confidence <= 100:
        return "invalid"

    return "valid"


# ============================================================
# VALIDATE EXTRACTED.JSON
# ============================================================

def validate_extracted(data, result):

    fields = data.get("fields")

    # --------------------------------------------------------
    # fields must be a LIST
    # --------------------------------------------------------

    if not isinstance(fields, list):

        result["extracted_fields_valid"] = False

        result["errors"].append(
            "extracted.json: 'fields' is missing or is not a list"
        )

        return

    result["extracted_fields_valid"] = True
    result["extracted_field_count"] = len(fields)

    field_names = []

    # --------------------------------------------------------
    # Validate every extracted field
    # --------------------------------------------------------

    for index, field in enumerate(fields):

        if not isinstance(field, dict):

            result["errors"].append(
                f"extracted field #{index + 1} is not an object"
            )

            continue

        # ----------------------------------------------------
        # field_name
        # ----------------------------------------------------

        field_name = field.get("field_name")

        if field_name is None or str(field_name).strip() == "":

            result["extracted_missing_field_name"] += 1

        else:

            field_names.append(
                str(field_name).strip()
            )

        # ----------------------------------------------------
        # value
        # ----------------------------------------------------

        if "value" not in field:

            result["extracted_missing_value"] += 1

            result["errors"].append(
                f"extracted field '{field_name}' missing value"
            )

        elif is_empty_value(field.get("value")):

            result["extracted_null_values"] += 1

        # ----------------------------------------------------
        # confidence
        # ----------------------------------------------------

        confidence_status = validate_confidence(
            field.get("confidence")
        )

        if confidence_status == "missing":

            result["extracted_missing_confidence"] += 1

        elif confidence_status == "invalid":

            result["extracted_invalid_confidence"] += 1

        # ----------------------------------------------------
        # Duplicate field names
        # ----------------------------------------------------

        if field_name:

            normalized_name = str(
                field_name
            ).strip().lower()

            if normalized_name in result[
                "_seen_extracted_names"
            ]:

                result[
                    "duplicate_extracted_field_names"
                ] += 1

            else:

                result[
                    "_seen_extracted_names"
                ].add(normalized_name)

    # --------------------------------------------------------
    # Overall confidence
    # --------------------------------------------------------

    overall_confidence = data.get(
        "overall_confidence"
    )

    overall_status = validate_confidence(
        overall_confidence
    )

    if overall_status == "missing":

        result["missing_overall_confidence"] = 1

    elif overall_status == "invalid":

        result["invalid_overall_confidence"] = 1

    result["_extracted_field_names"] = field_names


# ============================================================
# VALIDATE NORMALIZED.JSON
# ============================================================

def validate_normalized(data, result):

    fields = data.get("fields")

    # --------------------------------------------------------
    # fields must be a DICT
    # --------------------------------------------------------

    if not isinstance(fields, dict):

        result["normalized_fields_valid"] = False

        result["errors"].append(
            "normalized.json: 'fields' is missing or is not an object"
        )

        return

    result["normalized_fields_valid"] = True
    result["normalized_field_count"] = len(fields)

    normalized_names = set()

    # --------------------------------------------------------
    # Validate every normalized field
    # --------------------------------------------------------

    for field_name, field_data in fields.items():

        normalized_names.add(
            str(field_name).strip().lower()
        )

        if not isinstance(field_data, dict):

            result["errors"].append(
                f"normalized field '{field_name}' is not an object"
            )

            continue

        # ----------------------------------------------------
        # value
        # ----------------------------------------------------

        if "value" not in field_data:

            result["normalized_missing_value"] += 1

            result["errors"].append(
                f"normalized field '{field_name}' missing value"
            )

        elif is_empty_value(
            field_data.get("value")
        ):

            result["normalized_null_values"] += 1

        # ----------------------------------------------------
        # confidence
        # ----------------------------------------------------

        confidence_status = validate_confidence(
            field_data.get("confidence")
        )

        if confidence_status == "missing":

            result["normalized_missing_confidence"] += 1

        elif confidence_status == "invalid":

            result["normalized_invalid_confidence"] += 1

        # ----------------------------------------------------
        # original field name
        # ----------------------------------------------------

        original_field_name = field_data.get(
            "original_field_name"
        )

        if (
            original_field_name is None
            or str(original_field_name).strip() == ""
        ):

            result[
                "missing_original_field_name"
            ] += 1

        # ----------------------------------------------------
        # original value
        # ----------------------------------------------------

        if "original_value" not in field_data:

            result[
                "missing_original_value"
            ] += 1

    result["_normalized_field_names"] = normalized_names


# ============================================================
# CROSS-CHECK EXTRACTED vs NORMALIZED
# ============================================================

def cross_check_fields(result):

    extracted_names = result.get(
        "_extracted_field_names",
        []
    )

    normalized_names = result.get(
        "_normalized_field_names",
        set()
    )

    if not extracted_names:
        return

    # --------------------------------------------------------
    # Normalize the extracted names using the same helper
    # from main.py.
    #
    # We intentionally import it rather than duplicate the
    # normalization rules here.
    # --------------------------------------------------------

    try:

        import sys

        sys.path.insert(
            0,
            str(PROJECT_ROOT)
        )

        from src.main import normalize_field_name

    except Exception as e:

        result["errors"].append(
            f"Could not import normalize_field_name: {e}"
        )

        return

    expected_normalized_names = set()

    for original_name in extracted_names:

        normalized_name = normalize_field_name(
            original_name
        )

        expected_normalized_names.add(
            str(normalized_name).strip().lower()
        )

    # --------------------------------------------------------
    # Fields expected from extracted.json but absent
    # --------------------------------------------------------

    missing_from_normalized = (
        expected_normalized_names
        - normalized_names
    )

    # --------------------------------------------------------
    # Extra normalized fields
    # --------------------------------------------------------

    extra_in_normalized = (
        normalized_names
        - expected_normalized_names
    )

    result[
        "missing_from_normalized"
    ] = len(missing_from_normalized)

    result[
        "extra_normalized_fields"
    ] = len(extra_in_normalized)

    result[
        "_missing_normalized_names"
    ] = sorted(
        missing_from_normalized
    )

    result[
        "_extra_normalized_names"
    ] = sorted(
        extra_in_normalized
    )


# ============================================================
# VALIDATE ONE DOCUMENT
# ============================================================

def validate_document(folder):

    extracted_path = folder / "extracted.json"
    normalized_path = folder / "normalized.json"
    ocr_path = folder / "ocr.txt"

    result = {

        "document": folder.name,

        # File existence
        "ocr_exists": ocr_path.exists(),
        "extracted_exists": extracted_path.exists(),
        "normalized_exists": normalized_path.exists(),

        # JSON validity
        "extracted_valid_json": False,
        "normalized_valid_json": False,

        # Extracted
        "extracted_fields_valid": False,
        "extracted_field_count": 0,
        "extracted_missing_field_name": 0,
        "extracted_missing_value": 0,
        "extracted_null_values": 0,
        "extracted_missing_confidence": 0,
        "extracted_invalid_confidence": 0,
        "duplicate_extracted_field_names": 0,
        "missing_overall_confidence": 0,
        "invalid_overall_confidence": 0,

        # Normalized
        "normalized_fields_valid": False,
        "normalized_field_count": 0,
        "normalized_missing_value": 0,
        "normalized_null_values": 0,
        "normalized_missing_confidence": 0,
        "normalized_invalid_confidence": 0,
        "missing_original_field_name": 0,
        "missing_original_value": 0,

        # Cross-check
        "missing_from_normalized": 0,
        "extra_normalized_fields": 0,

        "errors": [],

        # Internal
        "_seen_extracted_names": set(),
        "_extracted_field_names": [],
        "_normalized_field_names": set(),
        "_missing_normalized_names": [],
        "_extra_normalized_names": [],
    }

    # ========================================================
    # OCR CHECK
    # ========================================================

    if not ocr_path.exists():

        result["errors"].append(
            "ocr.txt missing"
        )

    else:

        try:

            ocr_content = ocr_path.read_text(
                encoding="utf-8",
                errors="replace"
            )

            if not ocr_content.strip():

                result["errors"].append(
                    "ocr.txt is empty"
                )

        except Exception as e:

            result["errors"].append(
                f"Could not read ocr.txt: {e}"
            )

    # ========================================================
    # EXTRACTED.JSON
    # ========================================================

    if not extracted_path.exists():

        result["errors"].append(
            "extracted.json missing"
        )

    else:

        try:

            extracted_data = load_json(
                extracted_path
            )

            result["extracted_valid_json"] = True

            validate_extracted(
                extracted_data,
                result
            )

        except Exception as e:

            result["errors"].append(
                f"Invalid extracted.json: {e}"
            )

    # ========================================================
    # NORMALIZED.JSON
    # ========================================================

    if not normalized_path.exists():

        result["errors"].append(
            "normalized.json missing"
        )

    else:

        try:

            normalized_data = load_json(
                normalized_path
            )

            result["normalized_valid_json"] = True

            validate_normalized(
                normalized_data,
                result
            )

        except Exception as e:

            result["errors"].append(
                f"Invalid normalized.json: {e}"
            )

    # ========================================================
    # CROSS-CHECK
    # ========================================================

    if (
        result["extracted_valid_json"]
        and result["normalized_valid_json"]
        and result["extracted_fields_valid"]
        and result["normalized_fields_valid"]
    ):

        cross_check_fields(result)

    # ========================================================
    # DETERMINE PASS / FAIL
    # ========================================================

    passed = (

        result["ocr_exists"]

        and result["extracted_exists"]
        and result["normalized_exists"]

        and result["extracted_valid_json"]
        and result["normalized_valid_json"]

        and result["extracted_fields_valid"]
        and result["normalized_fields_valid"]

        and result["extracted_missing_field_name"] == 0
        and result["extracted_missing_value"] == 0

        and result["extracted_missing_confidence"] == 0
        and result["extracted_invalid_confidence"] == 0

        and result["duplicate_extracted_field_names"] == 0

        and result["missing_overall_confidence"] == 0
        and result["invalid_overall_confidence"] == 0

        and result["normalized_missing_value"] == 0

        and result["normalized_missing_confidence"] == 0
        and result["normalized_invalid_confidence"] == 0

        and result["missing_original_field_name"] == 0
        and result["missing_original_value"] == 0

        and result["missing_from_normalized"] == 0

        and not result["errors"]
    )

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FULL POP DATA VALIDATION")
    print("=" * 70)

    if not OUTPUT_ROOT.exists():

        raise FileNotFoundError(
            f"Output folder not found:\n{OUTPUT_ROOT}"
        )

    folders = sorted(
        path
        for path in OUTPUT_ROOT.iterdir()
        if path.is_dir()
        and path.name.endswith(
            "_POP_Document"
        )
    )

    print()
    print(
        f"Output folders found: {len(folders)}"
    )

    results = []

    # ========================================================
    # VALIDATE EVERY DOCUMENT
    # ========================================================

    for folder in folders:

        result = validate_document(
            folder
        )

        results.append(result)

        print(
            f"{result['status']}: "
            f"{result['document']} | "
            f"extracted_fields="
            f"{result['extracted_field_count']} | "
            f"normalized_fields="
            f"{result['normalized_field_count']} | "
            f"extracted_nulls="
            f"{result['extracted_null_values']} | "
            f"normalized_nulls="
            f"{result['normalized_null_values']}"
        )

        if result["errors"]:

            for error in result["errors"]:

                print(
                    f"    ERROR: {error}"
                )

        if result[
            "missing_from_normalized"
        ]:

            print(
                "    Missing from normalized: "
                + ", ".join(
                    result[
                        "_missing_normalized_names"
                    ]
                )
            )

        if result[
            "extra_normalized_fields"
        ]:

            print(
                "    Extra normalized fields: "
                + ", ".join(
                    result[
                        "_extra_normalized_names"
                    ]
                )
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    passed_count = sum(
        result["status"] == "PASS"
        for result in results
    )

    failed_count = (
        len(results) - passed_count
    )

    total_extracted_fields = sum(
        result["extracted_field_count"]
        for result in results
    )

    total_normalized_fields = sum(
        result["normalized_field_count"]
        for result in results
    )

    total_extracted_nulls = sum(
        result["extracted_null_values"]
        for result in results
    )

    total_normalized_nulls = sum(
        result["normalized_null_values"]
        for result in results
    )

    total_missing_confidence = sum(
        result["extracted_missing_confidence"]
        + result["normalized_missing_confidence"]
        for result in results
    )

    total_invalid_confidence = sum(
        result["extracted_invalid_confidence"]
        + result["normalized_invalid_confidence"]
        for result in results
    )

    total_duplicate_fields = sum(
        result[
            "duplicate_extracted_field_names"
        ]
        for result in results
    )

    total_missing_normalized = sum(
        result[
            "missing_from_normalized"
        ]
        for result in results
    )

    # ========================================================
    # PRINT SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("FULL DATA VALIDATION SUMMARY")
    print("=" * 70)

    print(
        f"Documents checked              : "
        f"{len(results)}"
    )

    print(
        f"Documents passed               : "
        f"{passed_count}"
    )

    print(
        f"Documents failed               : "
        f"{failed_count}"
    )

    print(
        f"Total extracted fields         : "
        f"{total_extracted_fields}"
    )

    print(
        f"Total normalized fields        : "
        f"{total_normalized_fields}"
    )

    print(
        f"Extracted null/empty values    : "
        f"{total_extracted_nulls}"
    )

    print(
        f"Normalized null/empty values   : "
        f"{total_normalized_nulls}"
    )

    print(
        f"Missing confidence             : "
        f"{total_missing_confidence}"
    )

    print(
        f"Invalid confidence             : "
        f"{total_invalid_confidence}"
    )

    print(
        f"Duplicate extracted fields     : "
        f"{total_duplicate_fields}"
    )

    print(
        f"Missing normalized mappings    : "
        f"{total_missing_normalized}"
    )

    print()

    if failed_count == 0:

        print(
            "RESULT: ALL POP DATA PASSED VALIDATION."
        )

    else:

        print(
            "RESULT: SOME POP FILES NEED ATTENTION."
        )

    print("=" * 70)


if __name__ == "__main__":
    main()
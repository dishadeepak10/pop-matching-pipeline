import json
from pathlib import Path


OUTPUT_DIR = Path("data/output")


def inspect_json(file_path):
    print(f"\n{'=' * 80}")
    print(f"FILE: {file_path}")
    print(f"{'=' * 80}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR reading file: {e}")
        return

    fields = data.get("fields", [])

    print(f"Fields type: {type(fields).__name__}")
    print(f"Number of fields: {len(fields) if isinstance(fields, list) else 'N/A'}")

    if not isinstance(fields, list):
        print("WARNING: fields is not a list.")
        return

    currency_fields_found = 0

    for field in fields:
        if not isinstance(field, dict):
            continue

        field_name = field.get("field_name")
        value = field.get("value")
        confidence = field.get("confidence")

        # Look for fields whose name suggests currency.
        if field_name and "currenc" in str(field_name).lower():
            currency_fields_found += 1

            print("\nCURRENCY FIELD FOUND")
            print(f"  field_name : {field_name}")
            print(f"  value      : {value}")
            print(f"  confidence: {confidence}")

    if currency_fields_found == 0:
        print("\nNo field with 'currency' in field_name was found.")

        # Also inspect fields where the value itself may contain currency
        # indicators such as INR, USD, EUR, ₹, $, €, etc.
        possible_currency_values = []

        currency_indicators = [
            "INR",
            "USD",
            "EUR",
            "GBP",
            "AED",
            "SGD",
            "AUD",
            "CAD",
            "JPY",
            "CNY",
            "₹",
            "$",
            "€",
            "£",
        ]

        for field in fields:
            if not isinstance(field, dict):
                continue

            field_name = field.get("field_name")
            value = field.get("value")

            value_text = str(value) if value is not None else ""

            if any(
                indicator.lower() in value_text.lower()
                for indicator in currency_indicators
            ):
                possible_currency_values.append(
                    {
                        "field_name": field_name,
                        "value": value,
                        "confidence": field.get("confidence"),
                    }
                )

        if possible_currency_values:
            print("\nPossible currency values found:")
            for item in possible_currency_values:
                print(f"  field_name : {item['field_name']}")
                print(f"  value      : {item['value']}")
                print(f"  confidence: {item['confidence']}")
                print()
        else:
            print("No obvious currency values found.")


def main():
    if not OUTPUT_DIR.exists():
        print(f"Output directory does not exist: {OUTPUT_DIR}")
        return

    pop_folders = sorted(
        folder
        for folder in OUTPUT_DIR.iterdir()
        if folder.is_dir()
    )

    if not pop_folders:
        print("No POP output folders found.")
        return

    print(f"Found {len(pop_folders)} POP output folders.")

    for folder in pop_folders:
        extracted_file = folder / "extracted.json"
        normalized_file = folder / "normalized.json"

        print(f"\n\n{'#' * 80}")
        print(f"POP FOLDER: {folder.name}")
        print(f"{'#' * 80}")

        if extracted_file.exists():
            inspect_json(extracted_file)
        else:
            print(f"\nMissing: {extracted_file}")

        if normalized_file.exists():
            inspect_json(normalized_file)
        else:
            print(f"\nMissing: {normalized_file}")


if __name__ == "__main__":
    main()
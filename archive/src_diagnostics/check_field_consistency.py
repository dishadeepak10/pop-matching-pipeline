import json
from collections import defaultdict
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FIELD NAME CONSISTENCY CHECK")
    print("=" * 70)

    field_documents = defaultdict(list)

    folders = sorted(
        path
        for path in OUTPUT_ROOT.iterdir()
        if path.is_dir()
    )

    for folder in folders:

        normalized_path = folder / "normalized.json"

        if not normalized_path.exists():
            continue

        with open(
            normalized_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        fields = data.get("fields", {})

        if not isinstance(fields, dict):
            continue

        for field_name in fields:
            field_documents[field_name].append(
                folder.name
            )

    # --------------------------------------------------------
    # Sort fields alphabetically
    # --------------------------------------------------------

    field_names = sorted(field_documents)

    print()
    print(
        f"Unique normalized field names: "
        f"{len(field_names)}"
    )

    print()

    for field_name in field_names:

        documents = field_documents[field_name]

        print(
            f"{field_name:<55} "
            f"{len(documents):>2} documents"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FIELD CONSISTENCY SUMMARY")
    print("=" * 70)

    print(
        f"Documents checked     : {len(folders)}"
    )

    print(
        f"Unique field names    : {len(field_names)}"
    )

    print(
        f"Total field instances : "
        f"{sum(len(v) for v in field_documents.values())}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
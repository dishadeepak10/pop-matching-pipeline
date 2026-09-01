from pathlib import Path
import pandas as pd

BASE = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

processed = set(
    pd.read_excel(BASE / "normalized_bank_statements.xlsx")
    ["source_file"]
    .dropna()
    .astype(str)
    .str.strip()
)

files = sorted(
    p for p in BASE.iterdir()
    if (
        p.is_file()
        and not p.name.startswith("~$")
        and "_cleaned" not in p.name.lower()
        and p.suffix.lower() in {".xls", ".xlsx", ".csv", ".html", ".htm"}
        and "normalized_bank_statements" not in p.name.lower()
        and "source_inventory" not in p.name.lower()
        and "zero_file_diagnosis" not in p.name.lower()
    )
)

missing = [p for p in files if p.name not in processed]

print("=" * 100)
print("MISSING FILE STRUCTURE INSPECTION")
print("=" * 100)
print(f"FILES: {len(missing)}")

for i, path in enumerate(missing, 1):
    print("\n" + "=" * 100)
    print(f"{i:02}. {path.name}")
    print("=" * 100)

    try:
        book = pd.ExcelFile(path)
        print("SHEETS:", book.sheet_names)

        for sheet in book.sheet_names:
            df = pd.read_excel(
                path,
                sheet_name=sheet,
                header=None,
            )

            print(
                f"  SHEET: {sheet!r} | "
                f"ROWS: {len(df)} | "
                f"COLUMNS: {len(df.columns)}"
            )

    except Exception as e:
        print("ERROR:", repr(e))

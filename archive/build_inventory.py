from pathlib import Path
import pandas as pd

INPUT_DIR = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

rows = []

for path in sorted(INPUT_DIR.iterdir()):
    if not path.is_file():
        continue

    ext = path.suffix.lower()

    row = {
        "source_file": path.name,
        "extension": ext,
        "size_kb": round(path.stat().st_size / 1024, 1),
    }

    try:
        if ext in [".xlsx", ".xls"]:
            try:
                xl = pd.ExcelFile(path)
                row["format"] = "EXCEL"
                row["sheets"] = " | ".join(xl.sheet_names)
            except Exception:
                # Some .xls files are actually HTML
                try:
                    tables = pd.read_html(path)
                    row["format"] = "HTML"
                    row["sheets"] = f"{len(tables)} HTML tables"
                except Exception as e:
                    row["format"] = "UNREADABLE"
                    row["sheets"] = str(e)

        elif ext == ".csv":
            row["format"] = "CSV"

            try:
                df = pd.read_csv(path, nrows=5)
                row["columns"] = " | ".join(str(c) for c in df.columns)
            except Exception:
                row["columns"] = "READ_ERROR"

        else:
            row["format"] = "OTHER"

    except Exception as e:
        row["format"] = "ERROR"
        row["error"] = repr(e)

    rows.append(row)

inventory = pd.DataFrame(rows)

output = INPUT_DIR / "source_inventory.xlsx"
inventory.to_excel(output, index=False)

print("=" * 100)
print("SOURCE INVENTORY COMPLETE")
print("=" * 100)
print(f"FILES: {len(inventory)}")
print()
print(inventory["extension"].value_counts())
print()
print(inventory["format"].value_counts())
print()
print(f"OUTPUT: {output}")
import pandas as pd

path = r"D:\bank_files\07-JUL-2026\31-07-2026\matching_diagnostic_top_candidates.xlsx"

xls = pd.ExcelFile(path)

print("=" * 100)
print("SHEETS:")
print(xls.sheet_names)

for sheet in xls.sheet_names:
    print()
    print("=" * 100)
    print("SHEET:", sheet)

    df = pd.read_excel(path, sheet_name=sheet)

    print("SHAPE:", df.shape)
    print("COLUMNS:")
    for col in df.columns:
        print("  -", col)

print()
print("=" * 100)
print("DONE")

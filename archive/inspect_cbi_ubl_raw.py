from pathlib import Path
import pandas as pd

BASE = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

FILES = [
    "CBI-CORPORATE-123141-100012290009.XLS",
    "CBI-OPALZ-ESCROW-123531-100012290821.XLS",
    "UBL-BAYZ-200643146.xls",
    "UBL-OPALZ-RETENTION-113648-200839282.xls",
    "UBL-SKYZ-CONSTRUCTION-123523-200705952.xls",
    "UBL-SKYZ-RETENTION-113621-200705969.xls",
    "UBL-TIMEZ-COLLECTION-123576-200829179.xls",
]


def inspect_cbi(path):
    print("\n" + "=" * 100)
    print(path.name)
    print("=" * 100)

    try:
        xl = pd.ExcelFile(path, engine="xlrd")
        print("SHEETS:", xl.sheet_names)

        for sheet in xl.sheet_names:
            df = pd.read_excel(
                path,
                sheet_name=sheet,
                header=None,
                engine="xlrd"
            )

            print(f"\nSHEET: {sheet}")
            print("SHAPE:", df.shape)
            print(df.to_string(index=False, header=False, max_rows=40))

    except Exception as e:
        print("ERROR:", repr(e))


def inspect_ubl(path):
    print("\n" + "=" * 100)
    print(path.name)
    print("=" * 100)

    raw = path.read_bytes()

    print("FILE SIZE:", len(raw), "bytes")
    print("FIRST 200 BYTES:")
    print(raw[:200])

    text = raw.decode("utf-8", errors="replace")

    print("\nHTML CHECK:")
    print("DOCTYPE:", "<!DOCTYPE" in text.upper())
    print("<TABLE>:", "<TABLE" in text.upper())

    try:
        tables = pd.read_html(text)

        print("\nTABLE COUNT:", len(tables))

        for i, table in enumerate(tables, 1):
            print(f"\n--- TABLE {i} ---")
            print("SHAPE:", table.shape)
            print(table.to_string(index=False, max_rows=20))

    except Exception as e:
        print("\nHTML TABLE PARSE ERROR:", repr(e))


for filename in FILES:
    path = BASE / filename

    if not path.exists():
        print("\nMISSING:", filename)
        continue

    if filename.startswith("CBI-"):
        inspect_cbi(path)
    else:
        inspect_ubl(path)
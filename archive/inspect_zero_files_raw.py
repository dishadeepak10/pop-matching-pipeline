from pathlib import Path
import pandas as pd

BASE = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

files = [
    "AJMAN-OASIZ-1-ESCROW-123593-011181473027.xlsx",
    "AJMAN-PETALZ-ESCROW-113628-011135744026.xlsx",
    "AJMAN-SPLZ-ESCROW-011181984033.xlsx",
    "CBD-BAYZ102-RETENTION-123598-1009727148.XLSX",
    "CBD-CORPORATE-123143-1005801574.XLSX",
    "CBD-ELITZ-RETENTION-113629-1006235426.XLSX",
    "CBI-CORPORATE-123141-100012290009.XLS",
    "CBI-OPALZ-ESCROW-123531-100012290821.XLS",
    "UBL-BAYZ-200643146.xls",
    "UBL-OPALZ-RETENTION-113648-200839282.xls",
    "UBL-SKYZ-CONSTRUCTION-123523-200705952.xls",
    "UBL-SKYZ-RETENTION-113621-200705969.xls",
    "UBL-TIMEZ-COLLECTION-123576-200829179.xls",
]

for name in files:
    path = BASE / name
    print("\n" + "=" * 100)
    print(name)
    print("=" * 100)

    try:
        if path.suffix.lower() == ".xls":
            import xlrd
            book = xlrd.open_workbook(path)
            for sheet in book.sheets():
                print(f"\nSHEET: {sheet.name} | SHAPE: {sheet.nrows} x {sheet.ncols}")
                for row in sheet.get_rows()[:25]:
                    print([c.value for c in row])
        else:
            xls = pd.ExcelFile(path)
            for sheet in xls.sheet_names:
                df = pd.read_excel(path, sheet_name=sheet, header=None)
                print(f"\nSHEET: {sheet} | SHAPE: {df.shape}")
                print(df.head(25).to_string(index=False, header=False))

    except Exception as e:
        print("ERROR:", repr(e))
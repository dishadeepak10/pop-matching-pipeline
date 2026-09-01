import pandas as pd
from pathlib import Path

folder = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

failed = [
    "AJMAN-DMZ-ESCROW-123619- 011190984010.csv_cleaned.xlsx",
    "AJMAN-OASIZ-1-ESCROW-123593-011181473027.xlsx",
    "AJMAN-PETALZ-ESCROW-113628-011135744026.xlsx",
    "AJMAN-SPLZ-ESCROW-011181984033.xlsx",

    "FAB-BBG-123521-4031001746692001.xlsx",
    "FAB-CALL-123529-4031201746692005.xlsx",
    "FAB-CALL-123530-4031201746692006.xlsx",
    "FAB-COLL-1031121746692042.xlsx",
    "FAB-ESCROW-123515-1011221746692029.xlsx",
    "FAB-PEARLZ-ESCROW-123533-4031221746692007.xlsx",

    "MASHREQ-COLLECTION-123125-019000050748.xlsx",
    "MASHREQ-CORPORATE-123124-019000050612.xlsx",
    "MASHREQ-CORPORATE-123131-019000051336.xlsx",
    "MASHREQ-ELEGANZ-CORPORATE-123159-019000080049.xlsx",
    "MASHREQ-GEMZ-CORPORATE-123170-019000086556.xlsx",
    "MASHREQ-SPARKLZ-ESCROW-123577-019500000758.xlsx",
    "MASHREQ-SPARKLZ-RETENTION-123582-019500000759.xlsx",

    "NBO-CALL-123155-2016153979131.xls",
    "NBO-CORPORATE-123153-2016153979001.xls",

    "UAB-CORPORATE-123146-1034025563001.xls",
    "UAB-OLIVZ-ESCROW-123551-1034025563002.xls",
    "UAB-OLIVZ-RETENTION-113635-1034025563003.xls",
    "UAB-PEARLZ-ESCROW-123564-1034025563006.xls",
    "UAB-PEARLZ-RETENTION-113641-1034025563007.xls",
    "UAB-SPORTZ-ESCROW-123557-1034025563004.xls",
    "UAB-SPORTZ-RETENTION-113638-1034025563005.xls",

    "UBL-BAYZ-200643146.xls",
    "UBL-CORPORATE-123169-200822024.xls",
    "UBL-OPALZ-COLLECTION-123171-200830612.xls",
    "UBL-OPALZ-ESCROW-123578-200839299.xls",
    "UBL-OPALZ-RETENTION-113648-200839282.xls",
    "UBL-SKYZ-CONSTRUCTION-123523-200705952.xls",
    "UBL-SKYZ-ESCROW-123522-200705976.xls",
    "UBL-SKYZ-RETENTION-113621-200705969.xls",
    "UBL-TIMEZ-COLLECTION-123576-200829179.xls",
    "UBL-TIMEZ-ESCROW-123575-200829193.xls",
    "UBL-TIMEZ-RETENTION-113647-200829186.xls",
]

for name in failed:
    path = folder / name

    print("\n" + "=" * 100)
    print(name)
    print("=" * 100)

    # File signature
    try:
        with open(path, "rb") as f:
            signature = f.read(16)
        print("SIGNATURE:", signature)
    except Exception as e:
        print("SIGNATURE ERROR:", e)
        continue

    # Try Excel engines
    loaded = False

    for engine in ["openpyxl", "xlrd"]:
        try:
            xls = pd.ExcelFile(path, engine=engine)
            print("ENGINE:", engine)
            print("SHEETS:", xls.sheet_names)

            for sheet in xls.sheet_names[:5]:
                try:
                    raw = pd.read_excel(
                        path,
                        sheet_name=sheet,
                        header=None,
                        engine=engine,
                        nrows=15,
                    )

                    print("\n--- SHEET:", sheet, "---")
                    print("SHAPE PREVIEW:", raw.shape)
                    print(raw.to_string(index=True, header=False))

                except Exception as e:
                    print("SHEET READ ERROR:", repr(e))

            loaded = True
            break

        except Exception as e:
            print("ENGINE", engine, "FAILED:", repr(e))

    if not loaded:
        print("NO EXCEL ENGINE COULD READ THIS FILE")


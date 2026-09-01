from pathlib import Path
import pandas as pd

base = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

files = [
    "AJMAN-OASIZ-1-ESCROW-123593-011181473027.xlsx",
    "CBD-BAYZ102-RETENTION-123598-1009727148.XLSX",
    "CBD-SERENZ -ESCROW-123603-1010131421.XLSX",
    "CBI-CORPORATE-123141-100012290009.XLS",
    "FAB-BBG-123521-4031001746692001.xlsx",
    "UAB-OLIVZ-RETENTION-113635-1034025563003.xls",
]

for f in files:
    print("\n" + "=" * 120)
    print(f)
    print("=" * 120)

    try:
        df = pd.read_excel(
            base / f,
            sheet_name=0,
            header=None,
        )

        print("SHAPE:", df.shape)
        print()
        print(df.to_string(index=True, header=False))

    except Exception as exc:
        print("ERROR:", repr(exc))

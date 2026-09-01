from pathlib import Path
import pandas as pd

ROOT = Path(
    r"D:\bank_files\07-JUL-2026\31-07-2026"
)

FILES = [
    "FAB-CORPORATE-123101-1031001746692014.xlsx",
    "ADIB-CORPORATE-123108-18584563.csv",
    "MASHREQ-CORPORATE-123131-019000051336.xlsx",
    "UBL-TIMEZ-RETENTION-113647-200829186.xls",
    "NBO-CALL-123155-2016153979131.xls",
    "Invest Bank.csv",
    "NBRAK-CORPORATE-123580-663118255001.csv",
]

for filename in FILES:

    path = ROOT / filename

    print("\n" + "=" * 120)
    print("FILE:", filename)
    print("=" * 120)

    if not path.exists():
        print("NOT FOUND")
        continue

    try:
        # ----------------------------------------------------
        # Detect whether Excel or CSV
        # ----------------------------------------------------
        if path.suffix.lower() == ".csv":

            df = pd.read_csv(
                path,
                header=None,
                dtype=str,
                sep=None,
                engine="python",
                on_bad_lines="skip",
            )

            print("FORMAT: CSV")
            print("SHAPE:", df.shape)

            print("\nFIRST 15 ROWS:")
            print(
                df.head(15).to_string(
                    index=False,
                    header=False
                )
            )

        else:

            excel = pd.ExcelFile(path)

            print("FORMAT: EXCEL")
            print("SHEETS:", excel.sheet_names)

            for sheet in excel.sheet_names:

                df = pd.read_excel(
                    path,
                    sheet_name=sheet,
                    header=None,
                    dtype=str,
                )

                print(
                    f"\nSHEET: {sheet}"
                )

                print(
                    "SHAPE:",
                    df.shape
                )

                print(
                    df.head(15).to_string(
                        index=False,
                        header=False
                    )
                )

    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )
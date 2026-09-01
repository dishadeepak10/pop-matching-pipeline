from pathlib import Path
import pandas as pd

FOLDER = Path("testing_bank_statements")

for file in FOLDER.glob("*"):

    print("\n" + "=" * 80)
    print(file.name)
    print("=" * 80)

    excel_file = pd.ExcelFile(file)

    print("Sheets:", excel_file.sheet_names)

    for sheet in excel_file.sheet_names:

        print("\nSheet:", sheet)

        df = pd.read_excel(
            file,
            sheet_name=sheet,
            header=None
        )

        print("Shape:", df.shape)

        print(df.head(15))

        print("\n")
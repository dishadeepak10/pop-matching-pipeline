from pathlib import Path
import pandas as pd

INPUT_FILE = Path(
    r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
)

df = pd.read_excel(INPUT_FILE)

def detect_bank(filename):
    name = str(filename).upper().strip()

    bank_prefixes = {
        "FAB": "FAB",
        "ADCB": "ADCB",
        "CBD": "CBD",
        "MASHREQ": "MASHREQ",
        "NBO": "NBO",
        "UAB": "UAB",
        "UBL": "UBL",
        "AJMAN": "AJMAN",
        "CBI": "CBI",
        "ABK": "ABK",
        "NBF": "NBF",
        "NBRAK": "NBRAK",
        "ADIB": "ADIB",
        "NBB": "NBB",
        "INVEST": "INVEST BANK",
    }

    for prefix, bank in bank_prefixes.items():
        if name.startswith(prefix):
            return bank

    return "UNKNOWN"


df["bank_name"] = df["source_file"].apply(detect_bank)

df.to_excel(
    INPUT_FILE,
    index=False
)

print("=" * 100)
print("BANK NAME UPDATE COMPLETE")
print("=" * 100)

print("\nROWS BY BANK:")
print(df["bank_name"].value_counts(dropna=False))

print("\nUNKNOWN FILES:")
unknown = df[df["bank_name"] == "UNKNOWN"]

if unknown.empty:
    print("NONE")
else:
    print(
        unknown["source_file"]
        .value_counts()
        .to_string()
    )

print("\nFINAL SHAPE:")
print(df.shape)
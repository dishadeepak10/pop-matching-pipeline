from pathlib import Path
import pandas as pd


BANK_FILE = Path(
    r"D:\bank_files\07-JUL-2026\31-07-2026\normalized_bank_statements.xlsx"
)

POP_FILE = Path(
    r"D:\Disha_Workarea\pop_process\data\output\POP_email_merged_final.xlsx"
)


print("=" * 100)
print("MATCHING INPUT INSPECTION")
print("=" * 100)

print("\nBANK FILE:")
print(BANK_FILE)
print("Exists:", BANK_FILE.exists())

print("\nPOP FILE:")
print(POP_FILE)
print("Exists:", POP_FILE.exists())


if BANK_FILE.exists():
    bank = pd.read_excel(BANK_FILE)

    print("\n" + "=" * 100)
    print("BANK DATA")
    print("=" * 100)

    print("Shape:", bank.shape)
    print("\nColumns:")
    print(bank.columns.tolist())

    print("\nFirst 3 rows:")
    print(bank.head(3).to_string(index=False))


if POP_FILE.exists():
    pop = pd.read_excel(POP_FILE)

    print("\n" + "=" * 100)
    print("POP DATA")
    print("=" * 100)

    print("Shape:", pop.shape)
    print("\nColumns:")
    print(pop.columns.tolist())

    print("\nFirst 3 rows:")
    print(pop.head(3).to_string(index=False))
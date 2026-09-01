from pathlib import Path
import pandas as pd


POP_FILE = Path(
    r"D:\Disha_Workarea\pop_process\data\output\POP_email_merged_final.xlsx"
)


pop = pd.read_excel(POP_FILE)


print("=" * 120)
print("POP CASE INSPECTION")
print("=" * 120)

print(f"Total cases: {len(pop)}")

columns = [
    "case_number",
    "sender_name",
    "transaction_date",
    "amount",
    "currency",
    "reference_number",
    "sender_bank",
    "email_receipt_amount",
    "email_receipt_reference",
    "pop_amount",
    "pop_currency",
    "pop_value_date",
    "pop_booking_reference",
]


print("\n" + "=" * 120)
print("POP CASES")
print("=" * 120)

print(
    pop[columns].to_string(index=False)
)


print("\n" + "=" * 120)
print("NON-NULL COUNTS")
print("=" * 120)

for col in columns:
    print(
        f"{col:<30} : "
        f"{pop[col].notna().sum():>3} / {len(pop)}"
    )


print("\n" + "=" * 120)
print("AMOUNT SOURCE COVERAGE")
print("=" * 120)

for col in [
    "amount",
    "pop_amount",
    "email_receipt_amount",
]:
    print(
        f"{col:<25} : "
        f"{pop[col].notna().sum():>3} populated"
    )


print("\n" + "=" * 120)
print("REFERENCE SOURCE COVERAGE")
print("=" * 120)

for col in [
    "reference_number",
    "pop_booking_reference",
    "email_receipt_reference",
]:
    print(
        f"{col:<30} : "
        f"{pop[col].notna().sum():>3} populated"
    )


print("\n" + "=" * 120)
print("DATE SOURCE COVERAGE")
print("=" * 120)

for col in [
    "transaction_date",
    "pop_value_date",
    "email_created_date",
]:
    print(
        f"{col:<30} : "
        f"{pop[col].notna().sum():>3} populated"
    )
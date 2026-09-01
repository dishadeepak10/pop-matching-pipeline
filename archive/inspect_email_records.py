import sys
from pathlib import Path

sys.path.insert(0, "src")

from services.email_service import load_email_records

if len(sys.argv) != 2:
    print("Usage: python inspect_email_records.py <excel_file>")
    sys.exit(1)

email_log = Path(sys.argv[1])

records = load_email_records(email_log)

print("EMAIL RECORDS:", len(records))
print("=" * 100)

for case_number, record in records.items():
    print()
    print("-" * 100)
    print("CASE:", case_number)
    print("-" * 100)

    for key, value in record.items():
        print(f"{key} = {value}")

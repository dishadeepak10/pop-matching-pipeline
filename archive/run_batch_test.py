import normalize_bank_statements as nbs
from pathlib import Path

base = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")

excluded = {
    "normalized_bank_statements.xlsx",
    "source_inventory.xlsx",
    "zero_file_diagnosis.xlsx",
}

files = [
    p for p in sorted(base.iterdir())
    if p.is_file()
    and p.suffix.lower() in nbs.SUPPORTED_EXTENSIONS
    and p.name.lower() not in excluded
    and not p.name.lower().endswith("_cleaned.xlsx")
]

print(f"BANK FILES TO TEST: {len(files)}")
print("=" * 120)

results = []
failures = []

for f in files:
    print("\n" + "=" * 120)
    print(f"TESTING: {f.name}")
    print("=" * 120)

    try:
        result = nbs.process_file(f)
        rows = len(result)
        cols = len(result.columns)

        results.append((f, rows, cols, "PASS"))
        print(f"RESULT: PASS | rows={rows} | cols={cols}")

    except Exception as exc:
        failures.append((f, repr(exc)))
        results.append((f, 0, 0, "FAIL"))
        print(f"RESULT: FAIL | {repr(exc)}")

print("\n" + "=" * 120)
print("FINAL BATCH SUMMARY")
print("=" * 120)

for f, rows, cols, status in results:
    print(f"{status:<5} | {rows:>5} rows | {cols:>2} cols | {f.name}")

print("\n" + "=" * 120)
print(f"TOTAL TESTED : {len(files)}")
print(f"PASSED       : {sum(1 for x in results if x[3] == 'PASS')}")
print(f"FAILED       : {len(failures)}")

if failures:
    print("\nFAILURES:")
    for f, error in failures:
        print(f"  {f.name}")
        print(f"    {error}")

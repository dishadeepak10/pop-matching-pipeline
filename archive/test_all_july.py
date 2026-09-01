import normalize_bank_statements as nbs
from pathlib import Path

folder = Path(r"D:\bank_files\07-JUL-2026\31-07-2026")
files = sorted(p for p in folder.iterdir() if p.suffix.lower() in [".xls", ".xlsx"])

ok = []
failed = []

for i, file in enumerate(files, 1):
    try:
        df = nbs.normalize_bank_statement(file)
        ok.append((file.name, len(df), str(df["bank_name"].iloc[0])))
        print(f"[{i:03}/{len(files)}] OK   {file.name} -> {len(df)} rows")
    except Exception as e:
        failed.append((file.name, type(e).__name__, str(e)))
        print(f"[{i:03}/{len(files)}] FAIL {file.name} -> {type(e).__name__}: {e}")

print("\n" + "=" * 80)
print(f"SUCCESS: {len(ok)}")
print(f"FAILED:  {len(failed)}")

print("\nFAILED FILES:")
for item in failed:
    print(item)

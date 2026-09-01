from pathlib import Path

p = Path("match_pop_to_bank.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = 1180
end = 1197

new = [
    '        elif (',
    '            len(usable) == 1',
    '            and has_real_pop_date',
    '            and exact_date',
    '        ):',
    '',
    '            best["status"] = "MATCHED"',
    '            best["match_reason"] = (',
    '                "EXACT_AMOUNT_AND_DATE_UNIQUE"',
    '            )',
]

lines[start:end] = new

p.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("DONE: unique exact-amount candidate now requires exact POP date.")

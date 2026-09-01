import csv

path = r"data\pop_master\pop_master_input.csv"

with open(path, newline="", encoding="utf-8") as f:
    reader = list(csv.reader(f))

header = reader[0]
data = reader[1:]

insert_pos = len(header) - 1
new_header = header[:insert_pos] + ["email_payment_method"] + header[insert_pos:]

repaired = []
unexpected = 0

for row in data:
    if len(row) == len(header):
        new_row = row[:insert_pos] + [""] + row[insert_pos:]
    elif len(row) == len(header) + 1:
        new_row = row
    else:
        unexpected += 1
        new_row = row + [""] * (len(new_header) - len(row))
    repaired.append(new_row)

with open(path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(new_header)
    writer.writerows(repaired)

print(f"Repaired {len(repaired)} rows.")
print(f"New header: {new_header}")
print(f"Rows with unexpected field count (needs manual look): {unexpected}")

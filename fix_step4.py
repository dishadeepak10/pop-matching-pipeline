path = r"src\pop_row_builder.py"
text = open(path, encoding="utf-8").read()
old = '        "overall_confidence": normalized_data.get("overall_confidence"),'
new = old + '\n        "fields_count": len(fields),'
assert old in text, "pattern not found - check file manually"
text = text.replace(old, new)
open(path, "w", encoding="utf-8").write(text)
print("updated pop_row_builder.py")

path = r"src\email_log_parser.py"
text = open(path, encoding="utf-8").read()
old = '        "overall_confidence": None,'
new = old + '\n        "fields_count": sum(1 for v in [amount, bank_name, payment_method, customer_name, account, reference] if v),\n        "email_received_date": pop_value_date,'
assert old in text, "pattern not found - check file manually"
text = text.replace(old, new)
open(path, "w", encoding="utf-8").write(text)
print("updated email_log_parser.py")

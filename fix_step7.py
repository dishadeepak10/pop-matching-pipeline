path = "run_pipeline.py"
text = open(path, encoding="utf-8").read()

old = '''    log_result(
        pop_path.name,
        result["status"],
        score=result.get("score"),
        email_data=json.dumps(pop_row, default=str),
        case_number=str(case_number),'''
new = '''    log_result(
        pop_path.name,
        result["status"],
        score=result.get("score"),
        email_data=json.dumps(pop_row, default=str),
        case_number=str(case_number),
        fields_count=pop_row.get("fields_count"),
        confidence_score=pop_row.get("overall_confidence"),
        email_received_date=pop_row.get("email_received_date"),'''
assert old in text, "pattern not found - check file manually"
text = text.replace(old, new)
open(path, "w", encoding="utf-8").write(text)
print("updated run_pipeline.py")

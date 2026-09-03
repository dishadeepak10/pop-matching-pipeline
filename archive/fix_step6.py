path = "subscription_client.py"
text = open(path, encoding="utf-8").read()

old_sig = "def log_result(attachment_name: str, match_status: str, score=None, email_data=None, case_number=None) -> None:"
new_sig = "def log_result(attachment_name: str, match_status: str, score=None, email_data=None, case_number=None, fields_count=None, confidence_score=None, email_received_date=None) -> None:"
assert old_sig in text, "signature pattern not found"
text = text.replace(old_sig, new_sig)

old_json = '''            json={
                "attachment_name": attachment_name,
                "match_status": match_status,
                "score": score,
                "email_data": email_data,
                "case_number": case_number,
            },'''
new_json = '''            json={
                "attachment_name": attachment_name,
                "match_status": match_status,
                "score": score,
                "email_data": email_data,
                "case_number": case_number,
                "fields_count": fields_count,
                "confidence_score": confidence_score,
                "email_received_date": email_received_date,
            },'''
assert old_json in text, "json block pattern not found"
text = text.replace(old_json, new_json)

open(path, "w", encoding="utf-8").write(text)
print("updated subscription_client.py")

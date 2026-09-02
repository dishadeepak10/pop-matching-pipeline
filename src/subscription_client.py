"""
Client for the pop_subscription_service. Called by run.py at exe startup
(E1 - subscription check) and after each individual POP is processed
(E2 - log result).
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
SUBS_KEY = os.getenv("SUBS_KEY", "test-key-123")
CLIENT_NAME = os.getenv("CLIENT_NAME", "test_client")
FAIL_CLOSED_ON_NETWORK_ERROR = True


def check_subscription() -> bool:
    """
    Returns True if the subscription is active and processing may proceed.
    Returns False (fail closed) on any network error or inactive subscription.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/subscription/check",
            headers={"x-subs-key": SUBS_KEY, "x-client-name": CLIENT_NAME},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return bool(data.get("is_active"))
    except requests.RequestException as e:
        print(f"[subscription check] network error, treating as inactive: {e}")
        return not FAIL_CLOSED_ON_NETWORK_ERROR


def log_result(attachment_name: str, match_status: str, score=None, email_data=None, case_number=None, fields_count=None, confidence_score=None, email_received_date=None) -> None:
    """
    Logs one processed POP's result. Failure here must NOT stop the batch -
    caught and printed, never raised.
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/results",
            headers={"x-subs-key": SUBS_KEY, "x-client-name": CLIENT_NAME},
            json={
                "attachment_name": attachment_name,
                "match_status": match_status,
                "score": score,
                "email_data": email_data,
                "case_number": case_number,
                "fields_count": fields_count,
                "confidence_score": confidence_score,
                "email_received_date": email_received_date,
            },
            timeout=5,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[log_result] failed to log {attachment_name}, continuing: {e}")

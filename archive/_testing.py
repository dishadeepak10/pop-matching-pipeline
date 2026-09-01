


import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import openai

def test_llm_client_prompt():
 
    ocr_text = """
        Transfer Receipt
 
        From:
        ABUBAKAR SADIQ BELLO
 
        Beneficiary:
        PAPIER PLUS FZE
 
        Transfer Date:
        17/03/2025
 
        Time:
        14:35:12
 
        Transfer Amount:
        AED 150,000.00
 
        Reference:
        TRX123456789
 
        Description:
        Invoice Payment
    """
 
    print("Calling Azure OpenAI for extraction...")
 
    # AZURE_OPENAI_API_KEY for Azure LLMs
    # Note: Replace with your actual Azure OpenAI API key and endpoint
    AZURE_OPENAI_API_KEY="your-key-here"
    AZURE_OPENAI_API_VERSION="2024-06-01"
    AZURE_OPENAI_API_ENDPOINT="your-endpoint-here"
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini"
 
 
    # azure_openai_client = settings.azure_openai_client
 
    client = openai.AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_API_ENDPOINT,
    )
 
    system_prompt ="""
        You are a helpful assistant. Extract the payment fields from the OCR extracted input text.
 
        Return ONLY valid JSON.
 
        The JSON must contain exactly these fields:
 
        {
            "payer_name": "",
            "transaction_date": "",
            "transaction_time": "",
            "amount": "",
            "currency": "",
            "payment_type": "",
            "reference_number": "",
            "payment_description": ""
        }
 
        If a field cannot be identified, return an empty string.
 
    """
    document_content = ocr_text
    deployment_name = AZURE_OPENAI_DEPLOYMENT_NAME
 
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"OCR INPUT:\n{document_content}"}
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
 
    # Get raw response first
    raw_content = response.choices[0].message.content
 
    print("Successfully received response from Azure OpenAI.")
    print(f"Azure OpenAI Raw Output: {repr(raw_content)}")
    print("\n------------------------\n")
 
    # Validate response before json.loads()
    if not raw_content or not raw_content.strip():
        raise ValueError(
            "Azure OpenAI returned an empty response."
        )
 
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print("Invalid JSON returned by Azure OpenAI.")
        print(f"Raw content: {repr(raw_content)}")
        raise e
 
    print(f"Parsed Azure OpenAI Output: {content}")

def test_document_intelligence():
    pass


if __name__ == "__main__":
    # test_llm_client_prompt()

    test_document_intelligence()

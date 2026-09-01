import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import logging
import openai
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================
from app_paths import get_data_root
load_dotenv(get_data_root() / ".env")
# ============================================================
# PROJECT / INPUT
# ============================================================
from app_paths import get_data_root
DATA_ROOT = get_data_root()

INPUT_FOLDER = (
    DATA_ROOT
    / "data"
    / "input"
    / "Disha_Learning"
    / "Disha_Learning"
)

OUTPUT_ROOT = DATA_ROOT / "data" / "output"
LOG_FILE = OUTPUT_ROOT / "processing_errors.log"

OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}


# ============================================================
# AZURE DOCUMENT INTELLIGENCE
# ============================================================

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv(
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
)

AZURE_DOCUMENT_INTELLIGENCE_KEY = os.getenv(
    "AZURE_DOCUMENT_INTELLIGENCE_KEY"
)

DOC_INTELLIGENCE_API_VERSION = "2024-11-30"
DOC_INTELLIGENCE_MODEL_ID = "prebuilt-layout"

MAX_WAIT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2
HTTP_TIMEOUT_SECONDS = 30


# ============================================================
# AZURE OPENAI
# ============================================================

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION"
)

AZURE_OPENAI_API_ENDPOINT = os.getenv(
    "AZURE_OPENAI_API_ENDPOINT"
)

AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NAME"
)


# ============================================================
# CHECK CONFIGURATION
# ============================================================

def check_configuration():

    required_values = {
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT":
            AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,

        "AZURE_DOCUMENT_INTELLIGENCE_KEY":
            AZURE_DOCUMENT_INTELLIGENCE_KEY,

        "AZURE_OPENAI_API_KEY":
            AZURE_OPENAI_API_KEY,

        "AZURE_OPENAI_API_VERSION":
            AZURE_OPENAI_API_VERSION,

        "AZURE_OPENAI_API_ENDPOINT":
            AZURE_OPENAI_API_ENDPOINT,

        "AZURE_OPENAI_DEPLOYMENT_NAME":
            AZURE_OPENAI_DEPLOYMENT_NAME,
    }

    missing = [
        name
        for name, value in required_values.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables:\n"
            + "\n".join(missing)
        )

    if not INPUT_FOLDER.exists():
        raise FileNotFoundError(
            f"Input folder not found:\n{INPUT_FOLDER}"
        )


# ============================================================
# FIND POP DOCUMENTS
# ============================================================

def get_pop_documents():

    documents = [
        path
        for path in INPUT_FOLDER.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    return sorted(documents)


# ============================================================
# AZURE DOCUMENT INTELLIGENCE
# ============================================================

def clean_endpoint(endpoint):

    return endpoint.rstrip("/")


def submit_document(pop_path):

    print()
    print("Sending document to Azure Document Intelligence...")
    print("Please wait...")

    endpoint = clean_endpoint(
        AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
    )

    url = (
        f"{endpoint}/documentintelligence/"
        f"documentModels/{DOC_INTELLIGENCE_MODEL_ID}:analyze"
        f"?api-version={DOC_INTELLIGENCE_API_VERSION}"
    )

    with open(pop_path, "rb") as f:
        document_bytes = f.read()

    encoded_document = base64.b64encode(
        document_bytes
    ).decode("utf-8")

    payload = json.dumps(
        {
            "base64Source": encoded_document
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key":
            AZURE_DOCUMENT_INTELLIGENCE_KEY,
    }

    request = Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:

        with urlopen(
            request,
            timeout=HTTP_TIMEOUT_SECONDS
        ) as response:

            status_code = response.status
            response_headers = response.headers
            response_body = (
                response.read()
                .decode("utf-8")
            )

    except HTTPError as e:

        error_body = ""

        try:
            error_body = (
                e.read()
                .decode("utf-8")
            )
        except Exception:
            pass

        raise RuntimeError(
            f"Azure Document Intelligence HTTP "
            f"error {e.code}:\n{error_body}"
        )

    except URLError as e:

        raise RuntimeError(
            "Could not connect to Azure "
            f"Document Intelligence:\n{e}"
        )

    print(
        f"Azure returned HTTP {status_code}."
    )

    if status_code != 202:

        raise RuntimeError(
            "Azure did not accept the document.\n"
            f"HTTP status: {status_code}\n"
            f"Response: {response_body}"
        )

    operation_location = (
        response_headers.get(
            "Operation-Location"
        )
    )

    if not operation_location:

        raise RuntimeError(
            "Azure returned 202 but did not "
            "provide Operation-Location."
        )

    print("Azure accepted the document.")
    print("Polling for OCR result...")

    return operation_location
def get_analyze_result(operation_location):

    headers = {
        "Ocp-Apim-Subscription-Key":
            AZURE_DOCUMENT_INTELLIGENCE_KEY,
    }

    start_time = time.time()
    attempt = 0

    # Retry temporary connection problems
    MAX_POLL_RETRIES = 5
    retry_count = 0

    while True:

        elapsed = time.time() - start_time

        if elapsed > MAX_WAIT_SECONDS:

            raise TimeoutError(
                "Azure OCR timed out after "
                f"{MAX_WAIT_SECONDS} seconds."
            )

        attempt += 1

        request = Request(
            operation_location,
            headers=headers,
            method="GET",
        )

        try:

            with urlopen(
                request,
                timeout=HTTP_TIMEOUT_SECONDS
            ) as response:

                body = (
                    response.read()
                    .decode("utf-8")
                )

            # Successful connection, reset retry counter
            retry_count = 0

        except HTTPError as e:

            error_body = ""

            try:
                error_body = (
                    e.read()
                    .decode("utf-8")
                )
            except Exception:
                pass

            raise RuntimeError(
                f"Azure polling HTTP error "
                f"{e.code}:\n{error_body}"
            )

        except URLError as e:

            retry_count += 1

            print()
            print(
                "Temporary Azure polling connection error."
            )
            print(
                f"Retry {retry_count}/{MAX_POLL_RETRIES}"
            )
            print(
                f"Error: {e}"
            )

            if retry_count >= MAX_POLL_RETRIES:

                raise RuntimeError(
                    "Azure polling connection failed "
                    f"after {MAX_POLL_RETRIES} retries:\n"
                    f"{e}"
                )

            # Wait before retrying
            retry_delay = min(
                2 ** retry_count,
                15
            )

            print(
                f"Waiting {retry_delay} seconds "
                "before retry..."
            )

            time.sleep(retry_delay)

            continue

        data = json.loads(body)

        status = str(
            data.get(
                "status",
                ""
            )
        ).lower()

        elapsed_display = int(
            time.time() - start_time
        )

        print(
            f"Poll {attempt}: "
            f"status={status or 'unknown'} "
            f"elapsed={elapsed_display}s"
        )

        if status == "succeeded":

            print()
            print("Azure OCR completed.")

            return data

        if status == "failed":

            error = data.get("error")

            raise RuntimeError(
                "Azure OCR operation failed:\n"
                + json.dumps(
                    error,
                    indent=4,
                    ensure_ascii=False
                )
            )

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

def extract_ocr_text(result):

    analyze_result = result.get(
        "analyzeResult",
        {}
    )

    content = analyze_result.get("content")

    if content:
        return content.strip()

    parts = []

    pages = analyze_result.get(
        "pages",
        []
    )

    for page_number, page in enumerate(
        pages,
        start=1
    ):

        parts.append(
            f"PAGE {page_number}"
        )

        for line in page.get(
            "lines",
            []
        ):

            line_content = line.get("content")

            if line_content:
                parts.append(
                    line_content
                )

        parts.append("")

    return "\n".join(parts).strip()


# ============================================================
# AZURE OPENAI - STRUCTURED FIELD EXTRACTION
# ============================================================

def extract_structured_data(ocr_text):

    print()
    print("Sending OCR text to Azure OpenAI...")
    print(
        f"Deployment: {AZURE_OPENAI_DEPLOYMENT_NAME}"
    )

    client = openai.AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_API_ENDPOINT,
    )

    system_prompt = """
You are an information extraction system for Proof of Payment (POP)
documents, bank transfer receipts, payment receipts, remittance
receipts, and related financial documents.

Your task is to extract ALL meaningful structured information explicitly
present in the OCR text.

IMPORTANT:

1. Extract every meaningful field that is actually present.

2. Do NOT restrict extraction to a predefined list of fields.

3. Create a clear snake_case field_name based on the meaning of the
   original label.

4. Do NOT invent, infer, guess, calculate, or fabricate values.

5. Only extract information explicitly supported by the OCR text.

6. Preserve the original value as closely as possible.

7. Preserve currencies exactly as shown.

8. Preserve dates exactly as shown.

9. Preserve account numbers exactly as shown.

10. Preserve masked account numbers exactly as shown.

11. Preserve reference numbers exactly as shown.

12. Preserve bank names, customer names, beneficiary names, addresses,
    transaction descriptions, payment purposes, exchange rates, fees,
    payment methods, and other meaningful information.

13. OCR may contain incorrect spacing, line breaks, or minor OCR errors.
    Use surrounding context only when the intended value is clearly
    supported by the OCR.

14. Do not compare this document with other documents.

15. Do not add fields merely because they are common on payment documents.
    Only include fields actually supported by the OCR.

CONFIDENCE:

For every extracted field, provide a confidence score from 0 to 100.

95-100 = clearly visible and unambiguous
80-94  = minor OCR issue but meaning is clear
60-79  = noticeable OCR ambiguity
40-59  = significant uncertainty
Below 40 = barely readable but still explicitly present

The output must contain a list of fields.

Each field must contain:

field_name
value
confidence

The field_name should be snake_case.

The value should be a string containing the extracted value.

If the OCR explicitly indicates a value is missing, you may use null.

Do not invent values.

overall_confidence should be the average confidence of all extracted
fields.
"""


    # ========================================================
    # STRUCTURED OUTPUT SCHEMA
    #
    # IMPORTANT:
    # Azure Structured Outputs requires all object properties to be
    # explicitly defined and required when strict=True.
    #
    # Therefore fields is an ARRAY instead of a dynamic object.
    # ========================================================

    response_schema = {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {
                            "type": "string"
                        },
                        "value": {
                            "type": [
                                "string",
                                "null"
                            ]
                        },
                        "confidence": {
                            "type": "number"
                        }
                    },
                    "required": [
                        "field_name",
                        "value",
                        "confidence"
                    ],
                    "additionalProperties": False
                }
            },
            "overall_confidence": {
                "type": [
                    "number",
                    "null"
                ]
            }
        },
        "required": [
            "fields",
            "overall_confidence"
        ],
        "additionalProperties": False
    }


    # ========================================================
    # CALL AZURE OPENAI
    # ========================================================

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,

        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "OCR INPUT:\n\n"
                    + ocr_text
                ),
            },
        ],

        temperature=0,

        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "pop_extraction",
                "strict": True,
                "schema": response_schema
            }
        },
    )


    # ========================================================
    # READ RESPONSE
    # ========================================================

    raw_content = (
        response
        .choices[0]
        .message
        .content
    )

    print()
    print("Azure OpenAI response received.")

    print()
    print("=" * 70)
    print("RAW AZURE OPENAI OUTPUT")
    print("=" * 70)

    print(raw_content)


    if not raw_content or not raw_content.strip():

        raise ValueError(
            "Azure OpenAI returned an empty response."
        )


    # ========================================================
    # PARSE JSON
    # ========================================================

    try:

        structured_data = json.loads(
            raw_content
        )

    except json.JSONDecodeError as e:

        print()
        print(
            "Azure OpenAI did not return valid JSON."
        )

        raise e


    # ========================================================
    # CALCULATE OVERALL CONFIDENCE
    # ========================================================

    fields = structured_data.get(
        "fields",
        []
    )

    confidences = []

    for field in fields:

        if not isinstance(
            field,
            dict
        ):
            continue

        confidence = field.get(
            "confidence"
        )

        if isinstance(
            confidence,
            (int, float)
        ):

            confidences.append(
                confidence
            )


    if confidences:

        overall_confidence = (
            sum(confidences)
            / len(confidences)
        )

        structured_data[
            "overall_confidence"
        ] = round(
            overall_confidence,
            2
        )

    else:

        structured_data[
            "overall_confidence"
        ] = None


    return structured_data
# ============================================================
# NORMALIZATION
# ============================================================

import re
from datetime import datetime


def normalize_date(value):
    """
    Normalize dates when a complete and unambiguous date is present.

    Date-only values are converted to YYYY-MM-DD.

    Date + time values keep the original time/timezone while
    normalizing only the date portion.

    Values without a year or unparseable values are preserved.
    """

    if not isinstance(value, str):
        return value

    original = value.strip()

    if not original:
        return original

    # Normalize repeated whitespace.
    value = re.sub(r"\s+", " ", original).strip()

    # --------------------------------------------------------
    # 1. YYYY/MM/DD or YYYY-MM-DD
    # --------------------------------------------------------

    match = re.search(
        r"(?P<year>\d{4})\s*[/-]\s*"
        r"(?P<month>\d{1,2})\s*[/-]\s*"
        r"(?P<day>\d{1,2})",
        value
    )

    if match:
        try:
            parsed = datetime(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day"))
            )

            return (
                value[:match.start()]
                + parsed.strftime("%Y-%m-%d")
                + value[match.end():]
            )

        except ValueError:
            pass

    # --------------------------------------------------------
    # 2. DD/MM/YYYY or DD-MM-YYYY
    #
    # Accept when the first number is > 12, because then
    # it cannot be a month.
    #
    # Example:
    # 20/07/2026 -> 2026-07-20
    # 24/07/2026 -> 2026-07-24
    # --------------------------------------------------------

    match = re.search(
        r"(?P<day>\d{1,2})\s*[/-]\s*"
        r"(?P<month>\d{1,2})\s*[/-]\s*"
        r"(?P<year>\d{4})",
        value
    )

    if match:
        day_value = int(match.group("day"))
        month_value = int(match.group("month"))

        # If day > 12, DD/MM is unambiguous.
        if day_value > 12:
            try:
                parsed = datetime(
                    int(match.group("year")),
                    month_value,
                    day_value
                )

                return (
                    value[:match.start()]
                    + parsed.strftime("%Y-%m-%d")
                    + value[match.end():]
                )

            except ValueError:
                pass

    # --------------------------------------------------------
    # 3. MM/DD/YYYY or MM-DD-YYYY
    #
    # Accept when the second number is > 12, because then
    # it cannot be a month.
    #
    # Example:
    # 07/21/2026 -> 2026-07-21
    # --------------------------------------------------------

    match = re.search(
        r"(?P<month>\d{1,2})\s*[/-]\s*"
        r"(?P<day>\d{1,2})\s*[/-]\s*"
        r"(?P<year>\d{4})",
        value
    )

    if match:
        month_value = int(match.group("month"))
        day_value = int(match.group("day"))

        # If day > 12, MM/DD is unambiguous.
        if day_value > 12:
            try:
                parsed = datetime(
                    int(match.group("year")),
                    month_value,
                    day_value
                )

                return (
                    value[:match.start()]
                    + parsed.strftime("%Y-%m-%d")
                    + value[match.end():]
                )

            except ValueError:
                pass

    # --------------------------------------------------------
    # 4. DD Mon YYYY / DD Month YYYY
    #
    # Examples:
    # 19 Jul 2026
    # 19 July 2026
    # 21 Jul 2026, 03:01 pm IST
    # --------------------------------------------------------

    match = re.search(
        r"(?P<day>\d{1,2})\s+"
        r"(?P<month>[A-Za-z]{3,9})"
        r"(?:\s*,?\s*)"
        r"(?P<year>\d{4})",
        value
    )

    if match:
        try:
            month = datetime.strptime(
                match.group("month")[:3].title(),
                "%b"
            ).month

            parsed = datetime(
                int(match.group("year")),
                month,
                int(match.group("day"))
            )

            return (
                value[:match.start()]
                + parsed.strftime("%Y-%m-%d")
                + value[match.end():]
            )

        except ValueError:
            pass

    # --------------------------------------------------------
    # 5. Mon DD, YYYY / Month DD, YYYY
    #
    # Examples:
    # Jul 23, 2026
    # July 23, 2026
    # --------------------------------------------------------

    match = re.search(
        r"(?P<month>[A-Za-z]{3,9})\s+"
        r"(?P<day>\d{1,2})"
        r"\s*,?\s*"
        r"(?P<year>\d{4})",
        value
    )

    if match:
        try:
            month = datetime.strptime(
                match.group("month")[:3].title(),
                "%b"
            ).month

            parsed = datetime(
                int(match.group("year")),
                month,
                int(match.group("day"))
            )

            return (
                value[:match.start()]
                + parsed.strftime("%Y-%m-%d")
                + value[match.end():]
            )

        except ValueError:
            pass

    # --------------------------------------------------------
    # 6. Date with space between slash and year
    #
    # Example:
    # 24/07/ 2026 -> 2026-07-24
    # --------------------------------------------------------

    match = re.search(
        r"(?P<day>\d{1,2})\s*/\s*"
        r"(?P<month>\d{1,2})\s*/\s*"
        r"(?P<year>\d{4})",
        value
    )

    if match:
        try:
            parsed = datetime(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day"))
            )

            return (
                value[:match.start()]
                + parsed.strftime("%Y-%m-%d")
                + value[match.end():]
            )

        except ValueError:
            pass

    # --------------------------------------------------------
    # 7. Date-only formats
    # --------------------------------------------------------

    date_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d.%m.%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d-%B-%Y",
        "%d-%B-%y",
        "%d %b %Y",
        "%d %b %y",
        "%d %B %Y",
        "%d %B %y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for date_format in date_formats:
        try:
            parsed = datetime.strptime(
                value,
                date_format
            )

            return parsed.strftime("%Y-%m-%d")

        except ValueError:
            continue

    # --------------------------------------------------------
    # 8. Preserve anything that cannot be safely normalized.
    #
    # Examples:
    # Fri, 24 Jul (Within 4 days)
    # 20 July, 01:22 PM
    # 09:06:02
    # 19.111979
    # --------------------------------------------------------

    return original


def normalize_amount(value):
    """
    Normalize obvious numeric amount formatting while preserving
    the original numeric meaning.

    Examples:
        25,000.00 -> 25000.00
        12.101,03 -> 12101.03

    Values containing non-numeric text are left unchanged.
    """

    if not isinstance(value, str):
        return value

    value = value.strip()

    # Remove common currency symbols and surrounding spaces.
    cleaned = re.sub(
        r"^[^\d\-]+",
        "",
        value
    )

    cleaned = cleaned.strip()

    # European format:
    # 12.101,03 -> 12101.03
    if re.fullmatch(
        r"-?\d{1,3}(?:\.\d{3})+,\d{1,2}",
        cleaned
    ):
        cleaned = (
            cleaned
            .replace(".", "")
            .replace(",", ".")
        )

        return cleaned

    # Standard comma-separated format:
    # 25,000.00 -> 25000.00
    if re.fullmatch(
        r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?",
        cleaned
    ):
        return cleaned.replace(",", "")

    # Plain number.
    if re.fullmatch(
        r"-?\d+(?:\.\d+)?",
        cleaned
    ):
        return cleaned

    return value
def validate_currency(value, field_name=None):
    """
    Detect a currency code from a value or field name.

    Returns:
        A detected currency code (for example AED, USD, AUD)
        or None if no currency can be determined.
    """

    known_currencies = {
        "AED",
        "AUD",
        "CAD",
        "CHF",
        "CNY",
        "EUR",
        "GBP",
        "HKD",
        "INR",
        "JPY",
        "NZD",
        "PHP",
        "SAR",
        "SGD",
        "TRY",
        "USD",
        "USDT",
    }

    if isinstance(value, str):

        value_upper = value.upper()

        matches = re.findall(
            r"\b([A-Z]{3,5})\b",
            value_upper
        )

        for code in matches:

            if code in known_currencies:
                return code

    if isinstance(field_name, str):

        field_upper = field_name.upper()

        field_match = re.search(
            r"_([A-Z]{3,5})$",
            field_upper
        )

        if field_match:

            code = field_match.group(1)

            if code in known_currencies:
                return code

    return None
def normalize_field_name(value):
    """
    Normalize an extracted field name into a consistent
    snake_case-style key.
    """

    if not isinstance(value, str):
        return value

    value = value.strip().lower()

    # Replace spaces and hyphens with underscores.
    value = re.sub(
        r"[\s\-]+",
        "_",
        value
    )

    # Replace other non-alphanumeric characters.
    value = re.sub(
        r"[^a-z0-9_]",
        "_",
        value
    )

    # Collapse repeated underscores.
    value = re.sub(
        r"_+",
        "_",
        value
    )

    # Remove leading/trailing underscores.
    return value.strip("_")


def normalize_structured_data(structured_data):
    """
    Convert raw extracted fields into a consistent normalized structure.

    Original values and confidence scores are preserved.
    """

    raw_fields = structured_data.get(
        "fields",
        []
    )

    normalized_fields = {}

    # --------------------------------------------------------
    # Current extraction format: list
    # --------------------------------------------------------

    if isinstance(raw_fields, list):

        for field in raw_fields:

            if not isinstance(field, dict):
                continue

            original_name = field.get(
                "field_name"
            )

            if not original_name:
                continue

            normalized_name = normalize_field_name(
                original_name
            )

            value = field.get("value")

            confidence = field.get(
                "confidence"
            )

            normalized_value = value

            # ------------------------------------------------
            # Normalize dates and date-containing time fields.
            # ------------------------------------------------

            if (
                isinstance(value, str)
                and (
                    "date" in normalized_name
                    or (
                        "time" in normalized_name
                        and re.search(
                            r"\b\d{4}\b",
                            value
                        )
                    )
                )
            ):
                normalized_value = normalize_date(
                    value
                )

            # ------------------------------------------------
            # Normalize amounts.
            # ------------------------------------------------

            elif (
                (
                    "amount" in normalized_name
                    or normalized_name.endswith("_value")
                )
                and isinstance(value, str)
            ):
                normalized_value = normalize_amount(
                    value
                )

            normalized_fields[
                normalized_name
            ] = {
                "value": normalized_value,
                "confidence": confidence,
                "original_field_name": original_name,
                "original_value": value,
            }

    # --------------------------------------------------------
    # Legacy dictionary-style extraction.
    # --------------------------------------------------------

    elif isinstance(raw_fields, dict):

        for original_name, field in raw_fields.items():

            if not isinstance(field, dict):
                continue

            normalized_name = normalize_field_name(
                original_name
            )

            value = field.get("value")

            confidence = field.get(
                "confidence"
            )

            normalized_value = value

            if (
                "date" in normalized_name
                and isinstance(value, str)
            ):
                normalized_value = normalize_date(
                    value
                )

            elif (
                "amount" in normalized_name
                and isinstance(value, str)
            ):
                normalized_value = normalize_amount(
                    value
                )

            normalized_fields[
                normalized_name
            ] = {
                "value": normalized_value,
                "confidence": confidence,
                "original_field_name": original_name,
                "original_value": value,
            }

    return {
        "fields": normalized_fields,
        "overall_confidence": structured_data.get(
            "overall_confidence"
        )
    }
# ============================================================
# SAVE OUTPUTS
# ============================================================
def save_outputs(
    pop_path,
    ocr_text,
    structured_data
):

    document_name = pop_path.stem

    output_folder = (
        OUTPUT_ROOT / document_name
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    ocr_output_path = (
        output_folder / "ocr.txt"
    )

    json_output_path = (
        output_folder / "extracted.json"
    )

    normalized_output_path = (
        output_folder / "normalized.json"
    )

    # --------------------------------------------------------
    # Normalize extracted data
    # --------------------------------------------------------

    normalized_data = normalize_structured_data(
        structured_data
    )

    # --------------------------------------------------------
    # Save OCR text
    # --------------------------------------------------------

    ocr_output_path.write_text(
        ocr_text,
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Save raw structured JSON
    # --------------------------------------------------------

    json_output_path.write_text(
        json.dumps(
            structured_data,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Save normalized JSON
    # --------------------------------------------------------

    normalized_output_path.write_text(
        json.dumps(
            normalized_data,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print("=" * 70)
    print("OUTPUT FILES SAVED")
    print("=" * 70)

    print(
        f"OCR text: {ocr_output_path}"
    )

    print(
        f"Structured JSON: {json_output_path}"
    )

    print(
        f"Normalized JSON: {normalized_output_path}"
    )

    return normalized_data

# ============================================================
# PROCESS ONE DOCUMENT
# ============================================================

def process_document(pop_path):

    print()
    print("=" * 70)
    print("PROCESSING DOCUMENT")
    print("=" * 70)

    print(
        f"File: {pop_path.name}"
    )

    print(
        f"Path: {pop_path}"
    )


    # --------------------------------------------------------
    # 1. OCR
    # --------------------------------------------------------

    operation_location = submit_document(
        pop_path
    )

    azure_result = get_analyze_result(
        operation_location
    )

    ocr_text = extract_ocr_text(
        azure_result
    )


    print()
    print("=" * 70)
    print("OCR TEXT")
    print("=" * 70)

    print(ocr_text)


    # --------------------------------------------------------
    # 2. Azure OpenAI
    # --------------------------------------------------------

    structured_data = extract_structured_data(
        ocr_text
    )


    # --------------------------------------------------------
    # 3. Structured extraction
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STRUCTURED EXTRACTION")
    print("=" * 70)

    print(
        json.dumps(
            structured_data,
            indent=4,
            ensure_ascii=False
        )
    )


    # --------------------------------------------------------
    # 4. Save results
    # --------------------------------------------------------

    save_outputs(
        pop_path,
        ocr_text,
        structured_data
    )


# ============================================================
# MAIN - BATCH PROCESSING
# ============================================================

def main():

    print()
    print("=" * 70)
    print("POP DOCUMENT BATCH PROCESSING")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Configuration check
    # --------------------------------------------------------

    check_configuration()

    print()
    print("Configuration check: OK")


    # --------------------------------------------------------
    # 2. Find documents
    # --------------------------------------------------------

    documents = get_pop_documents()

    print()
    print(
        f"Input folder: {INPUT_FOLDER}"
    )

    print(
        f"POP documents found: {len(documents)}"
    )


    if not documents:

        print()
        print("No supported POP documents found.")

        return


    print()
    print("Documents to process:")

    for index, document in enumerate(
        documents,
        start=1
    ):

        print(
            f"{index}. {document.name}"
        )


    # --------------------------------------------------------
    # 3. Process documents one by one
    # --------------------------------------------------------

    successful = []
    failed = []


    for index, pop_path in enumerate(
        documents,
        start=1
    ):

        print()
        print()
        print("#" * 70)

        print(
            f"DOCUMENT {index} OF {len(documents)}"
        )

        print(
            f"{pop_path.name}"
        )

        print("#" * 70)


        try:

            process_document(
                pop_path
            )

            successful.append(
                pop_path.name
            )

            print()
            print(
                f"SUCCESS: {pop_path.name}"
            )


        except Exception as e:
            logging.error(
                "Document failed: %s | Error: %s",
                pop_path.name,
                str(e),
                exc_info=True,
            )

            failed.append(
                (
                    pop_path.name,
                    str(e)
                )
            )

            print()
            print(
                f"FAILED: {pop_path.name}"
            )

            print(
                f"Reason: {e}"
            )

            print()
            print(
                "Continuing with the next document..."
            )


    # --------------------------------------------------------
    # 4. Final summary
    # --------------------------------------------------------

    print()
    print()

    print("=" * 70)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 70)

    print(
        f"Total documents : {len(documents)}"
    )

    print(
        f"Successful       : {len(successful)}"
    )

    print(
        f"Failed           : {len(failed)}"
    )


    if failed:

        print()
        print("FAILED DOCUMENTS")
        print("-" * 70)

        for filename, reason in failed:

            print()
            print(
                f"{filename}"
            )

            print(
                f"Reason: {reason}"
            )


    print()
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

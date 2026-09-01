from pathlib import Path
import pandas as pd
import match_pop_to_bank_v6 as engine

BASE_DIR = Path(__file__).resolve().parent

POP_PATH = BASE_DIR / "data" / "output" / "POP_AUG_MASTER.xlsx"
BANK_PATH = Path(r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx")

OUTPUT_DIR = BASE_DIR / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MATCH_OUTPUT = OUTPUT_DIR / "POP_AUG_MATCHES_FINAL.xlsx"
CANDIDATE_OUTPUT = OUTPUT_DIR / "POP_AUG_CANDIDATES_FINAL.xlsx"


def build_pop_source():
    df = pd.read_excel(POP_PATH)

    mapping = {
        "case_number": "case_number",
        "amount": "receipt_amount",
        "reference": "receipt_reference",
        "customer_reference": None,
        "account": "bank_account_number",
        "customer": "customer_name",
        "bank_name": "bank_name",
        "payment_method": "payment_method",
        "source_file": None,
        "date": "pop_date",
    }

    return {
        "path": POP_PATH,
        "data": df,
        "sheet": "POP_AUG_MASTER",
        "mapping": mapping,
    }


def build_bank_source():
    df = pd.read_excel(BANK_PATH)

    mapping = {
        "date": "date",
        "value_date": "value_date",
        "description": "description",
        "reference": "reference",
        "customer_reference": "customer_reference",
        "account": None,
        "transaction_type": "transaction_type",
        "debit_amount": "debit_amount",
        "credit_amount": "credit_amount",
        "balance": "balance",
        "bank_name": "bank_name",
        "source_file": "source_file",
    }

    return {
        "path": BANK_PATH,
        "data": df,
        "sheet": "normalized_bank_statements",
        "mapping": mapping,
    }


def discover_input_files_fixed():
    return build_pop_source(), build_bank_source()


# ------------------------------------------------------------
# FORCE THE ENGINE TO USE THE VERIFIED AUGUST INPUTS
# ------------------------------------------------------------
engine.discover_input_files = discover_input_files_fixed

# ------------------------------------------------------------
# FORCE August output names
# ------------------------------------------------------------
engine.MATCH_OUTPUT = MATCH_OUTPUT
engine.CANDIDATE_OUTPUT = CANDIDATE_OUTPUT


print("=" * 100)
print("AUGUST POP -> BANK MATCHING")
print("=" * 100)

print("\nVERIFIED INPUTS")
print("-" * 100)
print("POP :", POP_PATH)
print("BANK:", BANK_PATH)

pop_check = pd.read_excel(POP_PATH)
bank_check = pd.read_excel(BANK_PATH)

print("\nINPUT VALIDATION")
print("-" * 100)
print("POP ROWS :", len(pop_check))
print("BANK ROWS:", len(bank_check))

print("\nPOP COLUMNS:")
print(list(pop_check.columns))

print("\nBANK COLUMNS:")
print(list(bank_check.columns))

print("\nPOP BANK DISTRIBUTION:")
print(pop_check["bank_name"].value_counts(dropna=False).to_string())

print("\nBANK BANK-CODE DISTRIBUTION:")
print(bank_check["bank_name"].value_counts(dropna=False).to_string())

print("\nMATCHING CONFIGURATION")
print("-" * 100)
print("AMOUNT TOLERANCE :", engine.AMOUNT_TOLERANCE)
print("DATE WINDOW      :", engine.DATE_WINDOW_DAYS, "days")
print("MATCH THRESHOLD  :", engine.MATCH_THRESHOLD)
print("NEAR THRESHOLD   :", engine.NEAR_MATCH_THRESHOLD)
print("MIN SCORE GAP    :", engine.MIN_SCORE_GAP)
print("MAX CANDIDATES   :", engine.MAX_CANDIDATES_PER_POP)

print("\nMATCHING ORDER")
print("1. AMOUNT FIRST")
print("2. REFERENCE / CUSTOMER REFERENCE")
print("3. ACCOUNT")
print("4. CUSTOMER / DESCRIPTION")
print("5. BANK / SOURCE / PAYMENT METHOD")
print("6. DATE SUPPORT")
print("7. ONE BANK TRANSACTION = ONE MATCH")

print("\n" + "=" * 100)
print("STARTING MATCH ENGINE")
print("=" * 100)

engine.main()

print("\n" + "=" * 100)
print("AUGUST MATCHING FINISHED")
print("=" * 100)

print("MATCH OUTPUT    :", MATCH_OUTPUT)
print("CANDIDATE OUTPUT:", CANDIDATE_OUTPUT)

if MATCH_OUTPUT.exists():
    result = pd.read_excel(MATCH_OUTPUT)

    print("\nFINAL RESULT")
    print("-" * 100)
    print("ROWS:", len(result))
    print("\nSTATUS:")
    if "status" in result.columns:
        print(result["status"].value_counts(dropna=False).to_string())
    elif "final_status" in result.columns:
        print(result["final_status"].value_counts(dropna=False).to_string())

if CANDIDATE_OUTPUT.exists():
    candidates = pd.read_excel(CANDIDATE_OUTPUT)

    print("\nCANDIDATE RESULT")
    print("-" * 100)
    print("CANDIDATE ROWS:", len(candidates))

    if "case_number" in candidates.columns:
        print("CASES WITH CANDIDATES:",
              candidates["case_number"].nunique())

print("\nFILES CREATED SUCCESSFULLY.")

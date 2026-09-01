import os
import pandas as pd
from io import StringIO


def normalize_cbi(path):
    df = pd.read_excel(path, sheet_name="report1", header=None)

    # Actual transaction header is row 15
    data = df.iloc[16:].copy()

    rows = []

    for _, r in data.iterrows():
        date = r.iloc[1]

        # Ignore opening/closing/total rows
        if pd.isna(date):
            continue

        date = str(date).strip()

        if date.lower() in ["date", "nan"]:
            continue

        try:
            date = pd.to_datetime(date, dayfirst=True)
        except:
            continue

        description = r.iloc[5]
        cheque = r.iloc[6]
        debit = r.iloc[10]
        credit = r.iloc[14]
        balance = r.iloc[16]

        rows.append({
            "date": date,
            "value_date": date,
            "description": "" if pd.isna(description) else str(description),
            "reference": "" if pd.isna(cheque) else str(cheque),
            "customer_reference": "",
            "transaction_type": (
                "DEBIT" if pd.notna(debit)
                else "CREDIT" if pd.notna(credit)
                else ""
            ),
            "debit_amount": pd.to_numeric(debit, errors="coerce"),
            "credit_amount": pd.to_numeric(credit, errors="coerce"),
            "balance": pd.to_numeric(balance, errors="coerce"),
            "bank_name": "CBI",
            "source_file": os.path.basename(path),
        })

    return pd.DataFrame(rows)


def normalize_ubl(path):
    # UBL .xls files are HTML disguised as XLS
    with open(path, "rb") as f:
        content = f.read()

    html = content.decode("utf-8", errors="ignore")

    tables = pd.read_html(StringIO(html))

    if not tables:
        return pd.DataFrame()

    # Find the transaction table
    df = None

    for table in tables:
        cols = [str(c).strip().lower() for c in table.columns]

        if "date" in cols and "description" in cols:
            df = table
            break

    if df is None:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]

    rows = []

    for _, r in df.iterrows():

        description = str(r.get("Description", "")).strip()

        # Ignore opening balance
        if "OPENING BALANCE" in description.upper():
            continue

        date = r.get("Date")

        if pd.isna(date):
            continue

        rows.append({
            "date": pd.to_datetime(date, errors="coerce"),
            "value_date": pd.to_datetime(
                r.get("Value Date"), errors="coerce"
            ),
            "description": description,
            "reference": str(r.get("Doc No", "")),
            "customer_reference": str(r.get("Buyer Code", "")),
            "transaction_type": (
                "DEBIT"
                if pd.to_numeric(
                    r.get("Withdrawls"), errors="coerce"
                ) not in [0, None]
                else "CREDIT"
            ),
            "debit_amount": pd.to_numeric(
                r.get("Withdrawls"), errors="coerce"
            ),
            "credit_amount": pd.to_numeric(
                r.get("Deposits"), errors="coerce"
            ),
            "balance": pd.to_numeric(
                r.get("Balance"), errors="coerce"
            ),
            "bank_name": "UBL",
            "source_file": os.path.basename(path),
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":

    test_files = [
        r"D:\bank_files\07-JUL-2026\31-07-2026\CBI-CORPORATE-123141-100012290009.XLS",
        r"D:\bank_files\07-JUL-2026\31-07-2026\CBI-OPALZ-ESCROW-123531-100012290821.XLS",
        r"D:\bank_files\07-JUL-2026\31-07-2026\UBL-BAYZ-200643146.xls",
        r"D:\bank_files\07-JUL-2026\31-07-2026\UBL-OPALZ-RETENTION-113648-200839282.xls",
    ]

    for path in test_files:

        print("\n" + "=" * 80)
        print(os.path.basename(path))
        print("=" * 80)

        try:
            if "CBI-" in os.path.basename(path).upper():
                result = normalize_cbi(path)
            else:
                result = normalize_ubl(path)

            print("Shape:", result.shape)
            print(result.to_string(index=False))

        except Exception as e:
            print("ERROR:", repr(e))
"""
Matching engine - per-POP callable version of match_pop_to_bank.py.

Core scoring/decision logic (field_evidence, date_difference_days,
date_score, decide) is UNCHANGED from match_pop_to_bank.py.

Stage 1 of generate_candidates() follows the mentor's account-first
hierarchy with graceful fallbacks when data is missing:
  Priority 1: bank_source_file (if present)
  Priority 2: account number match (bank_account_matches_pop)
  Priority 3: bank name match (narrows to that bank's statements)
  Priority 4: full bank master, only if a POP date exists (last resort)
"""

import re

import numpy as np
import pandas as pd


def clean_text(value):
    if pd.isna(value):
        return ""
    value = str(value).strip().upper()
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_alnum(value):
    value = clean_text(value)
    return re.sub(r"[^A-Z0-9]", "", value)


def normalize_account(value):
    return normalize_alnum(value)


def normalize_name(value):
    value = clean_text(value)
    value = re.sub(r"[^A-Z0-9 ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def name_tokens(value):
    value = normalize_name(value)
    if not value:
        return set()
    return {x for x in value.split() if len(x) >= 2}


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def amount_from_bank(row):
    debit = safe_float(row.get("debit_amount"))
    credit = safe_float(row.get("credit_amount"))
    if pd.notna(credit) and abs(credit) > 0:
        return abs(credit)
    if pd.notna(debit) and abs(debit) > 0:
        return abs(debit)
    return np.nan


def normalize_date(value):
    if pd.isna(value):
        return pd.NaT
    return pd.to_datetime(value, errors="coerce")


def bank_account_matches_pop(pop_row, bank_row):
    pop_account = normalize_account(pop_row.get("email_bank_account"))
    if not pop_account:
        return False

    bank_source = clean_text(bank_row.get("source_file"))
    numbers = re.findall(r"\d{8,}", bank_source)

    for number in numbers:
        if normalize_account(number) == pop_account:
            return True

    return False


def field_evidence(pop, bank):
    evidence = []
    score = 0

    pop_refs = []
    for col in ["pop_booking_reference", "reference_number", "email_receipt_reference"]:
        value = normalize_alnum(pop.get(col))
        if value:
            pop_refs.append(value)

    bank_refs = []
    for col in ["reference", "customer_reference", "description"]:
        value = normalize_alnum(bank.get(col))
        if value:
            bank_refs.append(value)

    for pref in pop_refs:
        for bref in bank_refs:
            if pref == bref:
                score += 40
                evidence.append(f"EXACT_REFERENCE:{pref}")
            elif len(pref) >= 6 and pref in bref:
                score += 30
                evidence.append(f"REFERENCE_CONTAINS:{pref}")
            elif len(bref) >= 6 and bref in pref:
                score += 25
                evidence.append(f"BANK_REFERENCE_CONTAINS:{bref}")

    pop_names = []
    for col in ["email_customer_name", "sender_name", "beneficiary_name"]:
        value = name_tokens(pop.get(col))
        if value:
            pop_names.append(value)

    bank_text = normalize_name(
        " ".join([
            str(bank.get("description", "")),
            str(bank.get("reference", "")),
            str(bank.get("customer_reference", "")),
        ])
    )
    bank_name_tokens = name_tokens(bank_text)

    for tokens in pop_names:
        if not tokens:
            continue
        overlap = tokens.intersection(bank_name_tokens)
        if len(overlap) >= 2:
            score += 25
            evidence.append("CUSTOMER_2+_TOKENS:" + ",".join(sorted(overlap)))
        elif len(overlap) == 1:
            score += 10
            evidence.append("CUSTOMER_1_TOKEN:" + next(iter(overlap)))

    pop_bank = normalize_name(pop.get("email_bank_name"))
    bank_name = clean_text(bank.get("bank_name"))

    bank_aliases = {
        "FAB": ["FAB", "FIRST ABU DHABI BANK", "FIRSTABUDHABIBANK"],
        "ADCB": ["ADCB", "ABU DHABI COMMERCIAL BANK"],
        "CBD": ["CBD", "COMMERCIAL BANK OF DUBAI"],
    }

    if pop_bank:
        normalized_pop_bank = normalize_alnum(pop_bank)
        normalized_bank_name = normalize_alnum(bank_name)
        aliases = bank_aliases.get(bank_name, [])

        matched = any(
            normalized_pop_bank in normalize_alnum(alias) for alias in aliases
        )

        # Generic fallback - works for ANY bank, not just the ones
        # listed in bank_aliases above. The dict only needs entries
        # for abbreviation mismatches (e.g. "FAB" not being a
        # substring of "FIRSTABUDHABIBANK"); every other bank still
        # gets credit via a direct name match.
        if not matched and normalized_bank_name:
            matched = (
                normalized_pop_bank in normalized_bank_name
                or normalized_bank_name in normalized_pop_bank
            )

        if matched:
            score += 10
            evidence.append("POP_BANK_SUPPORT")

    return score, evidence


def date_difference_days(pop, bank):
    pop_dates = []
    for col in ["pop_value_date", "transaction_date", "date_source"]:
        value = normalize_date(pop.get(col))
        if pd.notna(value):
            pop_dates.append(value)

    bank_date = normalize_date(bank.get("date"))
    bank_value_date = normalize_date(bank.get("value_date"))

    if not pop_dates:
        return np.nan

    bank_dates = [x for x in [bank_date, bank_value_date] if pd.notna(x)]
    if not bank_dates:
        return np.nan

    differences = []
    for p in pop_dates:
        for b in bank_dates:
            differences.append(abs((p - b).days))

    return min(differences)


def date_score(days):
    if pd.isna(days):
        return 0
    if days == 0:
        return 30
    if days == 1:
        return 20
    if days <= 3:
        return 10
    if days <= 7:
        return 3
    return 0


def generate_candidates(pop, bank_df):

    pop_amount = safe_float(pop.get("pop_amount"))

    if pd.isna(pop_amount):
        return []

    # --------------------------------------------------------
    # STAGE 1: identify the relevant bank rows.
    # --------------------------------------------------------

    pop_source_file = str(pop.get("bank_source_file") or "").strip().upper()

    account_rows = pd.DataFrame(columns=bank_df.columns)

    # Priority 1: explicit bank_source_file, if present.
    if pop_source_file:
        bank_source_files = (
            bank_df["source_file"].fillna("").astype(str).str.strip().str.upper()
        )
        account_rows = bank_df[bank_source_files.eq(pop_source_file)].copy()

    # Priority 2: account number match.
    if account_rows.empty:
        mask = bank_df.apply(lambda row: bank_account_matches_pop(pop, row), axis=1)
        account_rows = bank_df[mask].copy()
    def _apply_amount_filter(rows):
        """Returns amount-filtered rows, or empty DataFrame if none qualify."""
        rows = rows.copy()
        rows["_bank_amount"] = rows.apply(amount_from_bank, axis=1)
        rows["_amount_difference"] = (rows["_bank_amount"] - pop_amount).abs()

        exact = rows[rows["_amount_difference"].le(0.01)].copy()
        if not exact.empty:
            return exact

        near = rows[rows["_amount_difference"].le(5.00)].copy()
        return near

    working = pd.DataFrame(columns=bank_df.columns)

    if not account_rows.empty:
        working = _apply_amount_filter(account_rows)

    # Priority 3: bank name match. Only accepted if it actually
    # yields a usable amount-matched candidate - a non-empty
    # bank-name subset with no matching amount inside it does NOT
    # count as "found", since the true match may sit elsewhere
    # (e.g. sender's bank differs from the escrow/receiving bank).
    if working.empty:
        pop_bank = normalize_alnum(pop.get("email_bank_name"))
        if pop_bank:
            bank_names = bank_df["bank_name"].fillna("").apply(normalize_alnum)
            bank_mask = bank_names.apply(
                lambda name: bool(name) and (pop_bank in name or name in pop_bank)
            )
            bank_subset = bank_df[bank_mask].copy()
            if not bank_subset.empty:
                working = _apply_amount_filter(bank_subset)

    # Priority 4 (last resort): full bank master, only if a POP date
    # exists - amount-only across 14,000+ rows is too ambiguous
    # otherwise and risks false positives.
    if working.empty:
        pop_has_date = pd.notna(pop.get("pop_value_date")) and str(pop.get("pop_value_date")).strip() != ""
        if pop_has_date:
            working = _apply_amount_filter(bank_df)
        else:
            return []

    if working.empty:
        return []
        
    # --------------------------------------------------------
    # STAGE 3: FIELD + DATE SCORING (unchanged)
    # --------------------------------------------------------

    candidates = []

    for idx, bank in working.iterrows():

        f_score, f_evidence = field_evidence(pop, bank)
        days = date_difference_days(pop, bank)
        d_score = date_score(days)

        amount_difference = float(bank["_amount_difference"])

        if amount_difference <= 0.01:
            amount_score = 100
        else:
            amount_score = max(0, 50 - amount_difference * 5)

        total_score = amount_score + f_score + d_score

        candidates.append({
            "bank_row_index": idx,
            "bank_date": bank.get("date"),
            "bank_value_date": bank.get("value_date"),
            "bank_description": bank.get("description"),
            "bank_reference": bank.get("reference"),
            "bank_customer_reference": bank.get("customer_reference"),
            "bank_transaction_type": bank.get("transaction_type"),
            "bank_debit_amount": bank.get("debit_amount"),
            "bank_credit_amount": bank.get("credit_amount"),
            "bank_balance": bank.get("balance"),
            "bank_amount": bank["_bank_amount"],
            "bank_name": bank.get("bank_name"),
            "source_file": bank.get("source_file"),
            "amount_difference": amount_difference,
            "date_difference": days,
            "field_score": f_score,
            "date_score": d_score,
            "amount_score": amount_score,
            "score": total_score,
            "evidence": "; ".join(f_evidence),
        })

    candidates.sort(
        key=lambda x: (
            x["score"],
            -x["amount_difference"],
            -(x["field_score"] + x["date_score"]),
        ),
        reverse=True,
    )

    return candidates


def decide(candidates):

    if not candidates:
        return {
            "status": "NO_MATCH",
            "match_reason": "NO_VALID_CANDIDATE",
            "selected": None,
            "score": np.nan,
            "score_gap": np.nan,
        }

    best = candidates[0]

    second_score = candidates[1]["score"] if len(candidates) > 1 else np.nan
    score_gap = best["score"] - second_score if pd.notna(second_score) else np.inf

    exact_amount = best["amount_difference"] <= 0.01

    if exact_amount and best["field_score"] >= 25:
        return {
            "status": "MATCHED",
            "match_reason": "EXACT_AMOUNT_STRONG_FIELD",
            "selected": best, "score": best["score"], "score_gap": score_gap,
        }

    if exact_amount and best["date_difference"] <= 1 and score_gap >= 10:
        return {
            "status": "MATCHED",
            "match_reason": "EXACT_AMOUNT_DATE",
            "selected": best, "score": best["score"], "score_gap": score_gap,
        }

    if exact_amount and len(candidates) > 1 and score_gap < 10:
        return {
            "status": "AMBIGUOUS",
            "match_reason": "MULTIPLE_EXACT_AMOUNT_CANDIDATES",
            "selected": best, "score": best["score"], "score_gap": score_gap,
        }

    if exact_amount and len(candidates) == 1:
        return {
            "status": "MATCHED",
            "match_reason": "UNIQUE_EXACT_AMOUNT",
            "selected": best, "score": best["score"], "score_gap": score_gap,
        }

    return {
        "status": "NEAR_AMOUNT",
        "match_reason": "NO_EXACT_AMOUNT",
        "selected": best, "score": best["score"], "score_gap": score_gap,
    }


def match_one_pop(pop_row, bank_df, locked_bank_rows):
    """
    Matches a single POP row against the bank master.
    Returns (result_dict, candidates_list, error_reason).
    """

    missing = []
    for f in ["case_number", "pop_amount"]:
        v = pop_row.get(f)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            missing.append(f)

    if missing:
        return None, [], f"MISSING_REQUIRED_FIELDS:{','.join(missing)}"

    # Currency gate: no conversion is ever performed. A POP with an
    # explicitly non-AED currency is excluded from matching against
    # the AED bank master entirely. pop_currency defaults to "AED"
    # upstream (pop_row_builder.py / email_log_parser.py) when it
    # cannot be determined, so this only fires on a confirmed
    # mismatch, never on missing data.
    pop_currency = str(pop_row.get("pop_currency") or "AED").strip().upper()
    if pop_currency != "AED":
        candidates = []
        decision = {
            "status": "NO_MATCH",
            "match_reason": f"CURRENCY_MISMATCH:{pop_currency}",
            "selected": None,
            "score": np.nan,
            "score_gap": np.nan,
        }
    else:
        candidates = generate_candidates(pop_row, bank_df)
        candidates = [c for c in candidates if c["bank_row_index"] not in locked_bank_rows]
        decision = decide(candidates)
    selected = decision["selected"]

    case_number = pop_row.get("case_number")

    result = {
        "case_number": case_number,
        "status": decision["status"],
        "match_reason": decision["match_reason"],
        "score": decision["score"],
        "score_gap": decision["score_gap"],
        "candidate_count": len(candidates),

        "pop_amount": pop_row.get("pop_amount"),
        "pop_date": pop_row.get("pop_value_date"),
        "pop_reference": pop_row.get("pop_booking_reference"),
        "pop_customer_reference": pop_row.get("reference_number"),
        "pop_account": pop_row.get("email_bank_account"),
        "pop_customer_name": pop_row.get("email_customer_name"),
        "pop_bank_name": pop_row.get("email_bank_name"),
        "pop_payment_method": pop_row.get("email_payment_method"),
        "pop_source_file": pop_row.get("bank_source_file"),
        "pop_confidence": pop_row.get("overall_confidence"),

        "bank_row_index": selected["bank_row_index"] if selected else np.nan,
        "bank_date": selected["bank_date"] if selected else pd.NaT,
        "bank_value_date": selected["bank_value_date"] if selected else pd.NaT,
        "bank_description": selected["bank_description"] if selected else "",
        "bank_reference": selected["bank_reference"] if selected else "",
        "bank_customer_reference": selected["bank_customer_reference"] if selected else "",
        "bank_transaction_type": selected["bank_transaction_type"] if selected else "",
        "bank_debit_amount": selected["bank_debit_amount"] if selected else np.nan,
        "bank_credit_amount": selected["bank_credit_amount"] if selected else np.nan,
        "bank_balance": selected["bank_balance"] if selected else np.nan,
        "bank_amount": selected["bank_amount"] if selected else np.nan,
        "bank_name": selected["bank_name"] if selected else "",
        "source_file": selected["source_file"] if selected else "",
        "amount_difference": selected["amount_difference"] if selected else np.nan,
        "date_difference": selected["date_difference"] if selected else np.nan,
        "evidence": selected["evidence"] if selected else "",
    }

    if decision["status"] == "MATCHED" and selected is not None:
        locked_bank_rows.add(selected["bank_row_index"])

    return result, candidates, None


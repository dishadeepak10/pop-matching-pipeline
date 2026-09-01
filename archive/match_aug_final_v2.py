from pathlib import Path
import re
from collections import deque

import pandas as pd
import numpy as np


# ============================================================
# AUGUST POP -> BANK FINAL MATCHING ENGINE V6
# ============================================================
#
# OBJECTIVE
# ---------
# MAXIMUM NUMBER OF CORRECT ONE-TO-ONE MATCHES.
#
# HARD EVIDENCE
# -------------
# 1. Exact credit amount
# 2. Correct bank
# 3. Correct account
#
# SUPPORTING EVIDENCE
# -------------------
# 4. Date proximity
# 5. Reference
# 6. Customer/name
#
# IMPORTANT
# ---------
# POP IS THE SOURCE OF TRUTH.
#
# WE NEVER:
# - match to another bank
# - match to another account
# - use debit as POP receipt
# - force a match without hard evidence
#
# GLOBAL ASSIGNMENT
# -----------------
# FIRST:
#     maximize number of valid assignments
#
# THEN:
#     maximize total evidence score
#
# CONSTRAINTS:
#     one POP  -> one bank row
#     one bank -> one POP
#
# ============================================================


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

POP_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "POP_AUG_MASTER.xlsx"
)

BANK_FILE = Path(
    r"D:\AUG-bank_files\normalization_input\normalized_bank_statements.xlsx"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "output"
)

MATCH_OUTPUT = (
    OUTPUT_DIR
    / "POP_AUG_MATCHES_FINAL_V6.xlsx"
)

CANDIDATE_OUTPUT = (
    OUTPUT_DIR
    / "POP_AUG_CANDIDATES_FINAL_V6.xlsx"
)

DIAGNOSTIC_OUTPUT = (
    OUTPUT_DIR
    / "POP_AUG_DIAGNOSTICS_FINAL_V6.xlsx"
)

DATE_WINDOW_DAYS = 14
AMOUNT_TOLERANCE = 0.01

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return ""

    s = str(value).strip()

    if s.lower() in {
        "",
        "nan",
        "nat",
        "none",
        "<na>",
    }:
        return ""

    return s


def norm_text(value):
    s = clean_text(value).upper()
    return re.sub(r"[^A-Z0-9]+", "", s)


def norm_name(value):
    s = clean_text(value).upper()

    s = re.sub(
        r"[^A-Z0-9 ]+",
        " ",
        s,
    )

    s = re.sub(
        r"\s+",
        " ",
        s,
    ).strip()

    return s


def normalize_bank_name(value):
    s = norm_text(value)

    aliases = {
        "FIRSTABUDHABIBANK": "FAB",
        "FAB": "FAB",

        "COMMERCIALBANKOFDUBAI": "CBD",
        "CBD": "CBD",

        "AJMANBANK": "AJMAN",
        "AJMAN": "AJMAN",

        "NATIONALBANKOFRAK": "NBRAK",
        "NATIONALBANKOFRASALKHAIMAH": "NBRAK",
        "NBRAK": "NBRAK",

        "NATIONALBANKOFBAHRAIN": "NBB",
        "NBB": "NBB",

        "ABUDHABIBANK": "ADIB",
        "ADIB": "ADIB",

        "ABCB": "ABC",
        "ADCB": "ADCB",

        "UNITEDARABBANK": "UAB",
        "UAB": "UAB",

        "UNIONNATIONALBANK": "UNB",
        "UNB": "UNB",

        "MASHREQ": "MASHREQ",
        "MASHREQBANK": "MASHREQ",

        "INVESTBANK": "INVESTBANK",

        "ALHILALBANK": "ALHILAL",
        "ALHILAL": "ALHILAL",

        "BANKOFBARODA": "BOB",
        "BOB": "BOB",

        "UNITEDBANKLIMITED": "UBL",
        "UBL": "UBL",

        "ALMARYAHCOMMUNITYBANK": "MASHREQ",
    }

    return aliases.get(
        s,
        s,
    )


def normalize_account(value):
    """
    Normalize account number.

    Leading zeroes are removed.

    Example:

        011181475010
        11181475010

    become:

        11181475010
    """

    s = clean_text(value)

    digits = re.sub(
        r"\D",
        "",
        s,
    )

    if not digits:
        return ""

    digits = digits.lstrip("0")

    return (
        digits
        if digits
        else "0"
    )


def parse_date(value):
    if pd.isna(value):
        return pd.NaT

    try:
        return pd.to_datetime(
            value,
            errors="coerce",
        )
    except Exception:
        return pd.NaT


# ============================================================
# ACCOUNT EXTRACTION
# ============================================================

def extract_account_from_filename(filename):
    """
    Extract the final long numeric component from the
    statement filename.

    Examples:

        FAB-CORPORATE-123101-1031001746692014.xlsx
        -> 1031001746692014

        CBD-GREENZ-ESCROW-123612-1010172243.XLSX
        -> 1010172243

        FAB-BREEZ-ESCROW-123583-4031221746692063.xlsx
        -> 4031221746692063
    """

    name = Path(
        str(filename)
    ).name

    numbers = re.findall(
        r"(?<!\d)(\d{8,20})(?!\d)",
        name,
    )

    if not numbers:
        return ""

    return normalize_account(
        numbers[-1]
    )


def infer_bank_from_filename(filename):
    name = Path(
        str(filename)
    ).name.upper()

    first = re.split(
        r"[-_\s]+",
        name,
    )[0]

    mapping = {
        "FAB": "FAB",
        "CBD": "CBD",
        "ADCB": "ADCB",
        "ADIB": "ADIB",
        "AJMAN": "AJMAN",
        "NBRAK": "NBRAK",
        "NBB": "NBB",
        "UAB": "UAB",
        "UBL": "UBL",
        "MASHREQ": "MASHREQ",
        "ABK": "ABK",
        "INVEST": "INVESTBANK",
    }

    return mapping.get(
        first,
        normalize_bank_name(first),
    )


# ============================================================
# SIMILARITY
# ============================================================

def token_similarity(a, b):

    a = norm_name(a)
    b = norm_name(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    at = set(a.split())
    bt = set(b.split())

    if not at or not bt:
        return 0.0

    intersection = len(
        at & bt
    )

    return (
        2.0 * intersection
        / (len(at) + len(bt))
    )


def substring_similarity(a, b):

    a = norm_text(a)
    b = norm_text(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if len(a) >= 5 and a in b:
        return 0.8

    if len(b) >= 5 and b in a:
        return 0.8

    return 0.0


# ============================================================
# LOAD POP
# ============================================================

def load_pop():

    print()
    print("=" * 110)
    print("LOADING AUGUST POP MASTER")
    print("=" * 110)

    pop = pd.read_excel(
        POP_FILE
    )

    print(
        "POP MASTER rows:",
        len(pop),
    )

    required = [
        "case_number",
        "pop_date",
        "receipt_reference",
        "receipt_amount",
        "bank_name",
        "payment_method",
        "customer_name",
        "bank_account_number",
    ]

    missing = [
        c
        for c in required
        if c not in pop.columns
    ]

    if missing:
        raise ValueError(
            f"POP master missing required columns: {missing}"
        )

    # --------------------------------------------------------
    # STANDARDIZE
    # --------------------------------------------------------

    pop["case_number"] = (
        pop["case_number"]
        .astype(str)
        .str.strip()
    )

    pop["pop_date"] = pd.to_datetime(
        pop["pop_date"],
        errors="coerce",
    )

    pop["pop_amount"] = pd.to_numeric(
        pop["receipt_amount"],
        errors="coerce",
    )

    pop["pop_bank"] = (
        pop["bank_name"]
        .apply(normalize_bank_name)
    )

    pop["pop_account"] = (
        pop["bank_account_number"]
        .apply(normalize_account)
    )

    pop["pop_customer"] = (
        pop["customer_name"]
        .apply(clean_text)
    )

    pop["pop_reference"] = (
        pop["receipt_reference"]
        .apply(clean_text)
    )

    pop["pop_payment_method"] = (
        pop["payment_method"]
        .apply(clean_text)
    )

    # --------------------------------------------------------
    # ONLY VALID POP TRANSACTIONS
    # --------------------------------------------------------

    pop = pop[
        pop["case_number"].ne("")
        & pop["pop_amount"].notna()
    ].copy()

    # One POP case = one transaction.
    pop = (
        pop
        .drop_duplicates(
            subset=["case_number"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    print(
        "VALID POP TRANSACTIONS:",
        len(pop),
    )

    print()
    print("POP BANKS:")

    print(
        pop["pop_bank"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print()
    print("POP DATE RANGE:")

    print(
        pop["pop_date"].min(),
        "to",
        pop["pop_date"].max(),
    )

    return pop


# ============================================================
# LOAD BANK
# ============================================================

def load_bank():

    print()
    print("=" * 110)
    print("LOADING NORMALIZED BANK DATA")
    print("=" * 110)

    bank = pd.read_excel(
        BANK_FILE
    )

    required = [
        "date",
        "value_date",
        "description",
        "reference",
        "customer_reference",
        "debit_amount",
        "credit_amount",
        "balance",
        "bank_name",
        "source_file",
    ]

    missing = [
        c
        for c in required
        if c not in bank.columns
    ]

    if missing:
        raise ValueError(
            f"Bank normalized file missing columns: {missing}"
        )

    # --------------------------------------------------------
    # STANDARDIZE
    # --------------------------------------------------------

    bank["date"] = pd.to_datetime(
        bank["date"],
        errors="coerce",
    )

    bank["value_date"] = pd.to_datetime(
        bank["value_date"],
        errors="coerce",
    )

    bank["credit_amount"] = pd.to_numeric(
        bank["credit_amount"],
        errors="coerce",
    )

    bank["debit_amount"] = pd.to_numeric(
        bank["debit_amount"],
        errors="coerce",
    )

    bank["bank_name_norm"] = (
        bank["bank_name"]
        .apply(normalize_bank_name)
    )

    # --------------------------------------------------------
    # SOURCE FILE = ACCOUNT SOURCE OF TRUTH
    # --------------------------------------------------------

    bank["source_account"] = (
        bank["source_file"]
        .apply(
            extract_account_from_filename
        )
    )

    bank["source_bank"] = (
        bank["source_file"]
        .apply(
            infer_bank_from_filename
        )
    )

    # Prefer actual statement filename.
    bank["effective_bank"] = (
        bank["source_bank"]
    )

    bank.loc[
        bank["effective_bank"].eq(""),
        "effective_bank",
    ] = bank["bank_name_norm"]

    bank["effective_bank"] = (
        bank["effective_bank"]
        .apply(normalize_bank_name)
    )

    # --------------------------------------------------------
    # POP RECEIPTS = CREDIT ONLY
    # --------------------------------------------------------

    bank["bank_amount"] = (
        bank["credit_amount"]
    )

    # Unique physical row identifier.
    bank["bank_row_index"] = np.arange(
        len(bank)
    )

    print(
        "BANK rows:",
        len(bank),
    )

    print(
        "CREDIT rows:",
        int(
            bank["bank_amount"]
            .notna()
            .sum()
        ),
    )

    print()
    print("BANKS:")

    print(
        bank["effective_bank"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print()
    print(
        "UNIQUE SOURCE FILES:",
        bank["source_file"].nunique(),
    )

    # --------------------------------------------------------
    # ACCOUNT VALIDATION
    # --------------------------------------------------------

    print()
    print(
        "ROWS WITH MISSING SOURCE ACCOUNT:",
        int(
            bank["source_account"]
            .eq("")
            .sum()
        ),
    )

    print()
    print("SOURCE ACCOUNT SAMPLE:")

    print(
        bank[
            [
                "effective_bank",
                "source_account",
                "source_file",
            ]
        ]
        .drop_duplicates()
        .head(20)
        .to_string(index=False)
    )

    return bank


# ============================================================
# CANDIDATE GENERATION
# ============================================================

def make_candidates(
    pop,
    bank,
):

    print()
    print("=" * 110)
    print(
        "GENERATING HARD-EVIDENCE CANDIDATES"
    )
    print("=" * 110)

    rows = []
    diagnostics = []

    for _, p in pop.iterrows():

        case = str(
            p["case_number"]
        )

        amount = float(
            p["pop_amount"]
        )

        pop_bank = clean_text(
            p["pop_bank"]
        )

        pop_account = clean_text(
            p["pop_account"]
        )

        pop_date = p["pop_date"]

        # ----------------------------------------------------
        # STEP 1
        # EXACT CREDIT AMOUNT
        # ----------------------------------------------------

        amount_mask = (
            bank["bank_amount"].notna()
            &
            (
                (
                    bank["bank_amount"]
                    - amount
                ).abs()
                <= AMOUNT_TOLERANCE
            )
        )

        amount_rows = bank.loc[
            amount_mask
        ].copy()

        if amount_rows.empty:

            diagnostics.append(
                {
                    "case_number": case,
                    "pop_amount": amount,
                    "pop_bank": pop_bank,
                    "pop_account": pop_account,
                    "diagnostic_status":
                        "NO_EXACT_CREDIT_AMOUNT",
                    "amount_rows": 0,
                    "bank_rows": 0,
                    "account_rows": 0,
                    "date_rows": 0,
                }
            )

            continue

        # ----------------------------------------------------
        # STEP 2
        # CORRECT BANK
        # ----------------------------------------------------

        bank_rows = amount_rows[
            amount_rows[
                "effective_bank"
            ].eq(pop_bank)
        ].copy()

        if bank_rows.empty:

            diagnostics.append(
                {
                    "case_number": case,
                    "pop_amount": amount,
                    "pop_bank": pop_bank,
                    "pop_account": pop_account,
                    "diagnostic_status":
                        "AMOUNT_FOUND_WRONG_BANK",
                    "amount_rows":
                        len(amount_rows),
                    "bank_rows": 0,
                    "account_rows": 0,
                    "date_rows": 0,
                }
            )

            continue

        # ----------------------------------------------------
        # STEP 3
        # CORRECT ACCOUNT
        # ----------------------------------------------------

        if pop_account:

            same_account = bank_rows[
                bank_rows[
                    "source_account"
                ].eq(pop_account)
            ].copy()

        else:

            same_account = pd.DataFrame(
                columns=bank_rows.columns
            )

        if same_account.empty:

            diagnostics.append(
                {
                    "case_number": case,
                    "pop_amount": amount,
                    "pop_bank": pop_bank,
                    "pop_account": pop_account,
                    "diagnostic_status":
                        "AMOUNT_BANK_FOUND_WRONG_ACCOUNT",
                    "amount_rows":
                        len(amount_rows),
                    "bank_rows":
                        len(bank_rows),
                    "account_rows": 0,
                    "date_rows": 0,
                }
            )

            continue

        # ----------------------------------------------------
        # STEP 4
        # DATE SUPPORT
        # ----------------------------------------------------

        if pd.notna(pop_date):

            date_valid = (
                same_account["date"].notna()
                &
                (
                    (
                        same_account["date"]
                        - pop_date
                    ).abs().dt.days
                    <= DATE_WINDOW_DAYS
                )
            )

            date_rows = same_account.loc[
                date_valid
            ].copy()

        else:

            date_rows = same_account.copy()

        # ----------------------------------------------------
        # IMPORTANT
        #
        # DATE IS NOT A HARD REQUIREMENT.
        #
        # If date candidates exist:
        #     use them.
        #
        # If not:
        #     retain hard-evidence candidates.
        # ----------------------------------------------------

        if not date_rows.empty:

            candidate_pool = (
                date_rows.copy()
            )

            date_fallback_used = False

        else:

            candidate_pool = (
                same_account.copy()
            )

            date_fallback_used = True

        # ----------------------------------------------------
        # DIAGNOSTIC
        # ----------------------------------------------------

        diagnostics.append(
            {
                "case_number": case,
                "pop_amount": amount,
                "pop_bank": pop_bank,
                "pop_account": pop_account,
                "diagnostic_status":
                    (
                        "VALID_CANDIDATES_DATE"
                        if not date_fallback_used
                        else
                        "VALID_CANDIDATES_DATE_FALLBACK"
                    ),
                "amount_rows":
                    len(amount_rows),
                "bank_rows":
                    len(bank_rows),
                "account_rows":
                    len(same_account),
                "date_rows":
                    len(date_rows),
            }
        )

        # ----------------------------------------------------
        # SCORE CANDIDATES
        # ----------------------------------------------------

        for _, x in candidate_pool.iterrows():

            bank_date = x["date"]

            # ------------------------------------------------
            # DATE DIFFERENCE
            # ------------------------------------------------

            if (
                pd.notna(pop_date)
                and pd.notna(bank_date)
            ):

                date_diff = abs(
                    (
                        bank_date
                        - pop_date
                    ).days
                )

            else:

                date_diff = 999

            # ------------------------------------------------
            # AMOUNT DIFFERENCE
            # ------------------------------------------------

            amount_diff = abs(
                float(
                    x["bank_amount"]
                )
                - amount
            )

            # ------------------------------------------------
            # SUPPORTING DATE SCORE
            # ------------------------------------------------

            if date_diff == 0:
                date_score = 200

            elif date_diff == 1:
                date_score = 180

            elif date_diff <= 3:
                date_score = 150

            elif date_diff <= 7:
                date_score = 100

            elif date_diff <= DATE_WINDOW_DAYS:
                date_score = 50

            else:
                date_score = 0

            # ------------------------------------------------
            # REFERENCE
            # ------------------------------------------------

            reference = clean_text(
                x["reference"]
            )

            customer_reference = clean_text(
                x["customer_reference"]
            )

            description = clean_text(
                x["description"]
            )

            ref_similarity = max(
                substring_similarity(
                    p["pop_reference"],
                    reference,
                ),
                substring_similarity(
                    p["pop_reference"],
                    customer_reference,
                ),
            )

            # ------------------------------------------------
            # CUSTOMER
            # ------------------------------------------------

            name_similarity = max(
                token_similarity(
                    p["pop_customer"],
                    description,
                ),
                token_similarity(
                    p["pop_customer"],
                    customer_reference,
                ),
            )

            # ------------------------------------------------
            # TOTAL SCORE
            #
            # Hard evidence is already guaranteed by
            # candidate generation.
            #
            # Score is therefore ONLY used to rank
            # competing hard-evidence candidates.
            # ------------------------------------------------

            score = (
                date_score
                + (100 * ref_similarity)
                + (100 * name_similarity)
            )

            # ------------------------------------------------
            # REASONS
            # ------------------------------------------------

            reasons = [
                "EXACT_CREDIT_AMOUNT",
                "BANK_MATCH",
                "ACCOUNT_MATCH",
            ]

            if date_diff == 0:

                reasons.append(
                    "DATE_EXACT"
                )

            elif date_diff <= 3:

                reasons.append(
                    "DATE_CLOSE"
                )

            elif date_diff <= DATE_WINDOW_DAYS:

                reasons.append(
                    "DATE_WITHIN_WINDOW"
                )

            else:

                reasons.append(
                    "DATE_FALLBACK"
                )

            if ref_similarity > 0:

                reasons.append(
                    "REFERENCE_SUPPORT"
                )

            if name_similarity > 0:

                reasons.append(
                    "CUSTOMER_SUPPORT"
                )

            rows.append(
                {
                    "case_number":
                        case,

                    "pop_date":
                        p["pop_date"],

                    "pop_amount":
                        p["pop_amount"],

                    "pop_bank":
                        p["pop_bank"],

                    "pop_account":
                        p["pop_account"],

                    "pop_customer":
                        p["pop_customer"],

                    "pop_reference":
                        p["pop_reference"],

                    "pop_payment_method":
                        p["pop_payment_method"],

                    "bank_amount":
                        x["bank_amount"],

                    "bank_date":
                        x["date"],

                    "bank_value_date":
                        x["value_date"],

                    "bank_name":
                        x["effective_bank"],

                    "bank_account":
                        x["source_account"],

                    "bank_description":
                        x["description"],

                    "bank_reference":
                        x["reference"],

                    "bank_customer_reference":
                        x["customer_reference"],

                    "source_file":
                        x["source_file"],

                    "bank_row_index":
                        int(
                            x["bank_row_index"]
                        ),

                    "amount_difference":
                        amount_diff,

                    "date_difference_days":
                        date_diff,

                    "reference_similarity":
                        ref_similarity,

                    "name_similarity":
                        name_similarity,

                    "score":
                        round(
                            score,
                            4,
                        ),

                    "reasons":
                        "|".join(reasons),
                }
            )

    candidates = pd.DataFrame(
        rows
    )

    diagnostics_df = pd.DataFrame(
        diagnostics
    )

    if candidates.empty:

        raise ValueError(
            "No hard-evidence candidates generated."
        )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    candidates = (
        candidates
        .sort_values(
            [
                "case_number",
                "score",
                "date_difference_days",
                "bank_row_index",
            ],
            ascending=[
                True,
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    candidates["candidate_rank"] = (
        candidates
        .groupby("case_number")
        .cumcount()
        + 1
    )

    print()
    print(
        "CANDIDATES:",
        len(candidates),
    )

    print(
        "CASES WITH CANDIDATES:",
        candidates[
            "case_number"
        ].nunique(),
    )

    return (
        candidates,
        diagnostics_df,
    )


# ============================================================
# GLOBAL MAXIMUM-CARDINALITY + MAXIMUM-SCORE ASSIGNMENT
# ============================================================

def assign_matches(
    pop,
    candidates,
):

    print()
    print("=" * 110)
    print(
        "GLOBAL MAXIMUM-CARDINALITY + MAXIMUM-SCORE ASSIGNMENT"
    )
    print("=" * 110)

    # --------------------------------------------------------
    # POP NODES
    # --------------------------------------------------------

    pop_cases = (
        pop["case_number"]
        .astype(str)
        .tolist()
    )

    # --------------------------------------------------------
    # BANK NODES
    # --------------------------------------------------------

    bank_rows = (
        candidates[
            "bank_row_index"
        ]
        .drop_duplicates()
        .astype(int)
        .tolist()
    )

    pop_index = {
        case: i
        for i, case in enumerate(
            pop_cases
        )
    }

    bank_index = {
        row: i
        for i, row in enumerate(
            bank_rows
        )
    }

    n_pop = len(
        pop_cases
    )

    n_bank = len(
        bank_rows
    )

    # --------------------------------------------------------
    # EDGE LOOKUP
    # --------------------------------------------------------

    edge_lookup = {}

    for _, c in candidates.iterrows():

        case = str(
            c["case_number"]
        )

        bank_row = int(
            c["bank_row_index"]
        )

        edge_lookup[
            (
                pop_index[case],
                bank_index[bank_row],
            )
        ] = c

    # --------------------------------------------------------
    # GRAPH
    # --------------------------------------------------------

    source = 0

    pop_start = 1

    bank_start = (
        pop_start
        + n_pop
    )

    sink = (
        bank_start
        + n_bank
    )

    node_count = sink + 1

    graph = [
        []
        for _ in range(
            node_count
        )
    ]

    def add_edge(
        u,
        v,
        capacity,
        cost,
    ):

        forward = {
            "to": v,
            "rev": len(
                graph[v]
            ),
            "cap": capacity,
            "cost": cost,
        }

        backward = {
            "to": u,
            "rev": len(
                graph[u]
            ),
            "cap": 0,
            "cost": -cost,
        }

        graph[u].append(
            forward
        )

        graph[v].append(
            backward
        )

    # --------------------------------------------------------
    # SOURCE -> POP
    # --------------------------------------------------------

    for i in range(n_pop):

        add_edge(
            source,
            pop_start + i,
            1,
            0,
        )

    # --------------------------------------------------------
    # POP -> BANK
    #
    # NEGATIVE COST = HIGHER SCORE PREFERRED.
    #
    # Add deterministic bank-row tie breaker.
    # --------------------------------------------------------

    for (
        pi,
        bi,
    ), c in edge_lookup.items():

        score_int = int(
            round(
                float(
                    c["score"]
                )
                * 100
            )
        )

        # Score dominates tie-breaking.
        # bank row index is only a tiny deterministic
        # tie breaker.
        tie_break = int(
            c["bank_row_index"]
        ) % 100

        cost = (
            -score_int * 1000
            + tie_break
        )

        add_edge(
            pop_start + pi,
            bank_start + bi,
            1,
            cost,
        )

    # --------------------------------------------------------
    # BANK -> SINK
    # --------------------------------------------------------

    for i in range(n_bank):

        add_edge(
            bank_start + i,
            sink,
            1,
            0,
        )

    # --------------------------------------------------------
    # SUCCESSIVE SHORTEST AUGMENTING PATH
    #
    # Bellman-Ford / SPFA style relaxation.
    #
    # This explicitly allows negative edge costs.
    # --------------------------------------------------------

    flow = 0

    while True:

        INF = 10**30

        dist = [
            INF
            for _ in range(
                node_count
            )
        ]

        prev_node = [
            -1
            for _ in range(
                node_count
            )
        ]

        prev_edge = [
            -1
            for _ in range(
                node_count
            )
        ]

        dist[source] = 0

        queue = deque(
            [source]
        )

        in_queue = {
            source
        }

        while queue:

            u = queue.popleft()

            in_queue.discard(
                u
            )

            for ei, e in enumerate(
                graph[u]
            ):

                if e["cap"] <= 0:
                    continue

                v = e["to"]

                nd = (
                    dist[u]
                    + e["cost"]
                )

                if nd < dist[v]:

                    dist[v] = nd

                    prev_node[v] = u

                    prev_edge[v] = ei

                    if (
                        v
                        not in in_queue
                    ):

                        queue.append(
                            v
                        )

                        in_queue.add(
                            v
                        )

        # ----------------------------------------------------
        # NO MORE AUGMENTING PATH
        # ----------------------------------------------------

        if dist[sink] == INF:
            break

        # ----------------------------------------------------
        # AUGMENT ONE UNIT
        # ----------------------------------------------------

        v = sink

        while v != source:

            u = prev_node[v]

            ei = prev_edge[v]

            e = graph[u][ei]

            e["cap"] -= 1

            rev = e["rev"]

            graph[v][rev]["cap"] += 1

            v = u

        flow += 1

    print()
    print(
        "GLOBAL MATCHES:",
        flow,
    )

    print(
        "POP CASES:",
        len(pop),
    )

    print(
        "UNMATCHED POP CASES:",
        len(pop) - flow,
    )

    # --------------------------------------------------------
    # RECOVER SELECTED MATCHES
    # --------------------------------------------------------

    selected = {}

    for pi, case in enumerate(
        pop_cases
    ):

        node = (
            pop_start
            + pi
        )

        for e in graph[node]:

            if not (
                bank_start
                <= e["to"]
                < bank_start + n_bank
            ):
                continue

            # Forward edge originally had capacity 1.
            #
            # If current capacity is 0,
            # that edge carries the final flow.

            if e["cap"] == 0:

                bi = (
                    e["to"]
                    - bank_start
                )

                selected[case] = (
                    edge_lookup[
                        (
                            pi,
                            bi,
                        )
                    ]
                )

                break

    # --------------------------------------------------------
    # BUILD FINAL RESULTS
    # --------------------------------------------------------

    results = []

    for _, p in pop.iterrows():

        case = str(
            p["case_number"]
        )

        group = (
            candidates[
                candidates[
                    "case_number"
                ]
                .astype(str)
                .eq(case)
            ]
            .sort_values(
                [
                    "score",
                    "date_difference_days",
                    "bank_row_index",
                ],
                ascending=[
                    False,
                    True,
                    True,
                ],
            )
        )

        # ----------------------------------------------------
        # NO GLOBAL MATCH
        # ----------------------------------------------------

        if case not in selected:

            # Determine whether candidates existed but
            # were consumed by other POP cases.

            if group.empty:

                reason = (
                    "No exact credit amount + bank + "
                    "account candidate"
                )

            else:

                reason = (
                    "Hard-evidence candidates existed, "
                    "but all available bank rows were "
                    "allocated to other POP cases by "
                    "global one-to-one assignment"
                )

            results.append(
                {
                    "case_number":
                        case,

                    "status":
                        "NO_MATCH",

                    "match_reason":
                        reason,

                    "pop_date":
                        p["pop_date"],

                    "pop_amount":
                        p["pop_amount"],

                    "pop_bank":
                        p["pop_bank"],

                    "pop_account":
                        p["pop_account"],

                    "pop_customer":
                        p["pop_customer"],

                    "pop_reference":
                        p["pop_reference"],

                    "bank_date":
                        pd.NaT,

                    "bank_value_date":
                        pd.NaT,

                    "bank_amount":
                        np.nan,

                    "bank_name":
                        "",

                    "bank_account":
                        "",

                    "bank_reference":
                        "",

                    "bank_customer_reference":
                        "",

                    "bank_description":
                        "",

                    "source_file":
                        "",

                    "bank_row_index":
                        np.nan,

                    "score":
                        np.nan,

                    "date_difference_days":
                        np.nan,

                    "candidate_count":
                        len(group),
                }
            )

            continue

        # ----------------------------------------------------
        # SELECTED
        # ----------------------------------------------------

        chosen = selected[
            case
        ]

        alternatives = group[
            group[
                "bank_row_index"
            ]
            != chosen[
                "bank_row_index"
            ]
        ].copy()

        ambiguous = False

        chosen_date_diff = float(
            chosen[
                "date_difference_days"
            ]
        )

        # ----------------------------------------------------
        # CHECK ALTERNATIVE CANDIDATES
        # ----------------------------------------------------

        if not alternatives.empty:

            second = alternatives.iloc[0]

            score_gap = (
                float(
                    chosen["score"]
                )
                -
                float(
                    second["score"]
                )
            )

            # Very close supporting evidence.
            if score_gap < 50:

                ambiguous = True

        # ----------------------------------------------------
        # DATE FALLBACK
        # ----------------------------------------------------

        if (
            chosen_date_diff
            > DATE_WINDOW_DAYS
        ):

            ambiguous = True

        # ----------------------------------------------------
        # VERY CLOSE DATES
        # ----------------------------------------------------

        if (
            len(group) > 1
            and not alternatives.empty
        ):

            second_date = float(
                alternatives.iloc[0][
                    "date_difference_days"
                ]
            )

            if (
                abs(
                    chosen_date_diff
                    - second_date
                )
                <= 1
            ):

                ambiguous = True

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if ambiguous:

            status = "AMBIGUOUS"

            reason = (
                "Exact credit amount + bank + account "
                "assigned globally, but supporting "
                "evidence has a close alternative or "
                "date fallback"
            )

        else:

            status = "MATCHED"

            reason = (
                "Exact credit amount + bank + account "
                "selected by maximum-cardinality "
                "global one-to-one assignment"
            )

        results.append(
            {
                "case_number":
                    case,

                "status":
                    status,

                "match_reason":
                    reason,

                "pop_date":
                    p["pop_date"],

                "pop_amount":
                    p["pop_amount"],

                "pop_bank":
                    p["pop_bank"],

                "pop_account":
                    p["pop_account"],

                "pop_customer":
                    p["pop_customer"],

                "pop_reference":
                    p["pop_reference"],

                "bank_date":
                    chosen["bank_date"],

                "bank_value_date":
                    chosen[
                        "bank_value_date"
                    ],

                "bank_amount":
                    chosen[
                        "bank_amount"
                    ],

                "bank_name":
                    chosen[
                        "bank_name"
                    ],

                "bank_account":
                    chosen[
                        "bank_account"
                    ],

                "bank_reference":
                    chosen[
                        "bank_reference"
                    ],

                "bank_customer_reference":
                    chosen[
                        "bank_customer_reference"
                    ],

                "bank_description":
                    chosen[
                        "bank_description"
                    ],

                "source_file":
                    chosen[
                        "source_file"
                    ],

                "bank_row_index":
                    chosen[
                        "bank_row_index"
                    ],

                "score":
                    chosen["score"],

                "date_difference_days":
                    chosen[
                        "date_difference_days"
                    ],

                "candidate_count":
                    len(group),
            }
        )

    return pd.DataFrame(
        results
    )


# ============================================================
# MARK SELECTED CANDIDATES
# ============================================================

def mark_selected_candidates(
    candidates,
    results,
):

    selected_map = {}

    for _, r in results.iterrows():

        if (
            r["status"]
            in {
                "MATCHED",
                "AMBIGUOUS",
            }
            and pd.notna(
                r["bank_row_index"]
            )
        ):

            selected_map[
                (
                    str(
                        r["case_number"]
                    ),
                    int(
                        r["bank_row_index"]
                    ),
                )
            ] = r["status"]

    candidates = (
        candidates.copy()
    )

    candidates[
        "selected_status"
    ] = ""

    for idx, row in candidates.iterrows():

        key = (
            str(
                row["case_number"]
            ),
            int(
                row["bank_row_index"]
            ),
        )

        if key in selected_map:

            candidates.at[
                idx,
                "selected_status",
            ] = selected_map[key]

    return candidates


# ============================================================
# FINAL VALIDATION
# ============================================================

def validate_final_results(
    results,
):

    assigned = results[
        results["status"].isin(
            [
                "MATCHED",
                "AMBIGUOUS",
            ]
        )
    ].copy()

    print()
    print("=" * 110)
    print("FINAL ONE-TO-ONE VALIDATION")
    print("=" * 110)

    # --------------------------------------------------------
    # POP UNIQUENESS
    # --------------------------------------------------------

    duplicate_pop = (
        assigned["case_number"]
        .duplicated()
        .sum()
    )

    # --------------------------------------------------------
    # BANK UNIQUENESS
    # --------------------------------------------------------

    duplicate_bank = (
        assigned["bank_row_index"]
        .duplicated()
        .sum()
    )

    print(
        "DUPLICATE POP ASSIGNMENTS:",
        duplicate_pop,
    )

    print(
        "DUPLICATE BANK ROW ASSIGNMENTS:",
        duplicate_bank,
    )

    if duplicate_pop != 0:

        raise ValueError(
            "FINAL VALIDATION FAILED: "
            "duplicate POP assignments detected."
        )

    if duplicate_bank != 0:

        raise ValueError(
            "FINAL VALIDATION FAILED: "
            "same bank row assigned to multiple POP cases."
        )

    print(
        "ONE-TO-ONE VALIDATION: PASS"
    )

    # --------------------------------------------------------
    # HARD EVIDENCE VALIDATION
    # --------------------------------------------------------

    invalid_amount = (
        (
            assigned["pop_amount"]
            - assigned["bank_amount"]
        ).abs()
        > AMOUNT_TOLERANCE
    ).sum()

    invalid_bank = (
        assigned["pop_bank"]
        != assigned["bank_name"]
    ).sum()

    invalid_account = (
        assigned["pop_account"]
        != assigned["bank_account"]
    ).sum()

    print(
        "INVALID AMOUNT MATCHES:",
        invalid_amount,
    )

    print(
        "INVALID BANK MATCHES:",
        invalid_bank,
    )

    print(
        "INVALID ACCOUNT MATCHES:",
        invalid_account,
    )

    if invalid_amount != 0:
        raise ValueError(
            "FINAL VALIDATION FAILED: "
            "invalid amount assignment."
        )

    if invalid_bank != 0:
        raise ValueError(
            "FINAL VALIDATION FAILED: "
            "invalid bank assignment."
        )

    if invalid_account != 0:
        raise ValueError(
            "FINAL VALIDATION FAILED: "
            "invalid account assignment."
        )

    print(
        "HARD-EVIDENCE VALIDATION: PASS"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 110)
    print(
        "AUGUST POP -> BANK FINAL MATCHING ENGINE V6"
    )
    print("=" * 110)

    print()
    print("POP MASTER:")
    print(POP_FILE)

    print()
    print("BANK:")
    print(BANK_FILE)

    if not POP_FILE.exists():

        raise FileNotFoundError(
            f"POP file not found:\n{POP_FILE}"
        )

    if not BANK_FILE.exists():

        raise FileNotFoundError(
            f"Bank file not found:\n{BANK_FILE}"
        )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    pop = load_pop()

    bank = load_bank()

    # --------------------------------------------------------
    # CANDIDATES
    # --------------------------------------------------------

    (
        candidates,
        diagnostics,
    ) = make_candidates(
        pop,
        bank,
    )

    # --------------------------------------------------------
    # GLOBAL ASSIGNMENT
    # --------------------------------------------------------

    results = assign_matches(
        pop,
        candidates,
    )

    # --------------------------------------------------------
    # MARK SELECTED
    # --------------------------------------------------------

    candidates = (
        mark_selected_candidates(
            candidates,
            results,
        )
    )

    # --------------------------------------------------------
    # FINAL VALIDATION
    # --------------------------------------------------------

    validate_final_results(
        results
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    results = (
        results
        .sort_values(
            "case_number"
        )
        .reset_index(
            drop=True
        )
    )

    candidates = (
        candidates
        .sort_values(
            [
                "case_number",
                "score",
                "date_difference_days",
            ],
            ascending=[
                True,
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    if not diagnostics.empty:

        diagnostics = (
            diagnostics
            .sort_values(
                "case_number"
            )
            .reset_index(
                drop=True
            )
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    results.to_excel(
        MATCH_OUTPUT,
        index=False,
    )

    candidates.to_excel(
        CANDIDATE_OUTPUT,
        index=False,
    )

    diagnostics.to_excel(
        DIAGNOSTIC_OUTPUT,
        index=False,
    )

    # --------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print(
        "FINAL AUGUST MATCHING RESULT"
    )
    print("=" * 110)

    print()
    print(
        "POP CASES:",
        len(results),
    )

    print()
    print("STATUS:")

    print(
        results["status"]
        .value_counts()
        .to_string()
    )

    assigned = results[
        results["status"].isin(
            [
                "MATCHED",
                "AMBIGUOUS",
            ]
        )
    ]

    no_match = results[
        results["status"].eq(
            "NO_MATCH"
        )
    ]

    print()
    print(
        "TOTAL VALID GLOBAL ASSIGNMENTS:",
        len(assigned),
    )

    print(
        "TOTAL UNMATCHED:",
        len(no_match),
    )

    # --------------------------------------------------------
    # DIAGNOSTIC STATUS
    # --------------------------------------------------------

    print()
    print(
        "DIAGNOSTIC STATUS:"
    )

    if not diagnostics.empty:

        print(
            diagnostics[
                "diagnostic_status"
            ]
            .value_counts()
            .to_string()
        )

    # --------------------------------------------------------
    # ALL ASSIGNED
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print(
        "ALL GLOBALLY ASSIGNED MATCHES"
    )
    print("=" * 110)

    if assigned.empty:

        print(
            "NO GLOBAL ASSIGNMENTS"
        )

    else:

        print(
            assigned[
                [
                    "case_number",
                    "status",
                    "pop_date",
                    "pop_amount",
                    "pop_bank",
                    "pop_account",
                    "bank_date",
                    "bank_amount",
                    "bank_name",
                    "bank_account",
                    "source_file",
                    "date_difference_days",
                    "candidate_count",
                    "score",
                ]
            ]
            .to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # NO MATCH
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print(
        "NO MATCH CASES"
    )
    print("=" * 110)

    if no_match.empty:

        print(
            "NONE"
        )

    else:

        print(
            no_match[
                [
                    "case_number",
                    "pop_date",
                    "pop_amount",
                    "pop_bank",
                    "pop_account",
                    "candidate_count",
                    "match_reason",
                ]
            ]
            .to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # OUTPUTS
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print(
        "OUTPUT FILES"
    )
    print("=" * 110)

    print(
        MATCH_OUTPUT
    )

    print(
        CANDIDATE_OUTPUT
    )

    print(
        DIAGNOSTIC_OUTPUT
    )

    print()
    print("=" * 110)
    print("DONE.")
    print("=" * 110)


if __name__ == "__main__":
    main()
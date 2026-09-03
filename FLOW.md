# POP Matching Pipeline — Flow Map

Quick reference for the full execution order across all three projects.
Read top to bottom for a single POP's journey from input to dashboard.

---

## Entry point: run.py

    python run.py <pop-file-path OR case-number> [--month JUL|AUG] [--bank-master <path>]

1. E1 — Subscription check (subscription_client.check_subscription())
   Calls Project 2's GET /subscription/check (dual auth: x-subs-key +
   x-client-name). Fails closed — aborts immediately if inactive or
   unreachable.

2. Auto-routing — is the target an existing file path, or a case number?
   - File path exists -> routes to run_pipeline.py --file <path>
     (document/OCR-sourced path, July-style)
   - Not a file (treated as a case number) -> routes to
     run_pipeline_email_source.py --case <number>
     (email-log-sourced path, August-style)

3. Bank master month — explicit --month/--bank-master wins; otherwise
   auto-detected from today's calendar month (MONTH_KEY_BY_NUMBER in
   run.py). Resolved for real via config.resolve_bank_master() —
   never guessed, hard failure if ambiguous.

---

## Path A — Document/OCR-sourced (run_pipeline.py)

Used for July-style POPs where a raw document/image exists.

    extraction (src/main.py, Azure Document Intelligence + GPT-4o-mini, legacy/untouched)
      -> build_pop_row()        [src/pop_row_builder.py]
      -> is_case_already_processed()  [src/storage.py]  - skip if true
      -> append_pop_row()        [src/storage.py]
      -> match_one_pop()         [src/matching.py]
      -> append_match_result()   [src/storage.py]
      -> append_candidate_audit()[src/storage.py]  (diagnostic)
      -> log_result()             [subscription_client.py]  - E2, POST /results

Currently off-limits per mentor: July bank master is ~48.6% contaminated.
Do not run July cases against real data without mentor sign-off.

---

## Path B — Email-log-sourced (run_pipeline_email_source.py)

Used for the 90 August cases with no raw document — only a Salesforce
case-notification email.

    load_email_log_rows() / parse_email_row()  [src/email_log_parser.py]
      -> is_case_already_processed()  [src/storage.py]  - skip if true
      -> append_pop_row()              [src/storage.py]
      -> match_one_pop()               [src/matching.py]
      -> append_match_result()         [src/storage.py]
      -> append_candidate_audit()      [src/storage.py]  (diagnostic)
      -> log_result()                   [subscription_client.py]  - E2, POST /results

No confidence_score is structurally possible here (no OCR step) — this
is expected, not a bug.

---

## matching.py — the core matching engine

Fixed hierarchy (mentor-mandated, do not redesign):

    generate_candidates(pop, bank_df)
      Stage 1 - identify relevant bank rows:
        Priority 1: bank_source_file (if present)
        Priority 2: account number match
        Priority 3: bank name match (only counts if amount also matches inside it)
        Priority 4: full bank master (last resort, only if a POP date exists)
      Stage 2 - amount filter (exact match first, then +/-5.00 near-match fallback)
      Stage 3 - field + date scoring -> sorted candidate list

    decide(candidates)
      -> MATCHED / AMBIGUOUS / NO_MATCH / NEAR_AMOUNT

Currency gate happens in match_one_pop() before any of the above:
non-AED (confirmed) POPs are excluded from matching entirely — no
conversion is ever performed.

---

## Project 2 — pop_subscription_service (what receives E1/E2 calls)

    GET  /subscription/check   <- E1, called once at run.py startup
    POST /results               <- E2, called once per POP actually processed
    GET  /results                (client-scoped, used by dashboards/audits)
    GET  /analytics/summary
    GET  /dashboard

All writes land in the single results table in pop_subscription_db.

---

## Project 3 — pop_analytics (Streamlit dashboard)

Reads the same results table directly (read-only, no API call).
Sidebar filters: Client, Month (friendly labels), Status, minimum
confidence % (with an "include unscored" toggle for email-sourced rows
that structurally have no confidence_score).

---

## Demo order

1. Start Project 2 (uvicorn, port 8000) and Project 3 (streamlit, port 8501)
   in separate terminal windows.
2. Run one or two real cases through run.py --case <number> --month AUG.
3. Refresh the dashboard, show the new row + filters in action.

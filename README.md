# POP Matching Pipeline

An automated pipeline that matches Proof-of-Payment (POP) documents against
bank statement records for reconciliation, using OCR + LLM-assisted
extraction and a deterministic, evidence-based matching engine. Packaged as
a standalone Windows executable for client deployment.

## What it does

1. **Extraction**: Each POP document is processed via Azure Document
   Intelligence (OCR) and Azure OpenAI (structured field extraction) to pull
   out fields like amount, reference, customer name, and bank account.
2. **Normalization**: Extracted fields are cleaned and normalized in memory
   (dates parsed deterministically — never by the LLM — amounts validated,
   currency checked).
3. **Matching**: Each normalized POP is matched against a pre-normalized
   bank statement master using a fixed evidence hierarchy:
   1. Account / source-file match
   2. Reference / field match
   3. Date match
   Matching is fully rule-based and auditable — every decision carries a
   machine-readable reason code. `AMBIGUOUS` and `NO_MATCH` are legitimate,
   correct outcomes; the engine never forces a match without sufficient
   evidence, and each bank row can only be matched to one POP
   (one-to-one locking).
4. **Output**: Matched results and items needing manual review are written
   to consolidated output files (`pop_matched_results.csv`,
   `pop_review_queue.csv`), plus a separate log for anything that failed to
   process.

The whole pipeline is idempotent — reprocessing an already-matched POP
(by `case_number`) is automatically skipped rather than duplicated.

## Architecture

- `run.py` — main entry point; auto-detects input type and routes to the
  correct internal pipeline.
- `src/main.py` — OCR + LLM extraction.
- `src/pop_row_builder.py` — flattens raw extraction output into the
  matching schema.
- `src/matching.py` — the deterministic matching engine (candidate
  generation, scoring, decision logic).
- `src/storage.py` — schema-safe output writing (matched results, review
  queue, failed POPs).
- `src/email_log_parser.py` — alternate POP source: parses POP metadata
  from an email log instead of raw documents.
- `normalize_bank_statements.py` — normalizes raw bank statement exports
  into a consistent schema, per bank, per month. Run separately/upstream of
  the matching pipeline; output is reused across many pipeline runs.
- `archive/` — historical diagnostic and one-off scripts kept for
  reference; not part of the active pipeline.

## Setup

1. Create a virtual environment and install dependencies:
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
2. Copy .env.example to .env and fill in your own Azure Document
   Intelligence and Azure OpenAI credentials.
3. Normalize bank statements for the month(s) you need (produces a bank
   master file reused by the matching pipeline):
   python normalize_bank_statements.py
4. Run the pipeline against a POP source:
   python run.py --file path-to-pop-document --month AUG

## Sample data

`sample_data/` contains fully synthetic POP and bank statement rows (fake
names, amounts, and references) for demonstration purposes only — no real
client data is included in this repository. Run the pipeline against
`sample_data/sample_pop_input.csv` and `sample_data/demo_bank_statement.csv`
to see the matching engine produce real MATCHED output end-to-end.

## Notes

- This repository excludes all real client data, bank statements, and
  credentials (see `.gitignore` / `.env.example`). Real production data for
  this pipeline is stored separately and is never committed here.
- The matching hierarchy (account → reference → date) is intentionally
  fixed and evidence-based per project requirements — it is not a
  configurable scoring/confidence-tier system.


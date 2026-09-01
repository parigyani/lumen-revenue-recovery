# Lumen Skincare - AI Revenue Recovery Agent
**(Razorpay AI Buildathon, Track 03)**

## Overview
An intelligent revenue recovery engine that uses AI exclusively for diagnosing the reason behind cart abandonment, while strictly relying on deterministic Python logic for all execution, routing, and decision-making. 

## Architecture
- `agent.py`: Interfaces with the Gemini API to classify checkouts and implements rate-limit backoff.
- `app.py`: Streamlit dashboard offering a live demo, batch report viewer, and audit trail.
- `audit.py`: Handles immutable logging of all system actions and decisions to `audit_log.json`.
- `batch_runner.py`: Executes the recovery pipeline across all checkouts and generates `batch_report.json`.
- `checkouts.py`: Manages data loading and live-recheck eligibility rules.
- `recovery.py`: Executes interventions, simulates probabilistic outcomes, and enforces stopping rules under a `FileLock`.
- `data/generate_checkouts.py`: Seed script that generates 60 synthetic abandoned checkouts.

## What's Real vs Simulated
*   **Real**: 
    *   AI diagnosis and classification with guardrails (Real API calls via Gemini; model configurable via `GEMINI_MODEL` in `.env`; verified batch run used `gemini-3.6-flash` after `gemini-2.5-flash` and `gemini-3.5-flash` quotas were exhausted on the same project).
    *   Eligibility gating and the critical "live re-check".
    *   Stopping rules (max attempts, cooldowns).
    *   Audit trail generation.
    *   Integration with Razorpay SDK (if credentials provided).
*   **Simulated**:
    *   Message dispatch is simulated via probabilities.
    *   Payment links fall back to dummy URLs if no Razorpay credentials are provided.

## Setup & How to Run
1. `pip install -r requirements.txt`
2. `python3 data/generate_checkouts.py`
3. `python3 batch_runner.py`
4. `streamlit run app.py`

## Testing & Verification
*   `test_double_recovery.py`: Sequential stale-state guard testing.
*   `test_concurrent_recovery.py`: True multi-threaded concurrent execution guard using `FileLock`.
*   `scripts/test_idempotency.py`: Batch idempotency / double-run safety.
*   `scripts/test_malformed_output.py`: Malformed AI-output resilience across 7 edge cases.
*   `scripts/score_accuracy.py`: Ground-truth classification accuracy scoring.
*   `scripts/stress_test.py`: Sequential and concurrent scale/stress testing.

## Why the Stale-State Guard Matters
If a customer pays elsewhere while the AI is diagnosing their case, sending a late payment link damages brand trust. We purposefully seed `already_completed_elsewhere=true` cases and test it using two scripts:
1. `python3 test_double_recovery.py`: Tests sequential stale-state guarding.
2. `python3 test_concurrent_recovery.py`: Tests true multi-threaded concurrency using `FileLock`.

## Known Limitations
*   Google's free-tier quota (~20 requests/day) applies per model per project — different Gemini model variants (e.g. 2.5-flash, 3.5-flash, 3.6-flash) have independent quotas. Due to this hard constraint, running a full 60-record batch requires a paid tier for 100% AI coverage, or else it falls back to the deterministic baseline rule-set.
*   JSON-file storage has no real concurrent write safety at scale (though `filelock` mitigates this for testing).
*   Classification accuracy was validated against a hand-labeled ground-truth set: baseline rule-based classifier achieves ~83-85% accuracy, with a consistent, explainable error pattern (misclassifying ambiguous cases as price_hesitation instead of correctly flagging them as unknown/escalate). See `scripts/score_accuracy.py`. AI-vs-ground-truth accuracy could not be reliably measured in a single stable batch due to a dataset/cache ordering issue discovered during testing (see commit history) — the diagnosis cache must be generated in the same run as the dataset it scores against, not regenerated independently. This is now guarded against in batch_runner.py.
*   Message dispatch and payment completion outcomes are mathematically simulated, meaning recovery numbers are runtime-dependent.

### Scale Testing
*   **Empirical Throughput**: Measured via `scripts/stress_test.py`:
    *   100 records: 2.87s total wall-clock time (28.72ms/record, 26.75ms FileLock hold time, 64.2 KB dataset size).
    *   500 records: 17.94s total wall-clock time (35.88ms/record, 34.69ms FileLock hold time, 321.8 KB dataset size).
    *   1000 records: 55.15s total wall-clock time (55.15ms/record, 54.12ms FileLock hold time, 316.6 KB dataset size).
*   **Concurrent Contention**: 10 worker threads processing 1000 records completed in 41.63s with zero data corruption. While multithreading speeds up CPU-bound diagnosis prep, global FileLock serialization means I/O-bound state mutations remain sequential.
*   **Scale Limitation**: Beyond ~500–1000 records, the "read entire file, rewrite entire file" pattern under a global FileLock becomes bottlenecked by $O(N^2)$ cumulative I/O byte rewrites. Production deployment at higher scale requires a relational database (e.g., PostgreSQL) with row-level locking.

## Latest Batch Run Results
*   **AI Calls Succeeded**: 5 real Gemini 3.6 Flash calls (Token usage: 1,669 input / 322 output, Cost: ₹0.0184).
*   **Fallback Rate**: 55 / 60 checkouts (91.67% quota reserved).
*   **Real AI vs Baseline Agreement**: 40.0% (AI disagreed on 3 checkouts where cart value / tier signaled alternative diagnosis).
*   **Total At-Risk Value**: ₹281,878.11
*   **Recovered Value**: ₹65,756.11 (Recovery Rate: 23.33%)
*   **Escalated to Human**: 8 checkouts

Run `python3 batch_runner.py` to re-generate metrics — see `batch_report.json` and `batch_report_VERIFIED_REAL.json`.

## Architecture Extension: B2B Receivables
This extension validates that the core diagnose→execute→audit architecture seamlessly generalizes beyond abandoned checkouts to the brief's "overdue receivables" and "promise-to-pay tracker" directions. It reuses the exact same PII-stripping pattern (`business_id` omitted), confidence-threshold guardrails (< 0.55 escalates to human), FileLock concurrency safety (`receivables.json.lock`), and append-only audit trail logging. The receivables scenario adds a domain-specific stopping rule: automatically halting automated contacts and escalating to human review if 2+ broken promises are recorded in an invoice's history.

Ground-truth accuracy evaluation (`scripts/score_accuracy.py`) demonstrates that the B2B receivables baseline classifier achieves 66.7% accuracy (10/15), exhibiting the same structural limitation as checkouts (inability to output `unknown` on ambiguous scenarios) alongside threshold misclassifications on early-stage disputes.

import json

def generate_readme():
    with open("batch_report.json", "r") as f:
        report = json.load(f)

    readme_content = f"""# Lumen Skincare - AI Revenue Recovery Agent
**(Razorpay AI Buildathon, Track 03)**

## Overview
An intelligent revenue recovery engine that uses AI for diagnosis and deterministic Python logic for safe execution. 

### What's Real vs Simulated
*   **Real**: 
    *   AI diagnosis and classification with guardrails (Real API Calls via `gemini-2.5-flash`).
    *   Eligibility gating and the critical "live re-check".
    *   Stopping rules (max attempts, cooldowns).
    *   Audit trail generation.
    *   Integration with Razorpay SDK.
*   **Simulated**:
    *   Message dispatch is simulated via probabilities.
    *   Payment links fall back to dummy URLs if no Razorpay credentials are provided.

## Performance Metrics (Latest Batch Run)
*   **AI vs Fallback**: {report.get('ai_calls_succeeded', 0)} real Gemini API calls, {report.get('ai_calls_fell_back', 0)} fallbacks used (Fallback Rate: {report.get('fallback_rate_pct', 0)}%).
*   **Recovery Rate Variance (5 Runs):** Min {report.get('recovery_rate_pct_min', 0)}% | Max {report.get('recovery_rate_pct_max', 0)}% | Mean {report.get('recovery_rate_pct_mean', 0)}%
*   **AI Cost / ROI Ratio:** ₹{report.get('recovered_value', 0)} recovered per ₹{report.get('total_ai_diagnosis_cost_inr', 0)} spent (Ratio: {report.get('recovered_value_to_ai_cost_ratio', 0)}).
*   **Baseline vs AI Comparison**: {report.get('real_ai_agreement_pct', 0)}% agreement among REAL AI calls.

## Why the Stale-State Guard Matters
If a customer pays elsewhere while the AI is diagnosing their case, sending a late payment link damages brand trust. We purposefully seed `already_completed_elsewhere=true` cases and test it using two scripts:
1. `python test_double_recovery.py`: Tests sequential stale-state guarding.
2. `python test_concurrent_recovery.py`: Tests true multi-threaded concurrency using `FileLock`.

## Known Limitations
Gemini free-tier quota limits real AI diagnosis to ~18-20 calls/day per key. This batch run used real Gemini 2.5 Flash calls for the first N checkouts (quota-capped by design, not by failure) and deterministic baseline classification for the remainder, so the full 60-record batch report reflects complete deterministic execution/eligibility/stopping-rules/audit logic at full scale, with AI diagnosis verified on a real sample within free-tier limits. Production deployment would use a paid tier for full-batch AI coverage.

*   JSON-file storage has no real concurrent write safety at scale (though `filelock` mitigates this for testing).
*   Classification accuracy has no ground-truth validation set.
*   Message dispatch and payment completion are simulated.

## Setup
1. `pip install -r requirements.txt`
2. `python data/generate_checkouts.py`
3. `streamlit run app.py`
"""

    with open("README.md", "w") as f:
        f.write(readme_content)

if __name__ == "__main__":
    generate_readme()

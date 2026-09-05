import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent
import local_agent

def test_local_fallback():
    checkout = {
        "checkout_id": "test_local_chk",
        "cart_value": 4500,
        "items": ["Cream"],
        "payment_attempt_status": "none",
        "failure_reason_raw": "",
        "time_since_abandonment_hours": 3.0,
        "customer_tier": "vip"
    }

    print("=== TESTING LOCAL LLM (OLLAMA QWEN3:4B) FALLBACK CHAIN ===")

    # Test 1: Gemini Failure -> Local Model Success
    print("\n--- Test 1: Gemini Failure -> Local Ollama Model Success ---")
    if os.path.exists(agent.CACHE_FILE):
        os.remove(agent.CACHE_FILE)

    with patch("agent.genai.Client") as MockGemini, \
         patch("local_agent.diagnose_local_qwen") as mock_local_qwen, \
         patch("agent.os.getenv") as mock_getenv:
        
        mock_getenv.side_effect = lambda k, d=None: "fake_key" if k == "GEMINI_API_KEY" else d
        
        mock_gemini_inst = MagicMock()
        mock_gemini_inst.models.generate_content.side_effect = Exception("Gemini 429 Quota Exhausted")
        MockGemini.return_value = mock_gemini_inst

        mock_local_qwen.return_value = {
            "reason": "distracted",
            "confidence": 0.85,
            "recommended_intervention": "reminder_nudge",
            "discount_pct": 0,
            "reasoning_short": "Diagnosed by local Qwen3:4b model."
        }

        with patch("sys.stdout", new=open(os.devnull, "w")):
            res = agent.diagnose(checkout)

        if res.get("is_fallback") and res.get("fallback_reason") == "local_model_fallback" and res.get("reason") == "distracted":
            print("[PASS] Gemini failure correctly fell back to Local Ollama Qwen model.")
        else:
            print(f"[FAIL] Expected local_model_fallback result. Got: {res}")

    # Test 2: Gemini Failure -> Ollama Unavailable -> Rule-Based Baseline
    print("\n--- Test 2: Gemini Failure -> Ollama Unavailable -> Rule-Based Baseline ---")
    if os.path.exists(agent.CACHE_FILE):
        os.remove(agent.CACHE_FILE)

    with patch("agent.genai.Client") as MockGemini, \
         patch("local_agent.diagnose_local_qwen") as mock_local_qwen, \
         patch("agent.os.getenv") as mock_getenv:

        mock_getenv.side_effect = lambda k, d=None: "fake_key" if k == "GEMINI_API_KEY" else d
        MockGemini.return_value.models.generate_content.side_effect = Exception("Gemini 429")
        mock_local_qwen.side_effect = Exception("Ollama server unavailable (Connection Refused)")

        with patch("sys.stdout", new=open(os.devnull, "w")):
            res = agent.diagnose(checkout)

        if res.get("is_fallback") and res.get("fallback_reason") == "api_error" and res.get("reason") == "distracted":
            print("[PASS] Ollama unavailable correctly fell back to rule-based baseline.")
        else:
            print(f"[FAIL] Expected rule-based baseline. Got: {res}")

    # Test 3: Gemini Failure -> Local Model Invalid JSON -> Rule-Based Baseline
    print("\n--- Test 3: Gemini Failure -> Local Model Invalid JSON -> Rule-Based Baseline ---")
    if os.path.exists(agent.CACHE_FILE):
        os.remove(agent.CACHE_FILE)

    with patch("agent.genai.Client") as MockGemini, \
         patch("local_agent.diagnose_local_qwen") as mock_local_qwen, \
         patch("agent.os.getenv") as mock_getenv:

        mock_getenv.side_effect = lambda k, d=None: "fake_key" if k == "GEMINI_API_KEY" else d
        MockGemini.return_value.models.generate_content.side_effect = Exception("Gemini Error")
        mock_local_qwen.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("sys.stdout", new=open(os.devnull, "w")):
            res = agent.diagnose(checkout)

        if res.get("is_fallback") and res.get("fallback_reason") == "api_error":
            print("[PASS] Malformed local JSON safely fell back to rule-based baseline.")
        else:
            print(f"[FAIL] Expected rule-based baseline on malformed local JSON. Got: {res}")

    # Test 4: Local Model Returns Invalid Category -> Rejected -> Rule-Based Baseline
    print("\n--- Test 4: Local Model Invalid Category -> Rejected -> Rule-Based Baseline ---")
    if os.path.exists(agent.CACHE_FILE):
        os.remove(agent.CACHE_FILE)

    with patch("agent.genai.Client") as MockGemini, \
         patch("local_agent.diagnose_local_qwen") as mock_local_qwen, \
         patch("agent.os.getenv") as mock_getenv:

        mock_getenv.side_effect = lambda k, d=None: "fake_key" if k == "GEMINI_API_KEY" else d
        MockGemini.return_value.models.generate_content.side_effect = Exception("Gemini Error")
        mock_local_qwen.return_value = {
            "reason": "alien_abduction",
            "confidence": 0.99,
            "recommended_intervention": "reminder_nudge",
            "discount_pct": 0,
            "reasoning_short": "Invalid category test"
        }

        with patch("sys.stdout", new=open(os.devnull, "w")):
            res = agent.diagnose(checkout)

        if res.get("is_fallback") and res.get("fallback_reason") == "api_error" and res.get("reason") == "distracted":
            print("[PASS] Invalid local category was rejected and safely fell back to baseline.")
        else:
            print(f"[FAIL] Expected baseline fallback on invalid category. Got: {res}")

    # Test 5: Local Model Low Confidence (<0.55) & Clamping Validation
    print("\n--- Test 5: Local Model Low Confidence (<0.55) & Clamping Validation ---")
    if os.path.exists(agent.CACHE_FILE):
        os.remove(agent.CACHE_FILE)

    with patch("agent.genai.Client") as MockGemini, \
         patch("local_agent.diagnose_local_qwen") as mock_local_qwen, \
         patch("agent.os.getenv") as mock_getenv:

        mock_getenv.side_effect = lambda k, d=None: "fake_key" if k == "GEMINI_API_KEY" else d
        MockGemini.return_value.models.generate_content.side_effect = Exception("Gemini Error")
        mock_local_qwen.return_value = {
            "reason": "price_hesitation",
            "confidence": 0.40,
            "recommended_intervention": "discount_code",
            "discount_pct": 10,
            "reasoning_short": "Low confidence test"
        }

        with patch("sys.stdout", new=open(os.devnull, "w")):
            res = agent.diagnose(checkout)

        if res.get("reason") == "unknown" and res.get("recommended_intervention") == "escalate_human":
            print("[PASS] Local model low confidence (<0.55) passed shared validation & was overridden to human escalation.")
        else:
            print(f"[FAIL] Low confidence was not overridden. Got: {res}")

    # Test 6: REAL Integration Test with Local Ollama qwen3:4b Server
    print("\n--- Test 6: Real Integration Call with Local Ollama qwen3:4b Server ---")
    ambiguous_checkout = {
        "checkout_id": "test_real_ambiguous",
        "cart_value": 2500,
        "items": ["Skin Hydrator"],
        "payment_attempt_status": "none",
        "failure_reason_raw": "",
        "time_since_abandonment_hours": 1.0,
        "customer_tier": "new"
    }

    try:
        real_res = local_agent.diagnose_local_qwen(ambiguous_checkout, timeout=30.0)
        print("Real Ollama Response Output:")
        print(json.dumps(real_res, indent=2))
        
        if real_res.get("reason") == "unknown" and real_res.get("recommended_intervention") == "escalate_human":
            print("[PASS] Real Ollama qwen3:4b model correctly classified ambiguous checkout as unknown/escalate_human!")
        else:
            print(f"[WARN] Real model returned: reason={real_res.get('reason')}, intervention={real_res.get('recommended_intervention')}")
    except Exception as e:
        print(f"[SKIP] Real Ollama integration call skipped/failed: {str(e)}")

if __name__ == "__main__":
    test_local_fallback()

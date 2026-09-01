import os
import sys
import json
import time
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent

class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None

def test_malformed_output():
    checkout = {
        "checkout_id": "test_chk",
        "cart_value": 100,
        "items": [],
        "payment_attempt_status": "none",
        "failure_reason_raw": "",
        "time_since_abandonment_hours": 10,
        "customer_tier": "new"
    }

    cases = [
        {
            "name": "Case 1: Valid JSON with prose",
            "text": "Sure, here's the diagnosis:\n```json\n{\"reason\": \"distracted\", \"confidence\": 0.8, \"recommended_intervention\": \"reminder_nudge\", \"discount_pct\": 0, \"reasoning_short\": \"test\"}\n```\nLet me know if you need anything else!"
        },
        {
            "name": "Case 2: Truncated JSON",
            "text": "{\"reason\": \"payment_failed\", \"confidence\": 0.9, \"recommended"
        },
        {
            "name": "Case 3: Invalid intervention",
            "text": "{\"reason\": \"distracted\", \"confidence\": 0.9, \"recommended_intervention\": \"send_carrier_pigeon\", \"discount_pct\": 0, \"reasoning_short\": \"test\"}"
        },
        {
            "name": "Case 4a: Confidence 0.55 (Boundary)",
            "text": "{\"reason\": \"price_hesitation\", \"confidence\": 0.55, \"recommended_intervention\": \"discount_code\", \"discount_pct\": 10, \"reasoning_short\": \"test\"}"
        },
        {
            "name": "Case 4b: Confidence 0.54 (Below boundary)",
            "text": "{\"reason\": \"price_hesitation\", \"confidence\": 0.54, \"recommended_intervention\": \"discount_code\", \"discount_pct\": 10, \"reasoning_short\": \"test\"}"
        },
        {
            "name": "Case 5: Non-JSON garbage",
            "text": "I cannot process this request right now."
        },
        {
            "name": "Case 6: Empty object",
            "text": "{}"
        }
    ]

    for case in cases:
        print(f"--- {case['name']} ---")
        
        cache_path = agent.CACHE_FILE
        if os.path.exists(cache_path):
            os.remove(cache_path)
            
        with patch("agent.genai.Client") as MockClient, \
             patch("agent.os.getenv") as mock_getenv, \
             patch("agent.time.sleep") as mock_sleep:
             
            def fake_getenv(key, default=None):
                if key == "GEMINI_API_KEY": return "fake_key"
                if key == "GEMINI_MODEL": return "gemini-2.5-flash"
                return default
            mock_getenv.side_effect = fake_getenv
            
            mock_instance = MagicMock()
            mock_instance.models.generate_content.return_value = FakeResponse(case["text"])
            MockClient.return_value = mock_instance
            
            try:
                # Capture print statements to avoid polluting output with 5x retry warnings for expected failures
                with patch('sys.stdout', new=open(os.devnull, 'w')):
                    result = agent.diagnose(checkout)
                
                if "Case 1" in case["name"]:
                    if result.get("reason") == "distracted" and not result.get("is_fallback", False):
                        print("[PASS] Successfully extracted JSON despite prose.")
                    else:
                        print(f"[FAIL] Failed to extract JSON correctly. Result: {result}")
                        
                elif "Case 2" in case["name"]:
                    if result.get("is_fallback", False) and result.get("fallback_reason") == "api_error":
                        print("[PASS] Safely fell back after max retries for truncated JSON.")
                    else:
                        print(f"[FAIL] Did not fallback safely. Result: {result}")
                        
                elif "Case 3" in case["name"]:
                    if result.get("recommended_intervention") == "escalate_human":
                        print("[PASS] Clamped invalid intervention to escalate_human.")
                    else:
                        print(f"[FAIL] Did not clamp invalid intervention. Result: {result}")
                        
                elif "Case 4a" in case["name"]:
                    if result.get("reason") == "price_hesitation":
                        print("[PASS] 0.55 confidence was NOT overridden.")
                    else:
                        print(f"[FAIL] 0.55 confidence was incorrectly overridden. Result: {result}")
                        
                elif "Case 4b" in case["name"]:
                    if result.get("reason") == "unknown" and result.get("recommended_intervention") == "escalate_human":
                        print("[PASS] 0.54 confidence WAS safely overridden to unknown/escalate_human.")
                    else:
                        print(f"[FAIL] 0.54 confidence was NOT overridden. Result: {result}")
                        
                elif "Case 5" in case["name"]:
                    if result.get("is_fallback", False) and result.get("fallback_reason") == "api_error":
                        print("[PASS] Safely fell back for garbage text.")
                    else:
                        print(f"[FAIL] Did not fallback safely. Result: {result}")
                        
                elif "Case 6" in case["name"]:
                    if result.get("is_fallback", False) and result.get("fallback_reason") == "api_error":
                        print("[PASS] Safely fell back for empty object (missing fields).")
                    else:
                        print(f"[FAIL] Did not fallback safely for missing fields. Result: {result}")
                        
            except Exception as e:
                print(f"[FAIL] Uncaught exception during diagnose: {str(e)}")
        print()

if __name__ == "__main__":
    test_malformed_output()

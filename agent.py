from filelock import FileLock
import os
import json
import re
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "diagnosis_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with FileLock(CACHE_FILE + ".lock"):
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with FileLock(CACHE_FILE + ".lock"):
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

def classify_baseline(checkout):
    """Pure Python baseline classifier without LLM."""
    payment_status = checkout.get("payment_attempt_status", "none")
    time_abandoned = checkout.get("time_since_abandonment_hours", 0)
    
    if payment_status == "failed":
        return "payment_failed"
    elif time_abandoned > 24:
        return "price_hesitation"
    elif time_abandoned < 12:
        return "distracted"
    else:
        return "unknown"

def diagnose(checkout, force_fallback=False):
    checkout_id = checkout["checkout_id"]
    cache = load_cache()
    
    if checkout_id in cache:
        return cache[checkout_id]

    baseline_reason = classify_baseline(checkout)
    baseline_intervention_map = {
        "payment_failed": "payment_retry_link",
        "price_hesitation": "discount_code",
        "distracted": "reminder_nudge",
        "unknown": "escalate_human"
    }
    
    fallback = {
        "reason": baseline_reason,
        "confidence": 0.6,
        "recommended_intervention": baseline_intervention_map.get(baseline_reason, "escalate_human"),
        "discount_pct": 10 if baseline_reason == "price_hesitation" else 0,
        "reasoning_short": "AI unavailable (Rate Limit), using rule-based baseline.",
        "input_tokens": 0,
        "output_tokens": 0,
        "is_fallback": True
    }
    
    if force_fallback:
        fallback["reasoning_short"] = "AI skipped to reserve quota, using rule-based baseline."
        fallback["fallback_reason"] = "quota_reserved"
        cache[checkout_id] = fallback
        save_cache(cache)
        return fallback

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        fallback['fallback_reason'] = 'api_error'
        print("Warning: GEMINI_API_KEY not found in .env, returning fallback.")
        return fallback

    client = genai.Client(api_key=api_key)
    
    safe_data = {
        "cart_value": checkout.get("cart_value"),
        "items": checkout.get("items"),
        "payment_attempt_status": checkout.get("payment_attempt_status"),
        "failure_reason_raw": checkout.get("failure_reason_raw"),
        "time_since_abandonment_hours": checkout.get("time_since_abandonment_hours"),
        "customer_tier": checkout.get("customer_tier")
    }

    prompt = f"""You are an AI diagnosing abandoned checkouts for Lumen Skincare.
Analyze this checkout data: {json.dumps(safe_data)}
    
Rules:
- payment_attempt_status == "failed" usually -> payment_failed -> payment_retry_link
- high cart_value + no payment attempt + long time since abandonment -> often price_hesitation -> discount_code (scale discount_pct with cart_value and customer_tier — new customers can get slightly more)
- short time_since_abandonment + no failure signal -> distracted -> reminder_nudge
- ambiguous signals or model uncertainty -> unknown -> escalate_human

Return ONLY STRICT JSON. No markdown fences, no preamble.
Schema:
{{
  "reason": "payment_failed" | "price_hesitation" | "distracted" | "unknown",
  "confidence": 0.0-1.0,
  "recommended_intervention": "payment_retry_link" | "discount_code" | "reminder_nudge" | "escalate_human",
  "discount_pct": 0-20,
  "reasoning_short": "<one sentence>"
}}
"""
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    retries = 5
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )

            
            # 1. Extract JSON using regex to handle surrounding prose/markdown
            raw_text_str = response.text.strip()
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                match = re.search(r'(\{.*?\})', raw_text_str, re.DOTALL)
                json_str = match.group(1) if match else raw_text_str
            
            result = json.loads(json_str.strip())
            
            # 2. Validate required schema fields
            if not isinstance(result, dict) or "reason" not in result or "recommended_intervention" not in result:
                raise ValueError("Missing required schema fields in AI response")
            
            # 3. Apply confidence threshold guardrail (< 0.55)
            if result.get("confidence", 1.0) < 0.55:
                result["reason"] = "unknown"
                result["recommended_intervention"] = "escalate_human"
                result["reasoning_short"] = "Confidence below threshold (0.55), escalated."
            
            # 4. Clamp invalid interventions
            valid_interventions = ["payment_retry_link", "discount_code", "reminder_nudge", "escalate_human"]
            if result.get("recommended_intervention") not in valid_interventions:
                result["recommended_intervention"] = "escalate_human"

            result["input_tokens"] = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
            result["output_tokens"] = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
            result["is_fallback"] = False
            
            cache[checkout_id] = result
            save_cache(cache)
            return result
            
        except Exception as e:
            err_str = str(e)
            print(f"Gemini API Exception on attempt {attempt+1}/{retries} for {checkout_id}: {err_str}")
            sleep_time = 65.0
            print(f"Rate limited or error. Sleeping {sleep_time:.2f}s before retry...")
            time.sleep(sleep_time)
            
    print(f"Agent error after max retries. Falling back.")
    fallback['fallback_reason'] = 'api_error'
    cache[checkout_id] = fallback
    save_cache(cache)
    return fallback


RECEIVABLES_CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "receivables_diagnosis_cache.json")

def load_receivables_cache():
    if os.path.exists(RECEIVABLES_CACHE_FILE):
        with open(RECEIVABLES_CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_receivables_cache(cache):
    with open(RECEIVABLES_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def classify_receivable_baseline(invoice):
    """Pure Python baseline classifier for B2B receivables."""
    days_overdue = invoice.get("days_overdue", 0)
    history = invoice.get("promise_to_pay_history", [])
    broken_promises = sum(1 for p in history if not p.get("kept", True))
    
    if broken_promises >= 2:
        return "payment_capacity_issue"
    elif days_overdue > 60:
        return "payment_capacity_issue"
    elif days_overdue > 30:
        return "awaiting_approval"
    elif days_overdue > 15:
        return "dispute_unresolved"
    else:
        return "awaiting_approval"

def diagnose_receivable(invoice, force_fallback=True):
    """Diagnoses B2B receivables with PII stripping, schema validation, and fallback logic."""
    invoice_id = invoice["invoice_id"]
    cache = load_receivables_cache()
    
    if invoice_id in cache:
        return cache[invoice_id]

    baseline_reason = classify_receivable_baseline(invoice)
    baseline_action_map = {
        "payment_capacity_issue": "escalate_to_collections",
        "awaiting_approval": "request_promise_to_pay",
        "dispute_unresolved": "send_reminder",
        "unknown": "escalate_human"
    }
    
    fallback = {
        "reason": baseline_reason,
        "confidence": 0.6,
        "recommended_action": baseline_action_map.get(baseline_reason, "escalate_human"),
        "reasoning_short": "AI unavailable/skipped, using B2B rule-based baseline.",
        "input_tokens": 0,
        "output_tokens": 0,
        "is_fallback": True
    }
    
    if force_fallback:
        fallback["reasoning_short"] = "AI skipped to reserve quota, using B2B rule-based baseline."
        fallback["fallback_reason"] = "quota_reserved"
        cache[invoice_id] = fallback
        save_receivables_cache(cache)
        return fallback

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        fallback['fallback_reason'] = 'api_error'
        return fallback

    client = genai.Client(api_key=api_key)
    
    # Strip business_id PII
    safe_data = {
        "business_type": invoice.get("business_type"),
        "amount_due": invoice.get("amount_due"),
        "days_overdue": invoice.get("days_overdue"),
        "previous_contact_attempts": invoice.get("previous_contact_attempts"),
        "promise_to_pay_history": invoice.get("promise_to_pay_history")
    }

    prompt = f"""You are an AI diagnosing overdue B2B receivables for Lumen Skincare.
Analyze this invoice data: {json.dumps(safe_data)}
    
Rules:
- 2+ broken promises or days_overdue > 60 -> payment_capacity_issue -> escalate_to_collections
- 30+ days overdue without broken promises -> awaiting_approval -> request_promise_to_pay
- <30 days overdue -> dispute_unresolved or awaiting_approval -> send_reminder
- uncertainty -> unknown -> escalate_human

Return ONLY STRICT JSON. Schema:
{{
  "reason": "payment_capacity_issue" | "dispute_unresolved" | "awaiting_approval" | "unknown",
  "confidence": 0.0-1.0,
  "recommended_action": "send_reminder" | "escalate_to_collections" | "request_promise_to_pay" | "escalate_human",
  "reasoning_short": "<one sentence>"
}}
"""
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    retries = 5
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )

            raw_text_str = response.text.strip()
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                match = re.search(r'(\{.*?\})', raw_text_str, re.DOTALL)
                json_str = match.group(1) if match else raw_text_str
            
            result = json.loads(json_str.strip())
            
            if not isinstance(result, dict) or "reason" not in result or "recommended_action" not in result:
                raise ValueError("Missing required schema fields in AI response")
            
            if result.get("confidence", 1.0) < 0.55:
                result["reason"] = "unknown"
                result["recommended_action"] = "escalate_human"
                result["reasoning_short"] = "Confidence below threshold (0.55), escalated."
            
            valid_actions = ["send_reminder", "escalate_to_collections", "request_promise_to_pay", "escalate_human"]
            if result.get("recommended_action") not in valid_actions:
                result["recommended_action"] = "escalate_human"

            result["input_tokens"] = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
            result["output_tokens"] = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
            result["is_fallback"] = False
            
            cache[invoice_id] = result
            save_receivables_cache(cache)
            return result
            
        except Exception as e:
            err_str = str(e)
            print(f"Gemini API Exception on attempt {attempt+1}/{retries} for {invoice_id}: {err_str}")
            time.sleep(65.0)
            
    fallback['fallback_reason'] = 'api_error'
    cache[invoice_id] = fallback
    save_receivables_cache(cache)
    return fallback

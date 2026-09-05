import json
import ollama

LOCAL_MODEL = "qwen3:4b"

CHECKOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "enum": ["payment_failed", "price_hesitation", "distracted", "unknown"]
        },
        "confidence": {
            "type": "number"
        },
        "recommended_intervention": {
            "type": "string",
            "enum": ["payment_retry_link", "discount_code", "reminder_nudge", "escalate_human"]
        },
        "discount_pct": {
            "type": "integer"
        },
        "reasoning_short": {
            "type": "string"
        }
    },
    "required": ["reason", "confidence", "recommended_intervention", "discount_pct", "reasoning_short"]
}

def diagnose_local_qwen(checkout, timeout=10.0):
    """Diagnoses an abandoned checkout using local Ollama Qwen3:4b model conservatively.
    Returns parsed dictionary or raises Exception on failure/timeout.
    """
    safe_data = {
        "cart_value": checkout.get("cart_value"),
        "items": checkout.get("items"),
        "payment_attempt_status": checkout.get("payment_attempt_status"),
        "failure_reason_raw": checkout.get("failure_reason_raw"),
        "time_since_abandonment_hours": checkout.get("time_since_abandonment_hours"),
        "customer_tier": checkout.get("customer_tier")
    }

    prompt = (
        "Diagnose this abandoned checkout for Lumen Skincare conservatively.\n"
        f"Data: {json.dumps(safe_data)}\n\n"
        "Strict Classification Rules:\n"
        "1. If payment_attempt_status == 'failed' -> reason='payment_failed', recommended_intervention='payment_retry_link'\n"
        "2. Return reason='price_hesitation' (recommended_intervention='discount_code') ONLY when there is explicit evidence related to price (e.g. price query or price failure notes). Do NOT infer price hesitation merely from cart value, abandonment duration, or lack of payment attempt.\n"
        "3. Return reason='distracted' (recommended_intervention='reminder_nudge') ONLY when there is explicit evidence of interruption or inactivity beyond simply knowing that a checkout was abandoned. Do NOT treat time_since_abandonment_hours alone as sufficient evidence.\n"
        "4. Otherwise, for ambiguous data or lack of explicit evidence -> reason='unknown', recommended_intervention='escalate_human'\n"
        "5. Never infer missing reasons.\n\n"
        "Return ONLY the structured JSON matching schema."
    )

    client = ollama.Client(timeout=timeout)
    response = client.chat(
        model=LOCAL_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format=CHECKOUT_SCHEMA,
        options={
            "temperature": 0.0,
            "num_predict": 150
        },
        think=False
    )

    if isinstance(response, dict):
        message = response.get("message", {})
        content = message.get("content", "").strip() if isinstance(message, dict) else str(message)
    else:
        content = getattr(getattr(response, "message", None), "content", "").strip()

    if not content:
        raise ValueError("Empty response from local Ollama Qwen model")

    result = json.loads(content)
    return result

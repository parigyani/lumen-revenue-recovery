import json
import random
import os

def generate(num_records=20):
    checkouts = []
    tiers = ["new", "returning", "vip"]
    
    for i in range(1, num_records + 1):
        checkout_id = f"chk_{i:04d}"
        customer_id = f"cust_{random.randint(100, 999)}"
        tier = random.choice(tiers)
        cart_value = round(random.uniform(300, 8000), 2)
        
        # Decide category: payment_failed, price_hesitation, distracted, unknown
        category = random.choice(["payment_failed", "price_hesitation", "distracted", "unknown"])
        
        if category == "payment_failed":
            payment_attempt_status = "failed"
            failure_reason_raw = random.choice(["insufficient_funds", "bank_declined", "otp_timeout"])
            time_since_abandonment_hours = round(random.uniform(0.5, 24), 1)
        elif category == "price_hesitation":
            payment_attempt_status = "none"
            failure_reason_raw = ""
            time_since_abandonment_hours = round(random.uniform(24, 72), 1)
            # Usually higher cart value for price hesitation
            cart_value = round(random.uniform(3000, 8000), 2)
        elif category == "distracted":
            payment_attempt_status = "none"
            failure_reason_raw = ""
            time_since_abandonment_hours = round(random.uniform(0.5, 4), 1)
        else: # unknown/ambiguous
            payment_attempt_status = random.choice(["none", "partial"])
            failure_reason_raw = random.choice(["", "user_aborted"])
            time_since_abandonment_hours = round(random.uniform(12, 48), 1)
        
        # Channel available
        channels = ["email"]
        if random.random() > 0.3:
            channels.append("whatsapp")
        if random.random() > 0.5:
            channels.append("sms")
            
        record = {
            "checkout_id": checkout_id,
            "customer_id": customer_id,
            "customer_tier": tier,
            "cart_value": cart_value,
            "items": [{"sku": f"SKU-{random.randint(1000, 9999)}", "name": "Lumen Skincare Product", "qty": random.randint(1, 3)}],
            "payment_attempt_status": payment_attempt_status,
            "failure_reason_raw": failure_reason_raw,
            "time_since_abandonment_hours": time_since_abandonment_hours,
            "channel_available": channels,
            "already_completed_elsewhere": False,
            "already_recovered": False,
            "contact_attempts": 0,
            "last_contact_at": None,
            "status": "abandoned",
            "ground_truth_reason": category
        }
        checkouts.append(record)
        
    # Seed ~5 records as already_completed_elsewhere = true
    completed_indices = random.sample(range(num_records), min(2, num_records))
    for idx in completed_indices:
        checkouts[idx]["already_completed_elsewhere"] = True
        
    filepath = os.path.join(os.path.dirname(__file__), "checkouts.json")
    with open(filepath, "w") as f:
        json.dump(checkouts, f, indent=2)
    print(f"Generated {len(checkouts)} checkouts in {filepath}")

if __name__ == "__main__":
    generate()

import os
import random
import json
from datetime import datetime
import razorpay
from checkouts import is_recoverable
from audit import log_event
from dotenv import load_dotenv
from filelock import FileLock

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

rzp_key_id = os.getenv("RAZORPAY_KEY_ID")
rzp_secret = os.getenv("RAZORPAY_SECRET")
if rzp_key_id and rzp_secret:
    rzp_client = razorpay.Client(auth=(rzp_key_id, rzp_secret))
else:
    rzp_client = None

def generate_payment_link(checkout_id, amount, discount_pct=0):
    final_amount = amount * (1 - discount_pct / 100.0)
    final_amount_paise = int(final_amount * 100)
    
    if rzp_client:
        try:
            link_data = {
                "amount": final_amount_paise,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Recovery for {checkout_id}",
                "reference_id": checkout_id,
            }
            res = rzp_client.payment_link.create(link_data)
            return res.get("short_url", f"https://payment.lumen-skincare.com/checkout/{checkout_id}")
        except Exception:
            return f"https://payment.lumen-skincare.com/checkout/{checkout_id}"
    else:
        return f"https://payment.lumen-skincare.com/checkout/{checkout_id}"

def execute_recovery(checkout_id, diagnosis, checkouts_file=None):
    """
    Executes the deterministic recovery process based on the AI diagnosis.
    Returns a result dict.
    Wrapped entirely in a FileLock to prevent race conditions during read-modify-write.
    """
    if checkouts_file is None:
        checkouts_file = os.path.join(os.path.dirname(__file__), "data", "checkouts.json")
    lock_file = checkouts_file + ".lock" 
    
    with FileLock(lock_file):
        with open(checkouts_file, 'r') as f:
            checkouts = json.load(f)
            
        checkout = next((c for c in checkouts if c['checkout_id'] == checkout_id), None)
        if not checkout:
            return {"status": "error", "message": "Checkout not found"}

        # 1. LIVE RE-CHECK
        recoverable, skip_reason = is_recoverable(checkout)
        if not recoverable:
            log_event("skip", checkout_id, {"reason": skip_reason})
            return {"status": "skipped", "reason": skip_reason}

        # 2. ENFORCE STOPPING RULES
        if checkout.get("contact_attempts", 0) >= 3:
            skip_reason = "max_attempts_reached"
            log_event("skip", checkout_id, {"reason": skip_reason})
            return {"status": "skipped", "reason": skip_reason}

        if checkout.get("last_contact_at"):
            try:
                last_contact_dt = datetime.fromisoformat(checkout["last_contact_at"])
                if (datetime.now() - last_contact_dt).total_seconds() / 3600 < 24:
                    skip_reason = "cooldown_active"
                    log_event("skip", checkout_id, {"reason": skip_reason})
                    return {"status": "skipped", "reason": skip_reason}
            except Exception:
                pass

        # 3. MAP INTERVENTION TO MESSAGE & CHANNEL
        intervention = diagnosis.get("recommended_intervention")
        cart_value = checkout.get("cart_value", 0)
        customer_tier = checkout.get("customer_tier", "returning")
        available_channels = checkout.get("channel_available", [])
        
        channel = "email"
        message_sent = ""
        payment_link = ""
        discount_pct = 0
        
        if intervention == "payment_retry_link":
            channel = "whatsapp" if "whatsapp" in available_channels else "email"
            payment_link = generate_payment_link(checkout_id, cart_value)
            message_sent = f"Hi, it looks like your payment failed. You can complete your purchase here: {payment_link}"
        elif intervention == "discount_code":
            channel = "email"
            discount_pct = diagnosis.get("discount_pct", 10)
            payment_link = generate_payment_link(checkout_id, cart_value, discount_pct)
            message_sent = f"Still thinking? Use code LUMEN{discount_pct}OFF to complete your purchase: {payment_link}"
        elif intervention == "reminder_nudge":
            channel = "sms" if "sms" in available_channels else "email"
            message_sent = "Just a reminder: you left some items in your cart at Lumen Skincare!"
        elif intervention == "escalate_human":
            pass
        
        # 4. SIMULATE OUTCOME
        success = False
        recovered_amount = 0
        
        if intervention != "escalate_human":
            base_success = {
                "payment_retry_link": 0.45,
                "discount_code": 0.35,
                "reminder_nudge": 0.20
            }.get(intervention, 0)
            
            if intervention == "discount_code" and customer_tier == "new":
                base_success += 0.10
                
            if random.random() < base_success:
                success = True
                recovered_amount = cart_value * (1 - discount_pct / 100.0)
                recovered_amount = round(recovered_amount, 2)

        # 5. UPDATE STATE
        now_iso = datetime.now().isoformat()
        update_fields = {
            "contact_attempts": checkout.get("contact_attempts", 0) + 1,
            "last_contact_at": now_iso
        }
        
        result_status = ""
        if intervention == "escalate_human":
            result_status = "escalated"
            update_fields["status"] = "pending_human"
        else:
            if success:
                result_status = "recovered"
                update_fields["status"] = "recovered"
                update_fields["already_recovered"] = True
            else:
                result_status = "contacted"
                update_fields["status"] = "contacted"
                
        # Apply updates back into memory list and save
        checkout.update(update_fields)
        with open(checkouts_file, 'w') as f:
            json.dump(checkouts, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # 6. LOG TO AUDIT
        action_details = {
            "intervention": intervention,
            "channel": channel if intervention != "escalate_human" else "none",
            "message_sent": message_sent
        }
        if intervention != "escalate_human":
            log_event("action", checkout_id, action_details)
        else:
            log_event("escalation", checkout_id, action_details)
            
        outcome_details = {
            "outcome": result_status,
            "recovered_amount": recovered_amount
        }
        log_event("outcome", checkout_id, outcome_details)
        
        return {
            "status": result_status,
            "intervention": intervention,
            "channel": channel,
            "message": message_sent,
            "link": payment_link,
            "recovered_amount": recovered_amount,
            "success": success
        }

def execute_receivable_recovery(invoice_id, diagnosis):
    """
    Executes recovery for B2B overdue receivables under FileLock.
    Stopping rules:
    - 2+ broken promises -> force escalate_human (broken_promise_stopping_rule)
    - previous_contact_attempts >= 3 -> max_attempts_reached
    - last_contact_at within 48h -> cooldown_active
    """
    lock_file = os.path.join(os.path.dirname(__file__), "data", "receivables.json.lock")
    receivables_file = os.path.join(os.path.dirname(__file__), "data", "receivables.json")
    
    with FileLock(lock_file):
        if not os.path.exists(receivables_file):
            return {"status": "error", "message": "Receivables file not found"}
            
        with open(receivables_file, 'r') as f:
            receivables = json.load(f)
            
        invoice = next((r for r in receivables if r['invoice_id'] == invoice_id), None)
        if not invoice:
            return {"status": "error", "message": "Invoice not found"}

        history = invoice.get("promise_to_pay_history", [])
        broken_promises = sum(1 for p in history if not p.get("kept", True))
        
        # Stopping Rule A: 2+ broken promises -> force escalate_human
        if broken_promises >= 2:
            skip_reason = "broken_promise_stopping_rule"
            log_event("receivable_skip", invoice_id, {"reason": skip_reason, "broken_promises": broken_promises}, entity_type="receivable")
            diagnosis["recommended_action"] = "escalate_human"

        # Stopping Rule B: Max attempts >= 3
        if invoice.get("previous_contact_attempts", 0) >= 3:
            skip_reason = "max_attempts_reached"
            log_event("receivable_skip", invoice_id, {"reason": skip_reason}, entity_type="receivable")
            return {"status": "skipped", "reason": skip_reason}

        # Stopping Rule C: Cooldown 48h
        if invoice.get("last_contact_at"):
            try:
                last_contact_dt = datetime.fromisoformat(invoice["last_contact_at"])
                if (datetime.now() - last_contact_dt).total_seconds() / 3600 < 48:
                    skip_reason = "cooldown_active"
                    log_event("receivable_skip", invoice_id, {"reason": skip_reason}, entity_type="receivable")
                    return {"status": "skipped", "reason": skip_reason}
            except Exception:
                pass

        action = diagnosis.get("recommended_action")
        amount_due = invoice.get("amount_due", 0)
        
        message_sent = ""
        if action == "send_reminder":
            message_sent = f"Reminder: Invoice {invoice_id} for ₹{amount_due} is overdue. Please complete payment."
        elif action == "request_promise_to_pay":
            message_sent = f"Notice: Invoice {invoice_id} is overdue. Please confirm your promised payment date."
        elif action == "escalate_to_collections":
            message_sent = f"Final Warning: Invoice {invoice_id} has been forwarded to collections."
        elif action == "escalate_human":
            message_sent = ""

        # Simulating outcome
        success = False
        status_result = ""
        recovered_amount = 0
        new_promise = None

        if action == "send_reminder":
            if random.random() < 0.30:
                success = True
                status_result = "recovered"
                recovered_amount = amount_due
            else:
                status_result = "reminded"
        elif action == "request_promise_to_pay":
            if random.random() < 0.50:
                success = True
                status_result = "promise_recorded"
                new_promise = {"promised_date": "2026-09-15", "kept": True}
            else:
                status_result = "promise_requested"
        elif action == "escalate_to_collections":
            status_result = "escalated_collections"
        elif action == "escalate_human":
            status_result = "escalated_human"

        now_iso = datetime.now().isoformat()
        update_fields = {
            "previous_contact_attempts": invoice.get("previous_contact_attempts", 0) + 1,
            "last_contact_at": now_iso,
            "status": status_result
        }
        if new_promise:
            history.append(new_promise)
            update_fields["promise_to_pay_history"] = history

        invoice.update(update_fields)
        with open(receivables_file, 'w') as f:
            json.dump(receivables, f, indent=2)

        log_event("receivable_action", invoice_id, {"action": action, "message": message_sent}, entity_type="receivable")
        log_event("receivable_outcome", invoice_id, {"status": status_result, "recovered_amount": recovered_amount}, entity_type="receivable")

        return {
            "status": status_result,
            "action": action,
            "message": message_sent,
            "recovered_amount": recovered_amount,
            "broken_promises": broken_promises
        }

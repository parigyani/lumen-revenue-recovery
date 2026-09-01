import json
import random
import os

def generate_receivables():
    invoices = []
    biz_types = ["SMB", "enterprise"]
    
    # Define explicit scenarios for 15 B2B invoices to include ground truth and ambiguous edge cases
    scenarios = [
        # inv_0001: Clear dispute
        {"days": 14.5, "type": "SMB", "promises": [], "truth": "dispute_unresolved"},
        # inv_0002: Clear awaiting approval
        {"days": 42.0, "type": "enterprise", "promises": [{"promised_date": "2026-08-10", "kept": True}], "truth": "awaiting_approval"},
        # inv_0003: 2 broken promises -> capacity issue
        {"days": 25.0, "type": "SMB", "promises": [{"promised_date": "2026-07-15", "kept": False}, {"promised_date": "2026-08-01", "kept": False}], "truth": "payment_capacity_issue"},
        # inv_0004: Over 60 days -> capacity issue
        {"days": 75.2, "type": "enterprise", "promises": [], "truth": "payment_capacity_issue"},
        # inv_0005: Ambiguous — 22 days overdue with 1 broken promise & high amount SMB (could be dispute or capacity)
        {"days": 22.0, "type": "SMB", "promises": [{"promised_date": "2026-08-05", "kept": False}], "truth": "unknown"},
        # inv_0006: Clear dispute
        {"days": 10.0, "type": "enterprise", "promises": [], "truth": "dispute_unresolved"},
        # inv_0007: 2 broken promises -> capacity issue
        {"days": 45.0, "type": "SMB", "promises": [{"promised_date": "2026-07-20", "kept": False}, {"promised_date": "2026-08-05", "kept": False}], "truth": "payment_capacity_issue"},
        # inv_0008: Clear awaiting approval
        {"days": 35.0, "type": "SMB", "promises": [], "truth": "awaiting_approval"},
        # inv_0009: Over 60 days -> capacity issue
        {"days": 82.0, "type": "SMB", "promises": [], "truth": "payment_capacity_issue"},
        # inv_00010: Ambiguous — 31 days overdue enterprise client with 1 broken promise (could be approval delay or capacity)
        {"days": 31.0, "type": "enterprise", "promises": [{"promised_date": "2026-08-12", "kept": False}], "truth": "unknown"},
        # inv_0011: Clear dispute
        {"days": 18.0, "type": "SMB", "promises": [], "truth": "dispute_unresolved"},
        # inv_0012: 2 broken promises -> capacity issue
        {"days": 50.0, "type": "enterprise", "promises": [{"promised_date": "2026-07-10", "kept": False}, {"promised_date": "2026-08-01", "kept": False}], "truth": "payment_capacity_issue"},
        # inv_0013: Clear awaiting approval
        {"days": 38.5, "type": "enterprise", "promises": [], "truth": "awaiting_approval"},
        # inv_0014: Over 60 days -> capacity issue
        {"days": 68.0, "type": "SMB", "promises": [], "truth": "payment_capacity_issue"},
        # inv_0015: Ambiguous — 12 days overdue enterprise client with partial dispute notes
        {"days": 12.0, "type": "enterprise", "promises": [], "truth": "unknown"}
    ]
    
    for i, s in enumerate(scenarios, start=1):
        invoice_id = f"inv_{i:04d}"
        business_id = f"biz_{random.randint(10, 99):03d}"
        amount_due = round(random.uniform(5000, 150000), 2)
        
        record = {
            "invoice_id": invoice_id,
            "business_id": business_id,
            "business_type": s["type"],
            "amount_due": amount_due,
            "days_overdue": s["days"],
            "previous_contact_attempts": 0,
            "promise_to_pay_history": s["promises"],
            "last_contact_at": None,
            "status": "overdue",
            "ground_truth_reason": s["truth"]
        }
        invoices.append(record)
        
    filepath = os.path.join(os.path.dirname(__file__), "receivables.json")
    with open(filepath, "w") as f:
        json.dump(invoices, f, indent=2)
    print(f"Generated {len(invoices)} receivables in {filepath}")

if __name__ == "__main__":
    generate_receivables()

import json
import random
import os

def generate_receivables():
    invoices = []
    biz_types = ["SMB", "enterprise"]
    
    for i in range(1, 16):
        invoice_id = f"inv_{i:04d}"
        business_id = f"biz_{random.randint(10, 99):03d}"
        business_type = random.choice(biz_types)
        amount_due = round(random.uniform(5000, 150000), 2)
        days_overdue = round(random.uniform(1, 90), 1)
        
        promise_history = []
        
        # Seed ~3 records with 2 broken promises explicitly
        if i in [3, 7, 12]:
            promise_history = [
                {"promised_date": "2026-07-15", "kept": False},
                {"promised_date": "2026-08-01", "kept": False}
            ]
        elif random.random() > 0.6:
            promise_history = [
                {"promised_date": "2026-08-10", "kept": True}
            ]
        elif random.random() > 0.7:
            promise_history = [
                {"promised_date": "2026-08-05", "kept": False}
            ]
            
        record = {
            "invoice_id": invoice_id,
            "business_id": business_id,
            "business_type": business_type,
            "amount_due": amount_due,
            "days_overdue": days_overdue,
            "previous_contact_attempts": 0,
            "promise_to_pay_history": promise_history,
            "last_contact_at": None,
            "status": "overdue"
        }
        invoices.append(record)
        
    filepath = os.path.join(os.path.dirname(__file__), "receivables.json")
    with open(filepath, "w") as f:
        json.dump(invoices, f, indent=2)
    print(f"Generated {len(invoices)} receivables in {filepath}")

if __name__ == "__main__":
    generate_receivables()

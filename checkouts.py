import json
import os
from datetime import datetime
from filelock import FileLock

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "checkouts.json")
LOCK_FILE = DATA_FILE + ".lock"

def load_checkouts():
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            return []
        with open(DATA_FILE, "r") as f:
            return json.load(f)

def save_checkouts(data):
    with FileLock(LOCK_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

def get_checkout(checkout_id):
    # Safe to read without lock, but we lock to be consistent
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            return None
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for c in data:
            if c["checkout_id"] == checkout_id:
                return c
        return None

def update_checkout(checkout_id, **fields):
    with FileLock(LOCK_FILE):
        if not os.path.exists(DATA_FILE):
            return
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for c in data:
            if c["checkout_id"] == checkout_id:
                c.update(fields)
                break
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

def is_recoverable(checkout):
    """
    Returns (bool, reason_if_not)
    """
    if checkout.get("already_recovered"):
        return False, "already_recovered"
    
    if checkout.get("already_completed_elsewhere"):
        return False, "already_completed_elsewhere"
        
    if checkout.get("time_since_abandonment_hours", 0) > 48:
        return False, "time_expired_48h"
        
    if checkout.get("contact_attempts", 0) >= 3:
        return False, "max_attempts_reached"
        
    last_contact_at = checkout.get("last_contact_at")
    if last_contact_at:
        try:
            last_contact_dt = datetime.fromisoformat(last_contact_at)
            hours_since_contact = (datetime.now() - last_contact_dt).total_seconds() / 3600
            if hours_since_contact < 24:
                return False, "cooldown_active"
        except Exception:
            pass
            
    return True, ""

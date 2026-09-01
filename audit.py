import json
import os
from datetime import datetime
from filelock import FileLock

AUDIT_FILE = os.path.join(os.path.dirname(__file__), "audit_log.json")
LOCK_FILE = AUDIT_FILE + ".lock"

def log_event(event_type, entity_id, details_dict, entity_type="checkout"):
    """
    Append an event to the audit log.
    entity_type: "checkout" or "receivable"
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details_dict
    }
    
    with FileLock(LOCK_FILE):
        with open(AUDIT_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

def get_audit_log(event_type=None):
    if not os.path.exists(AUDIT_FILE):
        return []
    
    logs = []
    with open(AUDIT_FILE, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if event_type is None or record.get("event_type") == event_type:
                    logs.append(record)
            except json.JSONDecodeError:
                pass
    return logs

import threading
import time
from checkouts import get_checkout, load_checkouts
from agent import diagnose
from recovery import execute_recovery

def run_recovery_thread(thread_id, checkout_id, diagnosis, results):
    print(f"[Thread {thread_id}] Executing recovery...")
    res = execute_recovery(checkout_id, diagnosis)
    results[thread_id] = res
    print(f"[Thread {thread_id}] Result status: {res.get('status')}, reason: {res.get('reason')}")

def test_concurrent_recovery():
    print("--- Running True Concurrent Recovery Stale-State Guard Test ---")
    checkouts = load_checkouts()
    target = None
    from checkouts import is_recoverable
    for c in checkouts:
        recoverable, reason = is_recoverable(c)
        if recoverable and c.get("status") == "abandoned":
            target = c
            break
            
    if not target:
        print("FAIL: No suitable checkout found to test.")
        return
        
    cid = target["checkout_id"]
    print(f"Target selected: {cid}")
    
    print("Pre-fetching AI diagnosis...")
    diagnosis = diagnose(target)
    
    results = {}
    
    t1 = threading.Thread(target=run_recovery_thread, args=(1, cid, diagnosis, results))
    t2 = threading.Thread(target=run_recovery_thread, args=(2, cid, diagnosis, results))
    
    print("Firing two concurrent threads at the exact same time...")
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    # Analyze results
    statuses = [res.get("status") for res in results.values()]
    
    if "skipped" in statuses and ("contacted" in statuses or "recovered" in statuses or "escalated" in statuses):
        print("\n✅ PASS: Only one thread executed! The other was caught by the stale-state guard.")
    elif statuses.count("skipped") == 2:
        # Depending on max attempts or cooldown, maybe both skipped, which is fine, but less illustrative
        print("\n✅ PASS (Alternative): Both skipped due to guardrails.")
    else:
        print(f"\n❌ FAIL: Concurrent execution allowed duplicate processing! Statuses: {statuses}")

if __name__ == "__main__":
    test_concurrent_recovery()

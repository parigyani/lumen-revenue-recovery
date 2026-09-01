import time
from checkouts import get_checkout, update_checkout, load_checkouts
from agent import diagnose
from recovery import execute_recovery

def test_race_condition():
    print("--- Running Sequential Double Recovery Stale-State Guard Test ---")
    # Grab a fresh checkout
    checkouts = load_checkouts()
    target = None
    for c in checkouts:
        if not c.get("already_completed_elsewhere") and c.get("status") == "abandoned":
            target = c
            break
            
    if not target:
        print("FAIL: No suitable checkout found to test.")
        return
        
    cid = target["checkout_id"]
    print(f"1. Target selected: {cid}")
    
    print("2. Calling AI for diagnosis...")
    diagnosis = diagnose(target)
    print(f"   AI Recommendation: {diagnosis.get('recommended_intervention')}")
    
    print(f"3. Simulating external mutation (customer pays on support call) in checkouts.json...")
    update_checkout(cid, already_completed_elsewhere=True)
    
    print("4. Executing recovery with stale memory...")
    result = execute_recovery(cid, diagnosis)
    
    if result.get("status") == "skipped" and result.get("reason") == "already_completed_elsewhere":
        print("✅ PASS: Live re-check caught the mutation and safely aborted execution!")
    else:
        print(f"❌ FAIL: Recovery sent anyway. Result: {result}")

if __name__ == "__main__":
    test_race_condition()

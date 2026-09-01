import os
os.environ['GEMINI_API_KEY'] = ''
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.generate_checkouts import generate
from checkouts import load_checkouts
from batch_runner import run_single_batch_pass

def test_idempotency():
    print("Regenerating fresh checkouts.json...")
    generate()
    
    # ------------------ PASS 1 ------------------
    checkouts_pass1 = load_checkouts()
    print("\n--- PASS 1 START ---")
    report_pass1 = run_single_batch_pass(checkouts_pass1)
    
    mutated_checkouts_pass1 = load_checkouts()
    pass1_state = {c["checkout_id"]: c for c in mutated_checkouts_pass1}
    
    recovered_in_pass1 = set()
    contacted_in_pass1 = set()
    for res in report_pass1["per_checkout_results"]:
        if res["status"] == "recovered":
            recovered_in_pass1.add(res["checkout_id"])
        elif res["status"] == "contacted":
            contacted_in_pass1.add(res["checkout_id"])
            
    # ------------------ PASS 2 ------------------
    print("--- PASS 2 START ---")
    checkouts_pass2 = load_checkouts() # Load fresh from disk
    report_pass2 = run_single_batch_pass(checkouts_pass2)
    
    mutated_checkouts_pass2 = load_checkouts()
    pass2_state = {c["checkout_id"]: c for c in mutated_checkouts_pass2}
    
    # ------------------ ASSERTIONS ------------------
    print("\n--- RESULTS & ASSERTIONS ---")
    
    fail_reasons = []
    
    # Assertion 1: No double-counting of revenue
    double_recovered = []
    for res in report_pass2["per_checkout_results"]:
        if res["checkout_id"] in recovered_in_pass1 and res["status"] == "recovered":
            double_recovered.append(res["checkout_id"])
            
    if double_recovered:
        print(f"[FAIL] Assertion 1 (No double recovery): {len(double_recovered)} checkouts were recovered again in Pass 2! IDs: {double_recovered[:5]}...")
        fail_reasons.append("double_recovery")
    else:
        print("[PASS] Assertion 1: No double-counting of revenue.")
        
    # Assertion 2: is_recoverable catches already_recovered
    failed_skip = []
    for res in report_pass2["per_checkout_results"]:
        if res["checkout_id"] in recovered_in_pass1 and res["status"] != "skipped":
            failed_skip.append(res["checkout_id"])
            
    if failed_skip:
        print(f"[FAIL] Assertion 2 (already_recovered correctly skipped): {len(failed_skip)} checkouts recovered in Pass 1 were NOT skipped in Pass 2! IDs: {failed_skip[:5]}...")
        fail_reasons.append("already_recovered_not_skipped")
    else:
        print("[PASS] Assertion 2: Checkouts already_recovered=true were correctly skipped in Pass 2.")
        
    # Assertion 3: contact_attempts only increments for legitimately eligible checkouts
    bad_increments = []
    for cid, state2 in pass2_state.items():
        state1 = pass1_state[cid]
        # if it was recovered in Pass 1, it should be skipped in Pass 2, so contact_attempts should remain the same
        if cid in recovered_in_pass1 or cid in contacted_in_pass1:
            if state2.get("contact_attempts", 0) > state1.get("contact_attempts", 0):
                bad_increments.append(cid)
             
    if bad_increments:
        print(f"[FAIL] Assertion 3 (Valid contact_attempts increment): {len(bad_increments)} checkouts had attempts incremented illegally! IDs: {bad_increments[:5]}...")
        fail_reasons.append("bad_contact_increments")
    else:
        print("[PASS] Assertion 3: contact_attempts incremented correctly.")
        
    # Assertion 4: Pass 2 incremental recovered_value from Pass 1 recoveries is 0
    incremental_value = 0
    for res in report_pass2["per_checkout_results"]:
        if res["checkout_id"] in recovered_in_pass1:
            incremental_value += res.get("recovered_amount", 0)
            
    if incremental_value > 0:
        print(f"[FAIL] Assertion 4 (Pass 2 incremental value from recovered): Incremental value is {incremental_value}, should be 0.")
        fail_reasons.append("incremental_value_nonzero")
    else:
        print("[PASS] Assertion 4: Pass 2 incremental recovered_value from already-recovered checkouts is 0.")

    print("\n--- SUMMARY TABLE ---")
    recovered_pass1_count = len(recovered_in_pass1)
    correctly_skipped_in_pass2 = recovered_pass1_count - len(failed_skip)
    
    print(f"Recovered in Pass 1:           {recovered_pass1_count}")
    print(f"Correctly skipped in Pass 2:   {correctly_skipped_in_pass2}")
    print(f"Total recovered_value Pass 1:  ₹{report_pass1['recovered_value']}")
    print(f"Incremental recovered_value from already-recovered in Pass 2: ₹{incremental_value}")
    
    if fail_reasons:
        sys.exit(1)

if __name__ == "__main__":
    test_idempotency()

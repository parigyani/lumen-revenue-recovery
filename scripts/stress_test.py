import os
import sys
import json
import time
import random
import threading
from filelock import FileLock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import diagnose
from recovery import execute_recovery

STRESS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "checkouts_stress.json")
LOCK_FILE = STRESS_FILE + ".lock"

def generate_stress_data(count):
    tiers = ["new", "returning", "vip"]
    categories = ["payment_failed", "price_hesitation", "distracted", "unknown"]
    checkouts = []
    
    for i in range(1, count + 1):
        checkout_id = f"chk_s_{i:06d}"
        customer_id = f"cust_{random.randint(1000, 9999)}"
        tier = random.choice(tiers)
        cart_value = round(random.uniform(300, 8000), 2)
        category = random.choice(categories)
        
        if category == "payment_failed":
            payment_attempt_status = "failed"
            failure_reason_raw = random.choice(["insufficient_funds", "bank_declined", "otp_timeout"])
            time_since_abandonment_hours = round(random.uniform(0.5, 24), 1)
        elif category == "price_hesitation":
            payment_attempt_status = "none"
            failure_reason_raw = ""
            time_since_abandonment_hours = round(random.uniform(24, 72), 1)
            cart_value = round(random.uniform(3000, 8000), 2)
        elif category == "distracted":
            payment_attempt_status = "none"
            failure_reason_raw = ""
            time_since_abandonment_hours = round(random.uniform(0.5, 4), 1)
        else:
            payment_attempt_status = random.choice(["none", "partial"])
            failure_reason_raw = random.choice(["", "user_aborted"])
            time_since_abandonment_hours = round(random.uniform(12, 48), 1)
            
        record = {
            "checkout_id": checkout_id,
            "customer_id": customer_id,
            "customer_tier": tier,
            "cart_value": cart_value,
            "items": [{"sku": f"SKU-{random.randint(1000, 9999)}", "name": "Lumen Skincare Product", "qty": random.randint(1, 3)}],
            "payment_attempt_status": payment_attempt_status,
            "failure_reason_raw": failure_reason_raw,
            "time_since_abandonment_hours": time_since_abandonment_hours,
            "channel_available": ["email", "whatsapp"],
            "already_completed_elsewhere": False,
            "already_recovered": False,
            "contact_attempts": 0,
            "last_contact_at": None,
            "status": "abandoned",
            "ground_truth_reason": category
        }
        checkouts.append(record)
        
    with open(STRESS_FILE, "w") as f:
        json.dump(checkouts, f, indent=2)
    return checkouts

def run_sequential_stress(count):
    checkouts = generate_stress_data(count)
    
    start_wall = time.perf_counter()
    lock_hold_times = []
    
    for c in checkouts:
        diag = diagnose(c, force_fallback=True)
        
        t0 = time.perf_counter()
        execute_recovery(c["checkout_id"], diag, checkouts_file=STRESS_FILE)
        t1 = time.perf_counter()
        
        lock_hold_times.append(t1 - t0)
        
    end_wall = time.perf_counter()
    
    total_wall_s = end_wall - start_wall
    avg_per_record_ms = (total_wall_s / count) * 1000
    avg_lock_ms = (sum(lock_hold_times) / len(lock_hold_times)) * 1000
    file_size_kb = os.path.getsize(STRESS_FILE) / 1024
    
    return {
        "count": count,
        "total_wall_s": round(total_wall_s, 3),
        "avg_per_record_ms": round(avg_per_record_ms, 2),
        "avg_lock_ms": round(avg_lock_ms, 2),
        "file_size_kb": round(file_size_kb, 1)
    }

def run_concurrent_stress_1000():
    count = 1000
    checkouts = generate_stress_data(count)
    num_workers = 10
    chunk_size = count // num_workers
    chunks = [checkouts[i * chunk_size : (i + 1) * chunk_size] for i in range(num_workers)]
    
    def worker_func(chunk):
        for c in chunk:
            diag = diagnose(c, force_fallback=True)
            execute_recovery(c["checkout_id"], diag, checkouts_file=STRESS_FILE)
            
    threads = []
    start_wall = time.perf_counter()
    
    for chunk in chunks:
        t = threading.Thread(target=worker_func, args=(chunk,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    end_wall = time.perf_counter()
    total_wall_s = end_wall - start_wall
    
    # Verify zero data corruption
    is_valid = True
    try:
        with open(STRESS_FILE, "r") as f:
            final_data = json.load(f)
        if len(final_data) != count:
            is_valid = False
    except Exception:
        is_valid = False
        
    return total_wall_s, is_valid

def main():
    print("=== SEQUENTIAL THROUGHPUT MEASUREMENTS ===")
    results = []
    for count in [100, 500, 1000]:
        res = run_sequential_stress(count)
        results.append(res)
        
    print(f"{'Count':<8} | {'Total Time (s)':<15} | {'Avg Time/Record (ms)':<22} | {'Avg Lock Hold Time (ms)':<23} | {'File Size (KB)':<14}")
    print("-" * 90)
    for r in results:
        print(f"{r['count']:<8} | {r['total_wall_s']:<15} | {r['avg_per_record_ms']:<22} | {r['avg_lock_ms']:<23} | {r['file_size_kb']:<14}")
        
    print("\n=== CONCURRENT CONTENTION MEASUREMENT (1000 RECORDS, 10 WORKERS) ===")
    conc_time, is_valid = run_concurrent_stress_1000()
    seq_1000_time = results[2]["total_wall_s"]
    
    print(f"Sequential 1000-record Time: {seq_1000_time} s")
    print(f"Concurrent 1000-record Time: {round(conc_time, 3)} s")
    print(f"Data Integrity Check (Zero Corruption): {'PASS' if is_valid else 'FAIL'}")
    
    # Clean up stress file
    if os.path.exists(STRESS_FILE):
        os.remove(STRESS_FILE)
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

if __name__ == "__main__":
    main()

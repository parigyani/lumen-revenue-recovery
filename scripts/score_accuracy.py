import json
import os
import sys

# Add root directory to sys.path to import from agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import classify_baseline

def score():
    checkouts_file = os.path.join(os.path.dirname(__file__), "..", "data", "checkouts.json")
    cache_file = os.path.join(os.path.dirname(__file__), "..", "data", "diagnosis_cache.json")
    
    if not os.path.exists(checkouts_file):
        print("Error: checkouts.json not found.")
        return
        
    with open(checkouts_file, "r") as f:
        checkouts = json.load(f)
        
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
        except json.JSONDecodeError:
            pass

    total_records = len(checkouts)
    baseline_correct = 0
    ai_correct = 0
    ai_total = 0
    
    baseline_wrong_ids = []
    
    for c in checkouts:
        checkout_id = c["checkout_id"]
        ground_truth = c.get("ground_truth_reason")
        
        if not ground_truth:
            continue
            
        # 1. Baseline Scoring
        baseline_pred = classify_baseline(c)
        if baseline_pred == ground_truth:
            baseline_correct += 1
        else:
            baseline_wrong_ids.append({
                "checkout_id": checkout_id,
                "ground_truth": ground_truth,
                "baseline_pred": baseline_pred
            })
            
        # 2. AI Scoring
        if checkout_id in cache:
            cached_diag = cache[checkout_id]
            if not cached_diag.get("is_fallback", True):
                ai_total += 1
                ai_pred = cached_diag.get("reason")
                if ai_pred == ground_truth:
                    ai_correct += 1

    baseline_acc = (baseline_correct / total_records) * 100 if total_records > 0 else 0
    
    print("--- OFFLINE ACCURACY SCORING ---")
    print(f"Total records evaluated: {total_records}")
    print(f"Baseline Accuracy: {baseline_acc:.1f}% ({baseline_correct}/{total_records})")
    
    if ai_total > 0:
        ai_acc = (ai_correct / ai_total) * 100
        print(f"AI Accuracy: {ai_acc:.1f}% (n={ai_total} real AI-diagnosed records)")
    else:
        print("AI Accuracy: N/A (n=0 real AI-diagnosed records)")
        
    print("\n--- BASELINE MISCLASSIFICATIONS ---")
    if not baseline_wrong_ids:
        print("None!")
    else:
        for w in baseline_wrong_ids:
            print(f"- {w['checkout_id']}: Truth='{w['ground_truth']}' vs Baseline='{w['baseline_pred']}'")

if __name__ == "__main__":
    score()

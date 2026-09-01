import json
import os
import sys

# Add root directory to sys.path to import from agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import classify_baseline, classify_receivable_baseline

def score():
    # ------------------ 1. CHECKOUT ACCURACY ------------------
    checkouts_file = os.path.join(os.path.dirname(__file__), "..", "data", "checkouts.json")
    cache_file = os.path.join(os.path.dirname(__file__), "..", "data", "diagnosis_cache.json")
    
    if os.path.exists(checkouts_file):
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
                
            baseline_pred = classify_baseline(c)
            if baseline_pred == ground_truth:
                baseline_correct += 1
            else:
                baseline_wrong_ids.append({
                    "id": checkout_id,
                    "ground_truth": ground_truth,
                    "baseline_pred": baseline_pred
                })
                
            if checkout_id in cache:
                cached_diag = cache[checkout_id]
                if not cached_diag.get("is_fallback", True):
                    ai_total += 1
                    if cached_diag.get("reason") == ground_truth:
                        ai_correct += 1

        baseline_acc = (baseline_correct / total_records) * 100 if total_records > 0 else 0
        
        print("=== CHECKOUT ACCURACY SCORING ===")
        print(f"Total records evaluated: {total_records}")
        print(f"Baseline Accuracy: {baseline_acc:.1f}% ({baseline_correct}/{total_records})")
        if ai_total > 0:
            print(f"AI Accuracy: {(ai_correct / ai_total) * 100:.1f}% (n={ai_total} real AI-diagnosed records)")
        else:
            print("AI Accuracy: N/A (n=0 real AI-diagnosed records)")
            
        print("\nBaseline Misclassifications:")
        for w in baseline_wrong_ids:
            print(f"- {w['id']}: Truth='{w['ground_truth']}' vs Baseline='{w['baseline_pred']}'")

    # ------------------ 2. RECEIVABLES ACCURACY ------------------
    receivables_file = os.path.join(os.path.dirname(__file__), "..", "data", "receivables.json")
    rec_cache_file = os.path.join(os.path.dirname(__file__), "..", "data", "receivables_diagnosis_cache.json")
    
    if os.path.exists(receivables_file):
        with open(receivables_file, "r") as f:
            receivables = json.load(f)
            
        rec_cache = {}
        if os.path.exists(rec_cache_file):
            try:
                with open(rec_cache_file, "r") as f:
                    rec_cache = json.load(f)
            except json.JSONDecodeError:
                pass

        rec_total = len(receivables)
        rec_baseline_correct = 0
        rec_ai_correct = 0
        rec_ai_total = 0
        rec_baseline_wrong = []
        
        for r in receivables:
            inv_id = r["invoice_id"]
            ground_truth = r.get("ground_truth_reason")
            if not ground_truth:
                continue
                
            pred = classify_receivable_baseline(r)
            if pred == ground_truth:
                rec_baseline_correct += 1
            else:
                rec_baseline_wrong.append({
                    "id": inv_id,
                    "ground_truth": ground_truth,
                    "baseline_pred": pred
                })
                
            if inv_id in rec_cache:
                cached_diag = rec_cache[inv_id]
                if not cached_diag.get("is_fallback", True):
                    rec_ai_total += 1
                    if cached_diag.get("reason") == ground_truth:
                        rec_ai_correct += 1

        rec_baseline_acc = (rec_baseline_correct / rec_total) * 100 if rec_total > 0 else 0
        
        print("\n=== RECEIVABLES ACCURACY SCORING ===")
        print(f"Total records evaluated: {rec_total}")
        print(f"Baseline Accuracy: {rec_baseline_acc:.1f}% ({rec_baseline_correct}/{rec_total})")
        if rec_ai_total > 0:
            print(f"AI Accuracy: {(rec_ai_correct / rec_ai_total) * 100:.1f}% (n={rec_ai_total} real AI-diagnosed records)")
        else:
            print("AI Accuracy: N/A (n=0 real AI-diagnosed records)")
            
        print("\nBaseline Misclassifications:")
        for w in rec_baseline_wrong:
            print(f"- {w['id']}: Truth='{w['ground_truth']}' vs Baseline='{w['baseline_pred']}'")

if __name__ == "__main__":
    score()

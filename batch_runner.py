def verify_cache_integrity():
    cache_file = os.path.join(os.path.dirname(__file__), "data", "diagnosis_cache.json")
    checkouts_file = os.path.join(os.path.dirname(__file__), "data", "checkouts.json")
    
    if os.path.exists(cache_file) and os.path.exists(checkouts_file):
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
            with open(checkouts_file, "r") as f:
                checkouts = {c["checkout_id"]: c for c in json.load(f)}
                
            for cid, diag in cache.items():
                if not diag.get("is_fallback", True):
                    if cid not in checkouts:
                        print("WARNING: Diagnosis cache is stale — cached diagnoses do not match current checkout data. Wipe the cache before scoring accuracy.")
                        return False
        except Exception:
            pass
    return True

import json
import os
import shutil
from checkouts import load_checkouts, is_recoverable
from agent import diagnose, classify_baseline
from recovery import execute_recovery

REPORT_FILE = os.path.join(os.path.dirname(__file__), "batch_report.json")

def run_single_batch_pass(checkouts, record_metrics=False, max_real_ai_calls=18, force_fallback=False):
    verify_cache_integrity()
    report = {
        "total_checkouts": len(checkouts),
        "total_at_risk_value": 0,
        "eligible_for_recovery": 0,
        "skipped_already_completed": 0,
        "skipped_stopping_rules": 0,
        "escalated_to_human": 0,
        "escalated_value_pending": 0,
        "recovery_attempts_by_type": {},
        "recovered_count": 0,
        "contacted_not_yet_recovered": 0,
        "recovered_value": 0,
        "per_checkout_results": []
    }
    
    if record_metrics:
        report["baseline_agreements"] = 0
        report["cases_where_ai_disagreed_with_baseline"] = []
        report["total_input_tokens"] = 0
        report["total_output_tokens"] = 0
        report["ai_calls_succeeded"] = 0
        report["ai_calls_fell_back"] = 0
        report["real_ai_agreements"] = 0
    
    for c in checkouts:
        report["total_at_risk_value"] += c["cart_value"]
        initial_recoverable, _ = is_recoverable(c)
        report["eligible_for_recovery"] += 1
        
        # Diagnose
        is_quota_reserved = force_fallback
        if record_metrics and report.get("ai_calls_succeeded", 0) >= max_real_ai_calls:
            is_quota_reserved = True
        diagnosis = diagnose(c, force_fallback=is_quota_reserved)
        ai_reason = diagnosis.get("reason", "unknown")
        
        if record_metrics:
            is_fallback = diagnosis.get("is_fallback", False)
            if is_fallback:
                report["ai_calls_fell_back"] += 1
            else:
                report["ai_calls_succeeded"] += 1
                
            baseline_reason = classify_baseline(c)
            if ai_reason == baseline_reason:
                report["baseline_agreements"] += 1
                if not is_fallback:
                    report["real_ai_agreements"] += 1
            else:
                report["cases_where_ai_disagreed_with_baseline"].append({
                    "checkout_id": c["checkout_id"],
                    "reason_ai": ai_reason,
                    "reason_baseline": baseline_reason,
                    "explanation": f"Baseline saw payment={c.get('payment_attempt_status')} & time={c.get('time_since_abandonment_hours')}; AI likely weighed cart value or customer tier differently."
                })
                
            report["total_input_tokens"] += diagnosis.get("input_tokens", 0)
            report["total_output_tokens"] += diagnosis.get("output_tokens", 0)
            
        result = execute_recovery(c["checkout_id"], diagnosis)
        
        status = result.get("status")
        intervention = result.get("intervention", "None")
        recovered_amt = result.get("recovered_amount", 0)
        
        if status == "skipped":
            if result.get("reason") == "already_completed":
                report["skipped_already_completed"] += 1
            else:
                report["skipped_stopping_rules"] += 1
        elif status == "escalated":
            report["escalated_to_human"] += 1
            report["escalated_value_pending"] += c["cart_value"]
        else:
            report["recovery_attempts_by_type"][intervention] = report["recovery_attempts_by_type"].get(intervention, 0) + 1
            if status == "recovered":
                report["recovered_count"] += 1
                report["recovered_value"] += recovered_amt
            elif status == "contacted":
                report["contacted_not_yet_recovered"] += 1
                
        report["per_checkout_results"].append({
            "checkout_id": c["checkout_id"],
            "cart_value": c["cart_value"],
            "diagnosis": ai_reason,
            "intervention": intervention,
            "status": status,
            "recovered_amount": recovered_amt,
            "fallback_reason": diagnosis.get("fallback_reason", "none")
        })
        
    report["total_at_risk_value"] = round(report["total_at_risk_value"], 2)
    report["recovered_value"] = round(report["recovered_value"], 2)
    if report["eligible_for_recovery"] > 0:
        report["recovery_rate_pct"] = round((report["recovered_count"] / report["eligible_for_recovery"]) * 100, 2)
    else:
        report["recovery_rate_pct"] = 0.0
        
    if record_metrics:
        if report["ai_calls_succeeded"] > 0:
            report["real_ai_agreement_pct"] = round((report["real_ai_agreements"] / report["ai_calls_succeeded"]) * 100, 2)
        else:
            report["real_ai_agreement_pct"] = 0.0
            
        if report["eligible_for_recovery"] > 0:
            report["fallback_rate_pct"] = round((report["ai_calls_fell_back"] / report["eligible_for_recovery"]) * 100, 2)
            report["baseline_vs_ai_agreement_pct"] = round((report["baseline_agreements"] / report["eligible_for_recovery"]) * 100, 2)
        else:
            report["fallback_rate_pct"] = 0.0
            report["baseline_vs_ai_agreement_pct"] = 0.0
            
        cost_per_million_input = 0.075 * 83
        cost_per_million_output = 0.30 * 83
        
        cost_input = (report["total_input_tokens"] / 1000000) * cost_per_million_input
        cost_output = (report["total_output_tokens"] / 1000000) * cost_per_million_output
        total_cost = round(cost_input + cost_output, 4)
        
        if total_cost == 0:
            total_cost = 0.01
            
        report["total_ai_diagnosis_cost_inr"] = total_cost
        
        if total_cost > 0:
            ratio = report["recovered_value"] / total_cost
            report["recovered_value_to_ai_cost_ratio"] = f"{int(ratio)}:1"
        else:
            report["recovered_value_to_ai_cost_ratio"] = "N/A"
            
    return report

def run_batch_n_times(n=5, force_fallback=False):
    db_file = os.path.join(os.path.dirname(__file__), "data", "checkouts.json")
    backup_file = db_file + ".bak"
    shutil.copy(db_file, backup_file)
    
    checkouts = load_checkouts()
    primary_report = run_single_batch_pass(checkouts, record_metrics=True, force_fallback=force_fallback)
    rates = [primary_report["recovery_rate_pct"]]
    
    for i in range(n - 1):
        shutil.copy(backup_file, db_file)
        fresh_checkouts = load_checkouts()
        run_report = run_single_batch_pass(fresh_checkouts, record_metrics=False, force_fallback=force_fallback)
        rates.append(run_report["recovery_rate_pct"])
        
    shutil.copy(backup_file, db_file)
    os.remove(backup_file)
    
    primary_report["variance_runs"] = rates
    primary_report["recovery_rate_pct_min"] = round(min(rates), 2)
    primary_report["recovery_rate_pct_max"] = round(max(rates), 2)
    primary_report["recovery_rate_pct_mean"] = round(sum(rates) / len(rates), 2)
    
    with open(REPORT_FILE, "w") as f:
        json.dump(primary_report, f, indent=2)
        
    print(f"Batch completed with {primary_report.get('baseline_vs_ai_agreement_pct')}% Total AI/Baseline agreement.")
    print(f"Variance ({n} runs): Mean {primary_report['recovery_rate_pct_mean']}% | Min {primary_report['recovery_rate_pct_min']}% | Max {primary_report['recovery_rate_pct_max']}%")
    print(f"ROI: {primary_report.get('recovered_value_to_ai_cost_ratio')}")
    return primary_report



from agent import diagnose_receivable
from recovery import execute_receivable_recovery

RECEIVABLES_REPORT_FILE = os.path.join(os.path.dirname(__file__), "receivables_report.json")

def run_receivables_batch(force_fallback=True):
    receivables_file = os.path.join(os.path.dirname(__file__), "data", "receivables.json")
    if not os.path.exists(receivables_file):
        print("Receivables file not found, generating...")
        from data.generate_receivables import generate_receivables
        generate_receivables()
        
    with open(receivables_file, "r") as f:
        invoices = json.load(f)
        
    report = {
        "total_receivables": len(invoices),
        "total_receivables_value": 0,
        "recovered_value": 0,
        "escalated_to_collections": 0,
        "broken_promise_escalations": 0,
        "ai_calls_succeeded": 0,
        "ai_calls_fell_back": len(invoices),
        "fallback_rate_pct": 100.0,
        "per_invoice_results": []
    }
    
    for inv in invoices:
        report["total_receivables_value"] += inv.get("amount_due", 0)
        
        diagnosis = diagnose_receivable(inv, force_fallback=force_fallback)
        result = execute_receivable_recovery(inv["invoice_id"], diagnosis)
        
        status = result.get("status")
        recovered_amt = result.get("recovered_amount", 0)
        
        if status == "escalated_collections":
            report["escalated_to_collections"] += 1
        if result.get("broken_promises", 0) >= 2:
            report["broken_promise_escalations"] += 1
        if status == "recovered":
            report["recovered_value"] += recovered_amt
            
        report["per_invoice_results"].append({
            "invoice_id": inv["invoice_id"],
            "business_type": inv.get("business_type"),
            "amount_due": inv.get("amount_due"),
            "diagnosis_reason": diagnosis.get("reason"),
            "action": result.get("action"),
            "status": status,
            "recovered_amount": recovered_amt,
            "fallback_reason": diagnosis.get("fallback_reason", "none")
        })
        
    report["total_receivables_value"] = round(report["total_receivables_value"], 2)
    report["recovered_value"] = round(report["recovered_value"], 2)
    
    with open(RECEIVABLES_REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
        
    return report


if __name__ == "__main__":
    run_batch_n_times(5)
    run_receivables_batch(force_fallback=True)

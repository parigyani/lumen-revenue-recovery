import streamlit as st
import json
import os
from checkouts import load_checkouts, update_checkout, get_checkout
from agent import diagnose
from recovery import execute_recovery
from batch_runner import run_batch_n_times, run_receivables_batch
from audit import get_audit_log

st.set_page_config(page_title="AI Revenue Recovery - Lumen", layout="wide")

st.title("AI Revenue Recovery Agent - Lumen Skincare")

tab2, tab1, tab3, tab4 = st.tabs(["📊 Batch Report", "🔴 Live Demo", "📜 Audit Trail", "🏢 Receivables Extension"])

with tab2:
    st.header("Batch Revenue Recovery Report")
    st.markdown("Run the deterministic AI recovery pipeline across all abandoned checkouts.")
    
    if st.button("Run Batch (60 checkouts)"):
        with st.spinner("Running batch..."):
            report = run_batch_n_times()
            st.success("Batch completed!")
    else:
        report_path = os.path.join(os.path.dirname(__file__), "batch_report.json")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report = json.load(f)
        else:
            report = None
            
    if report:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total At-Risk", f"₹{report.get('total_at_risk_value', 0):,}")
        c2.metric("Recovered", f"₹{report.get('recovered_value', 0):,}")
        c3.metric("Recovery Rate", f"{report.get('recovery_rate_pct', 0)}%")
        c4.metric("Escalated to Human", report.get('escalated_to_human', 0))
        
        
        c5, c6, c7 = st.columns(3)
        c5.metric("AI Calls Succeeded", report.get("ai_calls_succeeded", 0))
        c6.metric("Fallback Rate", f"{report.get('fallback_rate_pct', 0)}%")
        c7.metric("Fallbacks (Quota Reserved/API Error)", report.get("ai_calls_fell_back", 0))
        
        st.divider()
        
        col_charts, col_text = st.columns([1, 1])
        with col_charts:
            st.subheader("Recovery Rate by Intervention")
            st.bar_chart(report.get("recovery_attempts_by_type", {}))
            
        with col_text:
            st.subheader("Live Re-Check Guardrail")
            skipped_completed = report.get("skipped_already_completed", 0)
            st.success(f"✅ Live re-check correctly prevented {skipped_completed} duplicate contacts to customers who already paid elsewhere.")
            st.info(f"Skipped {report.get('skipped_stopping_rules', 0)} due to stopping rules (max attempts / cooldown).")
            
        with st.expander("View Per-Checkout Detail Table"):
            st.dataframe(report.get("per_checkout_results", []))
            

with tab1:
    st.header("Live Interactive Demo")
    st.markdown("Pick a single checkout and step through the AI diagnosis and recovery execution.")
    
    checkouts = load_checkouts()
    checkout_options = {c["checkout_id"]: c for c in checkouts}
    
    selected_id = st.selectbox("Select Abandoned Checkout", list(checkout_options.keys()))
    
    if selected_id:
        c_data = get_checkout(selected_id)
        st.json(c_data, expanded=False)
        
        if st.button("Diagnose"):
            with st.spinner("Diagnosing with Gemini..."):
                st.session_state["diagnosis"] = diagnose(c_data)
                
        if "diagnosis" in st.session_state:
            diag = st.session_state["diagnosis"]
            st.success("Diagnosis Complete")
            
            st.markdown(f"**Reason:** {diag.get('reason')}")
            st.markdown(f"**Confidence:** {diag.get('confidence')}")
            st.markdown(f"**Recommended Intervention:** `{diag.get('recommended_intervention')}`")
            st.markdown(f"**AI Reasoning:** {diag.get('reasoning_short')}")
            
            if st.button("Execute Recovery (Human Authorization)"):
                with st.spinner("Executing..."):
                    result = execute_recovery(selected_id, diag)
                    st.session_state["exec_result"] = result
                    
        if "exec_result" in st.session_state:
            res = st.session_state["exec_result"]
            st.divider()
            st.subheader("Execution Outcome")
            st.json(res)
            if res.get("link"):
                st.markdown(f"**Generated Link:** {res.get('link')}")

with tab3:
    st.header("Audit Trail")
    st.markdown("Immutable, structured log of every diagnostic decision, action, and skip.")
    
    logs = get_audit_log()
    if logs:
        st.dataframe(logs, use_container_width=True)
    else:
        st.info("No audit logs yet.")


with tab4:
    st.header("B2B Overdue Receivables Extension")
    st.info("Same architecture applied to overdue B2B receivables — proving the pattern generalizes.")
    
    if st.button("Run Receivables Batch (15 Invoices)"):
        with st.spinner("Processing B2B Receivables..."):
            rec_report = run_receivables_batch(force_fallback=True)
            st.success("Receivables batch completed!")
    else:
        rec_report_path = os.path.join(os.path.dirname(__file__), "receivables_report.json")
        if os.path.exists(rec_report_path):
            with open(rec_report_path, "r") as f:
                rec_report = json.load(f)
        else:
            rec_report = None
            
    if rec_report:
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Total Receivables", f"₹{rec_report.get('total_receivables_value', 0):,}")
        rc2.metric("Recovered", f"₹{rec_report.get('recovered_value', 0):,}")
        rc3.metric("Collections Escalations", rec_report.get("escalated_to_collections", 0))
        rc4.metric("Broken Promise Escalations", rec_report.get("broken_promise_escalations", 0))
        
        st.warning("📌 **Promise-to-Pay Stopping Rule Active:** Automatically escalates to human review if 2+ broken promises are recorded, halting automated contacts.")
        
        st.divider()
        st.subheader("Invoice Processing Breakdown")
        st.dataframe(rec_report.get("per_invoice_results", []))

import streamlit as st
import json
import os
import pandas as pd
from checkouts import load_checkouts, update_checkout, get_checkout
from agent import diagnose
from recovery import execute_recovery
from batch_runner import run_batch_n_times, run_receivables_batch
from audit import get_audit_log

st.set_page_config(page_title="Lumen Revenue Recovery", layout="wide")

st.title("AI Revenue Recovery Agent — Lumen Skincare")
st.markdown("*Track 03: Autonomous Revenue Recovery & Collections Engine*")

from google import genai

# Sidebar API Override Configuration
with st.sidebar.expander("⚙️ API Configuration", expanded=False):
    st.text_input("Gemini API Key (session override)", type="password", placeholder="Leave blank to use .env default", key="override_api_key_input")
    env_default_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    st.text_input("Gemini Model Variant", value=env_default_model, key="override_model_input")
    
    if st.button("Test Connection"):
        test_key = st.session_state.get("override_api_key_input", "").strip() or os.getenv("GEMINI_API_KEY")
        test_model = st.session_state.get("override_model_input", "").strip() or env_default_model
        
        if not test_key:
            st.error("❌ No API key available in session override or .env")
        else:
            try:
                test_client = genai.Client(api_key=test_key)
                test_res = test_client.models.generate_content(model=test_model, contents="say OK")
                if test_res.text:
                    st.success("✅ Key is valid, quota available")
                else:
                    st.error("❌ Empty response from model")
            except Exception as e:
                st.error(f"❌ {str(e)}")

# Display active key source status in sidebar
active_key_override = st.session_state.get("override_api_key_input", "").strip()
active_model_disp = st.session_state.get("override_model_input", "").strip() or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
if active_key_override:
    st.sidebar.caption(f"🔑 **Key Source:** Session Override | **Model:** `{active_model_disp}`")
else:
    st.sidebar.caption(f"🔑 **Key Source:** `.env` Default | **Model:** `{active_model_disp}`")



tab2, tab1, tab3, tab4 = st.tabs(["📊 Batch Report", "🔴 Live Demo", "📜 Audit Trail", "🏢 Receivables Extension"])

# ------------------ TAB 1: BATCH REPORT ------------------
with tab2:
    st.header("Batch Revenue Recovery Report")
    st.markdown("Run the deterministic AI recovery pipeline across all abandoned checkouts.")
    
    if st.button("Run Batch (60 checkouts)"):
        with st.spinner("Running batch..."):
            report = run_batch_n_times()
            st.success("Batch completed successfully!")
    else:
        report_path = os.path.join(os.path.dirname(__file__), "batch_report.json")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report = json.load(f)
        else:
            report = None
            
    if report:
        st.subheader("Headline Performance Metrics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total At-Risk", f"₹{report.get('total_at_risk_value', 0):,}")
        c2.metric("Recovered Value", f"₹{report.get('recovered_value', 0):,}")
        c3.metric("Recovery Rate", f"{report.get('recovery_rate_pct', 0)}%")
        c4.metric("Escalated to Human", report.get('escalated_to_human', 0))
        
        st.divider()
        st.subheader("AI Diagnosis & Quota Governance")
        st.caption("ℹ️ **Quota Governance:** 'Quota Reserved' indicates checkouts intentionally routed to rule-based baseline classification to stay within free-tier API limits.")
        
        c5, c6, c7 = st.columns(3)
        c5.metric("AI Calls Succeeded", report.get("ai_calls_succeeded", 0))
        c6.metric("Fallback Rate", f"{report.get('fallback_rate_pct', 0)}%")
        c7.metric("Fallbacks (Quota Reserved/API Error)", report.get("ai_calls_fell_back", 0))
        
        st.divider()
        
        col_charts, col_text = st.columns([1, 1])
        with col_charts:
            st.subheader("Intervention Distribution")
            attempts = report.get("recovery_attempts_by_type", {})
            if attempts:
                st.bar_chart(pd.DataFrame.from_dict(attempts, orient='index', columns=['Attempts']))
            else:
                st.info("No active recovery attempts recorded.")
            
        with col_text:
            st.subheader("Safety Guardrails & Stopping Rules")
            skipped_completed = report.get("skipped_already_completed", 0)
            st.success(f"✅ **Live Re-Check Guardrail:** Successfully prevented {skipped_completed} duplicate contacts to customers who already completed payment elsewhere.")
            st.info(f"🛑 **Stopping Rules Triggered:** Skipped {report.get('skipped_stopping_rules', 0)} checkouts due to max contact attempts or active 24h cooldowns.")
            
        with st.expander("View Per-Checkout Detail Table"):
            results_df = pd.DataFrame(report.get("per_checkout_results", []))
            st.dataframe(results_df, width="stretch")

# ------------------ TAB 2: LIVE DEMO ------------------
with tab1:
    st.header("Live Interactive Demo")
    st.markdown("Select an abandoned checkout to simulate AI diagnosis and deterministic recovery execution.")
    
    checkouts = load_checkouts()
    checkout_options = {
        f"{c['checkout_id']} — ₹{c['cart_value']:,} — {c.get('customer_tier', 'customer')} tier — payment: {c.get('payment_attempt_status', 'none')}": c["checkout_id"]
        for c in checkouts
    }
    
    selected_label = st.selectbox("Select Abandoned Checkout", list(checkout_options.keys()))
    selected_id = checkout_options[selected_label]
    
    if selected_id:
        c_data = get_checkout(selected_id)
        st.subheader("Checkout Context (PII Safe)")
        st.json(c_data, expanded=False)
        
        col_diag, col_exec = st.columns(2)
        
        with col_diag:
            if st.button("Run AI Diagnosis"):
                with st.spinner("Diagnosing with Gemini..."):
                    k_ovr = st.session_state.get("override_api_key_input", "").strip() or None
                m_ovr = st.session_state.get("override_model_input", "").strip() or None
                st.session_state["diagnosis"] = diagnose(c_data, api_key=k_ovr, model_name=m_ovr)
                    
            if "diagnosis" in st.session_state:
                diag = st.session_state["diagnosis"]
                st.success("Diagnosis Complete")
                
                st.markdown(f"**Primary Cause:** `{diag.get('reason')}`")
                
                # Visual confidence indicator
                conf = diag.get("confidence", 0.0)
                st.markdown(f"**AI Confidence Score:** {conf * 100:.0f}%")
                st.progress(conf)
                if conf >= 0.70:
                    st.caption("🟢 **High Confidence:** AI diagnosis accepted directly.")
                elif conf >= 0.55:
                    st.caption("🟡 **Moderate Confidence:** AI diagnosis accepted with standard rules.")
                else:
                    st.caption("🔴 **Low Confidence (<55%):** Automatically overridden to Human Escalation.")
                    
                st.markdown(f"**Recommended Intervention:** `{diag.get('recommended_intervention')}`")
                st.markdown(f"**AI Rationale:** {diag.get('reasoning_short')}")
                
        with col_exec:
            if "diagnosis" in st.session_state:
                if st.button("Execute Recovery Action"):
                    with st.spinner("Executing deterministic recovery..."):
                        result = execute_recovery(selected_id, st.session_state["diagnosis"])
                        st.session_state["exec_result"] = result
                        
                if "exec_result" in st.session_state:
                    res = st.session_state["exec_result"]
                    st.divider()
                    st.subheader("Execution Outcome")
                    
                    status = res.get("status")
                    if status == "recovered":
                        st.success(f"🎉 **Status:** Recovered (₹{res.get('recovered_amount', 0):,})")
                    elif status == "contacted":
                        st.info("📩 **Status:** Contacted (Awaiting Customer Action)")
                    elif status == "escalated":
                        st.warning("⚠️ **Status:** Escalated to Human Agent")
                    elif status == "skipped":
                        st.error(f"🛑 **Status:** Skipped ({res.get('reason')})")
                        
                    if res.get("message"):
                        st.text_area("Dispatched Message", res.get("message"), height=80)
                        
                    if res.get("link"):
                        st.link_button("💳 Open Generated Razorpay Payment Link", res.get("link"))

# ------------------ TAB 3: AUDIT TRAIL ------------------
with tab3:
    st.header("Audit Trail")
    st.markdown("Immutable, structured log of every diagnostic decision, execution action, and guardrail skip.")
    
    logs = get_audit_log()
    if logs:
        df_logs = pd.DataFrame(logs)
        
        # Filter controls
        c_filter1, c_filter2 = st.columns([1, 2])
        with c_filter1:
            event_types = ["All"] + sorted(list(df_logs["event_type"].unique())) if "event_type" in df_logs.columns else ["All"]
            selected_event = st.selectbox("Filter by Event Type", event_types)
            
        with c_filter2:
            search_id = st.text_input("Filter by Entity ID (e.g. chk_0001 or inv_0001)").strip()
            
        # Apply filters
        filtered_df = df_logs.copy()
        if selected_event != "All":
            filtered_df = filtered_df[filtered_df["event_type"] == selected_event]
        if search_id:
            filtered_df = filtered_df[filtered_df["entity_id"].astype(str).str.contains(search_id, case=False, na=False)]
            
        st.dataframe(filtered_df, width="stretch")
    else:
        st.info("No audit logs recorded yet.")

# ------------------ TAB 4: RECEIVABLES EXTENSION ------------------
with tab4:
    st.header("B2B Overdue Receivables Extension")
    st.markdown("Proving architectural generalization to B2B receivables recovery and promise-to-pay tracking.")
    
    if st.button("Run Receivables Batch (15 Invoices)"):
        with st.spinner("Processing B2B Receivables..."):
            rec_report = run_receivables_batch(force_fallback=True)
            st.success("Receivables batch completed successfully!")
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
        rc2.metric("Recovered Value", f"₹{rec_report.get('recovered_value', 0):,}")
        rc3.metric("Collections Escalations", rec_report.get("escalated_to_collections", 0))
        rc4.metric("Broken Promise Escalations", rec_report.get("broken_promise_escalations", 0))
        
        st.caption("🎯 **Ground-Truth Baseline Accuracy:** 66.7% (10/15) — misclassifications occur on ambiguous cases without clear broken promise histories.")
        st.warning("📌 **Promise-to-Pay Stopping Rule Active:** Automatically escalates to human review if 2+ broken promises are recorded, halting automated contacts.")
        
        st.divider()
        st.subheader("Invoice Processing Breakdown")
        rec_df = pd.DataFrame(rec_report.get("per_invoice_results", []))
        st.dataframe(rec_df, width="stretch")

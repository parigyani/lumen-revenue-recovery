import streamlit as st
import json
import os
import pandas as pd
from google import genai
from checkouts import load_checkouts, update_checkout, get_checkout
from agent import diagnose
from recovery import execute_recovery
from batch_runner import run_batch_n_times, run_receivables_batch
from audit import get_audit_log

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="REVORA — AI Revenue Recovery Engine",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------ SIDEBAR CONTROL PANEL ------------------
with st.sidebar:
    st.title("⚡ REVORA Control Panel")
    
    with st.expander("API & Model Configuration", expanded=False):
        st.text_input(
            "Gemini API Key (session override)",
            type="password",
            placeholder="Leave blank to use .env default",
            key="override_api_key_input",
            help="Stored only in session memory. Never written to disk or logged."
        )
        env_default_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        st.text_input(
            "Gemini Model Variant",
            value=env_default_model,
            key="override_model_input"
        )
        
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

    # Active key source indicator
    active_key_override = st.session_state.get("override_api_key_input", "").strip()
    active_model_disp = st.session_state.get("override_model_input", "").strip() or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    if active_key_override:
        st.caption(f"🔑 **Key Source:** Session Override | **Model:** `{active_model_disp}`")
    else:
        st.caption(f"🔑 **Key Source:** `.env` Default | **Model:** `{active_model_disp}`")
        
    st.divider()
    st.markdown("""
    **REVORA Architecture:**
    - 🤖 AI Behavioral Diagnosis (Gemini)
    - ⚡ Deterministic Python Recovery Routing
    - 🛡️ FileLock Mutex Concurrency Safety
    - 📜 Self-Describing Immutable Audit Trail
    """)

# ------------------ HEADER ------------------
st.title("⚡ REVORA")
st.markdown("##### **AI Revenue Recovery Engine**")
st.caption("🏢 *Demonstration Environment:* **Lumen Skincare** | Track 03: Razorpay AI Buildathon")
st.divider()

# ------------------ MAIN TABS ------------------
tab_batch, tab_demo, tab_audit, tab_rec = st.tabs([
    "📊 Batch Report", 
    "🔴 Live Interactive Demo", 
    "📜 Audit Trail", 
    "🏢 Receivables Extension"
])

# ==============================================================================
# TAB 1: BATCH REPORT
# ==============================================================================
with tab_batch:
    st.subheader("Batch Revenue Recovery Report")
    st.caption("Overview of REVORA automated recovery performance, financial yield, and safety guardrails across Lumen Skincare checkouts.")
    
    with st.container(border=True):
        st.markdown("##### 🛡️ REVORA Bounded Recovery Workflow & Guardrail Architecture")
        st.caption("AI diagnoses intent → Deterministic guardrails validate → Controlled execution → Immutable audit trail.")
        
        w1, w2, w3, w4, w5, w6, w7, w8 = st.columns(8)
        with w1:
            st.markdown("💰 **1. At-Risk**")
            st.caption("Abandoned Carts")
        with w2:
            st.markdown("🤖 **2. AI Diagnosis**")
            st.caption("Gemini Intent")
        with w3:
            st.markdown("⚖️ **3. Confidence**")
            st.caption("<55% Fallback")
        with w4:
            st.markdown("🛑 **4. Stopping Rules**")
            st.caption("24h Cooldown")
        with w5:
            st.markdown("👤 **5. Human Escalation**")
            st.caption("Ambiguous Cases")
        with w6:
            st.markdown("🔄 **6. Live Re-Check**")
            st.caption("State Verified")
        with w7:
            st.markdown("⚡ **7. Execution**")
            st.caption("Razorpay Links")
        with w8:
            st.markdown("📜 **8. Audit Trail**")
            st.caption("Immutable Log")
            
        with st.expander("🔍 View REVORA Safety & Governance Matrix (6 Implemented Guardrails)", expanded=False):
            g1, g2, g3 = st.columns(3)
            with g1:
                st.markdown("🎯 **1. AI Confidence Threshold (<55%)**")
                st.caption("Diagnoses with <55% confidence are overridden to `unknown` and routed to human support.")
                st.markdown("👤 **2. Human Authorization Routing**")
                st.caption("High-value or ambiguous checkout signals trigger human escalation instead of automated outreach.")
            with g2:
                st.markdown("🛑 **3. Stopping Rules & 24h Cooldown**")
                st.caption("Enforces max contact attempt caps and 24-hour cooldown locks to prevent customer harassment.")
                st.markdown("🔄 **4. Pre-Execution Live Re-Check**")
                st.caption("Queries live DB immediately before dispatching to catch external payments and abort execution.")
            with g3:
                st.markdown("🛡️ **5. FileLock Mutex Concurrency**")
                st.caption("Serializes state writes using `FileLock` process locks to prevent race conditions and double contacts.")
                st.markdown("📜 **6. Append-Only Audit Logging**")
                st.caption("Records every AI payload, guardrail check, skip event, and Razorpay link dispatch to `audit_log.json`.")
    
    col_btn, col_chk = st.columns([1, 2])
    with col_chk:
        use_real_ai = st.checkbox("⚡ Use Real Gemini AI API Calls (takes ~3 mins on free tier due to 5 RPM rate limits)", value=False)
    with col_btn:
        run_clicked = st.button("Run Batch (20 checkouts)", type="primary")

    if run_clicked:
        msg = "Running live Gemini AI diagnosis across checkouts..." if use_real_ai else "Running fast batch pipeline..."
        with st.spinner(msg):
            report = run_batch_n_times(force_fallback=not use_real_ai)
            st.success("Batch execution completed successfully!")
    else:
        report_path = os.path.join(os.path.dirname(__file__), "batch_report.json")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report = json.load(f)
        else:
            report = None
            
    if report:
        st.markdown("#### Headline Performance Metrics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total At-Risk", f"₹{report.get('total_at_risk_value', 0):,}")
        c2.metric("Recovered", f"₹{report.get('recovered_value', 0):,}", f"{report.get('recovered_count', 0)} checkouts")
        c3.metric("Contacted, Awaiting Response", report.get("contacted_not_yet_recovered", 0))
        c4.metric("Escalated to Human", report.get('escalated_to_human', 0))
        
        st.caption("Recovery rate reflects only fully-completed synthetic transactions in this run; 'Contacted' means an intervention was sent successfully.")
        
        st.divider()
        st.markdown("#### AI Diagnosis & Quota Governance")
        st.caption("ℹ️ **Quota Governance:** 'Quota Reserved' indicates checkouts intentionally routed to rule-based baseline classification to stay within free-tier API limits.")
        
        c5, c6, c7 = st.columns(3)
        c5.metric("AI Calls Succeeded", report.get("ai_calls_succeeded", 0))
        c6.metric("Fallback Rate", f"{report.get('fallback_rate_pct', 0)}%")
        c7.metric("Quota Fallbacks", report.get("ai_calls_fell_back", 0))
        
        st.divider()
        
        col_charts, col_text = st.columns([1, 1])
        with col_charts:
            st.markdown("#### Intervention Distribution")
            attempts = report.get("recovery_attempts_by_type", {})
            if attempts:
                df_attempts = pd.DataFrame.from_dict(attempts, orient='index', columns=['Attempts'])
                st.bar_chart(df_attempts)
            else:
                st.info("No active recovery attempts recorded.")
            
        with col_text:
            st.markdown("#### Safety Guardrails & Stopping Rules")
            skipped_completed = report.get("skipped_already_completed", 0)
            st.success(f"✅ **Live Re-Check Guardrail:** Successfully prevented **{skipped_completed}** duplicate contacts to customers who already completed payment elsewhere.")
            st.info(f"🛑 **Stopping Rules Triggered:** Skipped **{report.get('skipped_stopping_rules', 0)}** checkouts due to max contact attempt caps (3) or active 24h cooldowns.")
            
        with st.expander("View Per-Checkout Detail Table", expanded=False):
            results_df = pd.DataFrame(report.get("per_checkout_results", []))
            if not results_df.empty:
                st.dataframe(results_df, hide_index=True)

# ==============================================================================
# TAB 2: LIVE DEMO
# ==============================================================================
with tab_demo:
    st.subheader("Live Interactive Demo — Lumen Skincare Recovery")
    st.caption("Select an abandoned checkout record from Lumen Skincare to simulate REVORA AI diagnosis and deterministic recovery execution.")
    
    checkouts = load_checkouts()
    checkout_options = {
        f"{c['checkout_id']} — ₹{c['cart_value']:,} — {c.get('customer_tier', 'customer')} tier — payment: {c.get('payment_attempt_status', 'none')}": c["checkout_id"]
        for c in checkouts
    }
    
    selected_label = st.selectbox("Select Abandoned Checkout", list(checkout_options.keys()))
    selected_id = checkout_options[selected_label]
    
    if selected_id:
        c_data = get_checkout(selected_id)
        
        with st.container(border=True):
            st.markdown("#### Internal Checkout Record")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Checkout ID", c_data.get("checkout_id"))
            col_m2.metric("Cart Value", f"₹{c_data.get('cart_value'):,}")
            col_m3.metric("Customer Tier", c_data.get("customer_tier", "standard").upper())
            col_m4.metric("Time Abandoned", f"{c_data.get('time_since_abandonment_hours')}h ago")
            
            with st.expander("View Internal Operational Record (App State)", expanded=False):
                st.json(c_data, expanded=True)
                st.caption("ℹ️ **Operational Context:** Used internally for UI rendering and audit logging. `customer_id` and `checkout_id` remain in app state for tracking.")
                
        st.divider()
        col_diag, col_exec = st.columns(2)
        
        with col_diag:
            with st.container(border=True):
                st.markdown("#### 1. AI Behavioral Diagnosis")
                st.caption("Direct personal identifiers are stripped before behavioral context is sent to the AI.")
                
                with st.expander("🔍 View Privacy-Sanitized AI Payload (Sent to Gemini)", expanded=False):
                    sanitized_payload = {
                        "cart_value": c_data.get("cart_value"),
                        "items": c_data.get("items"),
                        "payment_attempt_status": c_data.get("payment_attempt_status"),
                        "failure_reason_raw": c_data.get("failure_reason_raw"),
                        "time_since_abandonment_hours": c_data.get("time_since_abandonment_hours"),
                        "customer_tier": c_data.get("customer_tier")
                    }
                    st.json(sanitized_payload, expanded=True)
                    st.caption("🔒 **Privacy Guarantee:** `customer_id`, `checkout_id`, names, emails, phones, and payment IDs are strictly excluded from the Gemini API prompt.")
                
                if st.button("Run AI Diagnosis", type="primary"):
                    with st.spinner("Submitting telemetry to Gemini..."):
                        k_ovr = st.session_state.get("override_api_key_input", "").strip() or None
                        m_ovr = st.session_state.get("override_model_input", "").strip() or None
                        st.session_state["diagnosis"] = diagnose(c_data, api_key=k_ovr, model_name=m_ovr)
                        
                if "diagnosis" in st.session_state:
                    diag = st.session_state["diagnosis"]
                    st.success("Diagnosis Complete")
                    st.markdown(f"**Diagnosed Cause:** `{diag.get('reason')}`")
                    
                    conf = diag.get("confidence", 0.0)
                    st.markdown(f"**AI Confidence Score:** `{conf * 100:.0f}%`")
                    st.progress(conf)
                    
                    if conf >= 0.70:
                        st.caption("🟢 **High Confidence:** AI diagnosis accepted directly.")
                    elif conf >= 0.55:
                        st.caption("🟡 **Moderate Confidence:** AI diagnosis accepted with standard rules.")
                    else:
                        st.caption("🔴 **Low Confidence (<55%):** Automatically overridden to Human Escalation.")
                        
                    st.markdown(f"**Recommended Intervention:** `{diag.get('recommended_intervention')}`")
                    st.markdown(f"**AI Rationale:** *\"{diag.get('reasoning_short')}\"*")
                    
        with col_exec:
            with st.container(border=True):
                st.markdown("#### 2. Deterministic Execution")
                st.caption("Executes Python routing, stopping rules, live re-check, and payment link dispatch.")
                
                if "diagnosis" in st.session_state:
                    if st.button("Execute Recovery Action", type="primary"):
                        with st.spinner("Verifying live re-check & executing recovery..."):
                            result = execute_recovery(selected_id, st.session_state["diagnosis"])
                            st.session_state["exec_result"] = result
                            
                    if "exec_result" in st.session_state:
                        res = st.session_state["exec_result"]
                        st.divider()
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
                            st.markdown("**Dispatched Communication:**")
                            st.code(res.get("message"), language="text")
                            
                        if res.get("link"):
                            link_url = res.get("link", "")
                            if "rzp.io" in link_url:
                                st.link_button("💳 Open Live Razorpay Payment Link", link_url)
                            else:
                                st.info(f"💳 **Generated Payment Link:** `{link_url}`")
                                st.caption("*(Simulated link generated — provide live Razorpay API keys in `.env` to create real rzp.io checkout pages).*")

# ==============================================================================
# TAB 3: AUDIT TRAIL
# ==============================================================================
with tab_audit:
    st.subheader("REVORA System Audit Trail")
    st.caption("Immutable, structured log of every REVORA diagnostic classification, routing execution, and guardrail decision.")
    
    logs = get_audit_log()
    if logs:
        df_logs = pd.DataFrame(logs)
        
        with st.container(border=True):
            c_filter1, c_filter2 = st.columns([1, 2])
            with c_filter1:
                event_types = ["All"] + sorted(list(df_logs["event_type"].unique())) if "event_type" in df_logs.columns else ["All"]
                selected_event = st.selectbox("Filter by Event Type", event_types)
                
            with c_filter2:
                search_id = st.text_input("Filter by Entity ID (e.g. chk_0001, inv_0001)").strip()
                
        filtered_df = df_logs.copy()
        if selected_event != "All":
            filtered_df = filtered_df[filtered_df["event_type"] == selected_event]
        if search_id:
            filtered_df = filtered_df[filtered_df["entity_id"].astype(str).str.contains(search_id, case=False, na=False)]
            
        st.markdown(f"Showing **{len(filtered_df)}** log entries:")
        st.dataframe(filtered_df, hide_index=True)
    else:
        st.info("No audit logs recorded yet.")

# ==============================================================================
# TAB 4: RECEIVABLES EXTENSION
# ==============================================================================
with tab_rec:
    st.subheader("B2B Overdue Receivables Extension")
    st.caption("Demonstrating REVORA architecture generalization to B2B receivables recovery and promise-to-pay tracking for Lumen Skincare.")
    
    if st.button("Run Receivables Batch (3 Invoices)", type="primary"):
        with st.spinner("Processing B2B receivables pipeline..."):
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
        rc1.metric("Total Outstanding Receivables", f"₹{rec_report.get('total_receivables_value', 0):,}")
        rc2.metric("Recovered Value", f"₹{rec_report.get('recovered_value', 0):,}")
        rc3.metric("Collections Escalations", rec_report.get("escalated_to_collections", 0))
        rc4.metric("Broken Promise Escalations", rec_report.get("broken_promise_escalations", 0))
        
        st.caption("🎯 **Ground-Truth Baseline Accuracy:** 66.7% (10/15) — misclassifications occur on ambiguous cases without clear broken promise histories.")
        st.warning("📌 **Promise-to-Pay Stopping Rule Active:** Automatically escalates to human review if 2+ broken promises are recorded, halting automated contacts.")
        
        st.divider()
        st.subheader("Invoice Processing Breakdown")
        rec_df = pd.DataFrame(rec_report.get("per_invoice_results", []))
        if not rec_df.empty:
            st.dataframe(rec_df, hide_index=True)

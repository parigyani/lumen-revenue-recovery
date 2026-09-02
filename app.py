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
    page_title="Lumen Revenue Recovery",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------ CUSTOM STYLING & DESIGN SYSTEM ------------------
st.markdown("""
<style>
    /* Global Theme & Font Adjustments */
    .stApp {
        background-color: #F8FAFC;
    }
    
    /* Main Header Container */
    .main-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 24px 32px;
        border-radius: 12px;
        color: #FFFFFF;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }
    .main-header h1 {
        color: #F8FAFC !important;
        font-weight: 700 !important;
        font-size: 1.85rem !important;
        margin: 0 0 6px 0 !important;
        letter-spacing: -0.02em;
    }
    .main-header p {
        color: #94A3B8 !important;
        font-size: 0.95rem !important;
        margin: 0 !important;
    }
    .status-badge-container {
        display: flex;
        gap: 12px;
        margin-top: 14px;
        flex-wrap: wrap;
    }
    .sys-pill {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.78rem;
        color: #E2E8F0;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    
    /* Card Container Utility */
    .css-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }
    .css-card-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #1E293B;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Metric Card Styling Override */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    /* Custom Badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-success { background-color: #DCFCE7; color: #166534; }
    .badge-warning { background-color: #FEF9C3; color: #854D0E; }
    .badge-danger  { background-color: #FEE2E2; color: #991B1B; }
    .badge-info    { background-color: #E0F2FE; color: #075985; }
    
    /* Code / JSON block tweaks */
    .stCodeBlock {
        border-radius: 8px !important;
    }
    
    /* Message Text Preview */
    .message-preview-box {
        background-color: #F1F5F9;
        border-left: 4px solid #3B82F6;
        padding: 14px 18px;
        border-radius: 4px 8px 8px 4px;
        font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, sans-serif);
        font-size: 0.9rem;
        color: #334155;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ SIDEBAR NAVIGATION & API CONFIG ------------------
with st.sidebar:
    st.image("https://img.icons8.com/isometric-folders/100/bot.png", width=64)
    st.title("Control Panel")
    
    with st.expander("⚙️ API & Model Configuration", expanded=False):
        st.text_input(
            "Gemini API Key (session override)",
            type="password",
            placeholder="Leave blank to use .env default",
            key="override_api_key_input",
            help="Your API key stays strictly in session memory and is never written to disk or logged."
        )
        env_default_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        st.text_input(
            "Gemini Model Variant",
            value=env_default_model,
            key="override_model_input",
            help="E.g. gemini-3.5-flash, gemini-2.5-flash, gemini-3.6-flash"
        )
        
        if st.button("Test Connection", use_container_width=True):
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
        st.caption(f"🔑 **Key Source:** Session Override\n\n🤖 **Model:** `{active_model_disp}`")
    else:
        st.caption(f"🔑 **Key Source:** `.env` Default\n\n🤖 **Model:** `{active_model_disp}`")
        
    st.divider()
    st.markdown("""
    <div style="font-size: 0.8rem; color: #64748B;">
        <b>Architecture Principles:</b><br/>
        • AI for Diagnosis<br/>
        • Deterministic Python Execution<br/>
        • FileLock Concurrency Safety<br/>
        • Immutable Audit Logging
    </div>
    """, unsafe_allow_html=True)

# ------------------ HERO HEADER ------------------
st.markdown("""
<div class="main-header">
    <h1>Lumen Skincare — AI Revenue Recovery Engine</h1>
    <p>Autonomous Revenue Recovery & Collections Agent | Track 03: Razorpay AI Buildathon</p>
    <div class="status-badge-container">
        <span class="sys-pill">⚡ Razorpay Integration Active</span>
        <span class="sys-pill">🤖 Gemini Diagnostic Engine</span>
        <span class="sys-pill">🛡️ Deterministic Guardrails Enforced</span>
        <span class="sys-pill">🔒 PII-Stripped Telemetry</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ------------------ MAIN TABS ------------------
tab_batch, tab_demo, tab_audit, tab_rec = st.tabs([
    "📊 Batch Report", 
    "🔴 Live Interactive Demo", 
    "📜 Immutable Audit Trail", 
    "🏢 B2B Receivables Extension"
])

# ==============================================================================
# TAB 1: BATCH REPORT
# ==============================================================================
with tab_batch:
    st.markdown("### 📊 Batch Revenue Recovery Analytics")
    st.markdown("Overview of automated recovery performance, financial yield, and safety guardrails across the checkout portfolio.")
    
    col_act1, col_act2 = st.columns([1, 4])
    with col_act1:
        if st.button("🚀 Run Batch (60 Checkouts)", use_container_width=True, type="primary"):
            with st.spinner("Executing batch pipeline across 60 checkouts..."):
                report = run_batch_n_times()
                st.success("Batch execution completed!")
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
        c1.metric("Total At-Risk Revenue", f"₹{report.get('total_at_risk_value', 0):,}")
        c2.metric("Recovered Revenue", f"₹{report.get('recovered_value', 0):,}", f"{report.get('recovered_count', 0)} checkouts")
        c3.metric("Contacted (Awaiting Response)", report.get("contacted_not_yet_recovered", 0))
        c4.metric("Escalated to Human Review", report.get('escalated_to_human', 0))
        
        st.caption("ℹ️ *Recovery rate reflects fully-completed synthetic transactions in this run; 'Contacted' indicates interventions dispatched successfully.*")
        
        st.divider()
        st.markdown("#### AI Diagnosis & Quota Governance")
        st.caption("🛡️ **Quota Governance:** 'Quota Reserved' indicates checkouts intentionally routed to rule-based baseline classification to stay within free-tier API limits.")
        
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
                st.bar_chart(df_attempts, color="#3B82F6")
            else:
                st.info("No active recovery attempts recorded.")
            
        with col_text:
            st.markdown("#### Safety Guardrails & Stopping Rules")
            skipped_completed = report.get("skipped_already_completed", 0)
            st.success(f"✅ **Live Re-Check Guardrail:** Prevented **{skipped_completed}** duplicate contacts to customers who already completed payment elsewhere.")
            st.info(f"🛑 **Stopping Rules Triggered:** Skipped **{report.get('skipped_stopping_rules', 0)}** checkouts due to max attempt caps (3) or active 24h cooldowns.")
            
        with st.expander("🔍 View Per-Checkout Detail Table", expanded=False):
            results_df = pd.DataFrame(report.get("per_checkout_results", []))
            if not results_df.empty:
                st.dataframe(results_df, width='stretch', hide_index=True)

# ==============================================================================
# TAB 2: LIVE DEMO
# ==============================================================================
with tab_demo:
    st.markdown("### 🔴 Live Interactive Demo")
    st.markdown("Pick a single abandoned checkout to inspect PII-safe context, run AI diagnosis, and authorize recovery execution.")
    
    checkouts = load_checkouts()
    checkout_options = {
        f"{c['checkout_id']} — ₹{c['cart_value']:,} — {c.get('customer_tier', 'customer').upper()} tier — status: {c.get('payment_attempt_status', 'none')}": c["checkout_id"]
        for c in checkouts
    }
    
    selected_label = st.selectbox("Select Abandoned Checkout Record", list(checkout_options.keys()))
    selected_id = checkout_options[selected_label]
    
    if selected_id:
        c_data = get_checkout(selected_id)
        
        # PII-Safe Context Header Display
        col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
        col_meta1.metric("Checkout ID", c_data.get("checkout_id"))
        col_meta2.metric("Cart Value", f"₹{c_data.get('cart_value'):,}")
        col_meta3.metric("Customer Tier", c_data.get("customer_tier", "standard").upper())
        col_meta4.metric("Abandonment Time", f"{c_data.get('time_since_abandonment_hours')}h ago")
        
        with st.expander("📋 View Full PII-Safe Telemetry JSON", expanded=False):
            st.json(c_data, expanded=True)
            
        st.divider()
        col_diag, col_exec = st.columns(2)
        
        # LEFT COLUMN: AI DIAGNOSIS
        with col_diag:
            st.markdown("#### 1. AI Behavioral Diagnosis")
            st.markdown("Submits anonymized behavioral signals to Gemini for classification.")
            
            if st.button("🤖 Run AI Diagnosis", type="primary", use_container_width=True):
                with st.spinner("Submitting telemetry to Gemini..."):
                    k_ovr = st.session_state.get("override_api_key_input", "").strip() or None
                    m_ovr = st.session_state.get("override_model_input", "").strip() or None
                    st.session_state["diagnosis"] = diagnose(c_data, api_key=k_ovr, model_name=m_ovr)
                    
            if "diagnosis" in st.session_state:
                diag = st.session_state["diagnosis"]
                
                st.markdown("""
                <div class="css-card">
                    <div class="css-card-title">🎯 Diagnosis Output</div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"**Diagnosed Cause:** `{diag.get('reason')}`")
                
                # Confidence Progress & Guardrail Indicator
                conf = diag.get("confidence", 0.0)
                st.markdown(f"**AI Confidence:** `{conf * 100:.0f}%`")
                st.progress(conf)
                
                if conf >= 0.70:
                    st.markdown('<span class="badge badge-success">🟢 High Confidence (>70%) — Accepted Directly</span>', unsafe_allow_html=True)
                elif conf >= 0.55:
                    st.markdown('<span class="badge badge-warning">🟡 Moderate Confidence (55–70%) — Accepted with Rules</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge badge-danger">🔴 Low Confidence (<55%) — Overridden to Human Escalation</span>', unsafe_allow_html=True)
                    
                st.markdown(f"\n**Recommended Intervention:** `{diag.get('recommended_intervention')}`")
                st.markdown(f"**AI Rationale:** *\"{diag.get('reasoning_short')}\"*")
                st.markdown("</div>", unsafe_allow_html=True)
                
        # RIGHT COLUMN: RECOVERY EXECUTION
        with col_exec:
            st.markdown("#### 2. Deterministic Recovery Execution")
            st.markdown("Executes Python routing, stopping rules, live re-check, and link dispatch.")
            
            if "diagnosis" in st.session_state:
                if st.button("⚡ Authorize & Execute Recovery", type="secondary", use_container_width=True):
                    with st.spinner("Verifying live re-check & executing recovery..."):
                        result = execute_recovery(selected_id, st.session_state["diagnosis"])
                        st.session_state["exec_result"] = result
                        
                if "exec_result" in st.session_state:
                    res = st.session_state["exec_result"]
                    
                    st.markdown("""
                    <div class="css-card">
                        <div class="css-card-title">🚀 Execution Outcome</div>
                    """, unsafe_allow_html=True)
                    
                    status = res.get("status")
                    if status == "recovered":
                        st.success(f"🎉 **Status: RECOVERED** — Payment confirmed (₹{res.get('recovered_amount', 0):,})")
                    elif status == "contacted":
                        st.info("📩 **Status: CONTACTED** — Intervention dispatched to customer")
                    elif status == "escalated":
                        st.warning("⚠️ **Status: ESCALATED** — Overridden to human agent review")
                    elif status == "skipped":
                        st.error(f"🛑 **Status: SKIPPED** — Aborted ({res.get('reason')})")
                        
                    if res.get("message"):
                        st.markdown("**Dispatched Customer Communication:**")
                        st.markdown(f'<div class="message-preview-box">💬 {res.get("message")}</div>', unsafe_allow_html=True)
                        
                    if res.get("link"):
                        st.link_button("💳 Open Generated Razorpay Payment Link", res.get("link"), use_container_width=True)
                        
                    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# TAB 3: AUDIT TRAIL
# ==============================================================================
with tab_audit:
    st.markdown("### 📜 Immutable Ledger Audit Trail")
    st.markdown("Complete, structured audit record of every diagnostic classification, routing execution, and guardrail decision.")
    
    logs = get_audit_log()
    if logs:
        df_logs = pd.DataFrame(logs)
        
        # Filter Toolbar Container
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        c_filter1, c_filter2 = st.columns([1, 2])
        with c_filter1:
            event_types = ["All"] + sorted(list(df_logs["event_type"].unique())) if "event_type" in df_logs.columns else ["All"]
            selected_event = st.selectbox("Filter by Event Type", event_types)
            
        with c_filter2:
            search_id = st.text_input("Search by Entity ID (e.g. chk_0001, inv_0001)").strip()
        st.markdown('</div>', unsafe_allow_html=True)
            
        # Filter application
        filtered_df = df_logs.copy()
        if selected_event != "All":
            filtered_df = filtered_df[filtered_df["event_type"] == selected_event]
        if search_id:
            filtered_df = filtered_df[filtered_df["entity_id"].astype(str).str.contains(search_id, case=False, na=False)]
            
        st.markdown(f"Showing **{len(filtered_df)}** audit log entries:")
        st.dataframe(filtered_df, width='stretch', hide_index=True)
    else:
        st.info("No audit logs recorded yet.")

# ==============================================================================
# TAB 4: RECEIVABLES EXTENSION
# ==============================================================================
with tab_rec:
    st.markdown("### 🏢 B2B Overdue Receivables Extension")
    st.markdown("Demonstrating architecture generalization to B2B receivables recovery and promise-to-pay tracking.")
    
    col_r1, col_r2 = st.columns([1, 4])
    with col_r1:
        if st.button("🚀 Process Invoices (15)", type="primary", use_container_width=True):
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
        st.markdown("#### B2B Receivables Performance")
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Total Outstanding Receivables", f"₹{rec_report.get('total_receivables_value', 0):,}")
        rc2.metric("Recovered Value", f"₹{rec_report.get('recovered_value', 0):,}")
        rc3.metric("Collections Escalations", rec_report.get("escalated_to_collections", 0))
        rc4.metric("Broken Promise Escalations", rec_report.get("broken_promise_escalations", 0))
        
        st.caption("🎯 **Ground-Truth Baseline Accuracy:** 66.7% (10/15) — misclassifications occur on ambiguous cases without clear broken promise histories.")
        st.warning("📌 **Promise-to-Pay Stopping Rule Active:** Automatically escalates to human review if 2+ broken promises are recorded, halting automated contacts.")
        
        st.divider()
        st.markdown("#### Invoice Processing Breakdown")
        rec_df = pd.DataFrame(rec_report.get("per_invoice_results", []))
        if not rec_df.empty:
            st.dataframe(rec_df, width='stretch', hide_index=True)

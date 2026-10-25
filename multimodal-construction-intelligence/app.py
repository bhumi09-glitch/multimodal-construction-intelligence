"""Multimodal Construction Intelligence Platform - Streamlit entry point (EPIC 1 & 6)."""
from __future__ import annotations

import importlib
import logging
import os
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules import crack_analysis, safety_analysis, valuation, weather_advisor
from modules.construction_assistant import EXAMPLE_QUESTIONS, answer_question
from modules.gemini_service import GeminiService
from modules.report_generator import build_consolidated_report, build_module_report, to_json_bytes
from utils.image_utils import load_uploaded_image
from utils.ui_utils import (badge_html, disclaimer, esc, inject_css, mode_banner, page_header,
                            result_source_notice, severity_badge)

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Construction Intelligence Platform", page_icon="\U0001F3D7\uFE0F", layout="wide")

PAGES = ["Overview", "Site Safety & PPE Audit", "Crack Diagnostics", "Planning & Valuation",
         "Daily Site Assistant", "Project Report"]


# ------------------------------------------------------------------ EPIC 1: setup
def check_dependencies() -> dict:
    """Report which optional/required packages are importable."""
    status = {}
    for label, module in (("Streamlit", "streamlit"), ("Pillow", "PIL"), ("Pandas", "pandas"),
                          ("Plotly", "plotly"), ("google-genai (Gemini)", "google.genai")):
        try:
            importlib.import_module(module)
            status[label] = True
        except Exception:
            status[label] = False
    return status


def _secret_key() -> str:
    """API key from environment or Streamlit secrets (never from code)."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:  # no secrets file configured
            key = ""
    return (key or "").strip()


def init_state() -> None:
    if st.session_state.get("initialised"):
        return
    st.session_state.update(initialised=True, gemini=None, key_error=None,
                            results={"safety": None, "crack": None, "valuation": None},
                            chat=[], weather="Normal", deps=check_dependencies())
    service, error = GeminiService.create(_secret_key())
    st.session_state.gemini, st.session_state.key_error = service, error


def is_live() -> bool:
    return st.session_state.gemini is not None


def store_result(key: str, data: dict, mode: str, source_name: str = None) -> None:
    st.session_state.results[key] = {"data": data, "mode": mode, "source_name": source_name,
                                     "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def download_button(label: str, kind: str, entry: dict, disc: str, filename: str, key: str) -> None:
    payload = to_json_bytes(build_module_report(kind, entry, disc))
    st.download_button(label, payload, file_name=filename, mime="application/json", key=key)


# ------------------------------------------------------------------ sidebar
def render_sidebar() -> str:
    sb = st.sidebar
    sb.markdown('<div class="hazard-stripe"></div><div class="app-title">Construction Intelligence Platform</div>'
                '<div class="app-sub">Multimodal AI for safer, smarter building</div>', unsafe_allow_html=True)

    if is_live():
        sb.markdown(badge_html("Live AI \u00b7 Gemini connected", "ok"), unsafe_allow_html=True)
    else:
        sb.markdown(badge_html("Demo Mode Active", "warn"), unsafe_allow_html=True)
    if st.session_state.key_error:
        sb.warning(st.session_state.key_error)

    with sb.form("api_key_form", clear_on_submit=True):
        key = st.text_input("Gemini API key", type="password", placeholder="Paste key and press Activate",
                            help="Kept only in this session's memory. Cleared from the box after submitting.")
        submitted = st.form_submit_button("Activate live AI", width="stretch")
    if submitted:
        if not key.strip():
            sb.error("Enter an API key, or keep using Demo Mode.")
        else:
            service, error = GeminiService.create(key)
            if service:
                st.session_state.gemini, st.session_state.key_error = service, None
                sb.success("Gemini activated. The key is not displayed again.")
            else:
                st.session_state.key_error = error
                sb.error(error or "Could not activate the key.")
    if is_live() and sb.button("Switch back to Demo Mode", width="stretch"):
        st.session_state.gemini = None
        st.rerun()

    sb.markdown("---")
    page = sb.radio("Navigate", PAGES, key="nav")
    sb.markdown("---")

    with sb.expander("Architecture overview"):
        st.markdown("**UI** (Streamlit) \u2192 **Modules** (safety, crack, valuation, weather, assistant) \u2192 "
                    "**Gemini service** (live) or **demo engine** (offline) \u2192 **JSON validation** \u2192 "
                    "**Dashboard + JSON reports**.\n\nNo database: state lives in the session only.")
    with sb.expander("System check"):
        for name, ok in st.session_state.deps.items():
            icon = "\u2705" if ok else "\u274C"
            st.markdown(f"{icon} {name}")
    with sb.expander("Project information"):
        st.markdown("**Skill Wallet Capstone Project 1**  \nMultimodal Construction Intelligence Platform  \n"
                    "Python \u00b7 Streamlit \u00b7 Gemini \u00b7 Plotly")
    return page


# ------------------------------------------------------------------ page: overview
def page_overview() -> None:
    page_header("Multimodal Construction Intelligence Platform",
                "Audit site safety, diagnose cracks, estimate project value and get daily weather-aware guidance.")
    mode_banner(is_live())
    results = st.session_state.results
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("AI mode", "Live (Gemini)" if is_live() else "Demo")
    c2.metric("PPE audits run", 1 if results["safety"] else 0)
    c3.metric("Crack analyses run", 1 if results["crack"] else 0)
    c4.metric("Site weather", st.session_state.weather)

    st.subheader("What you can do")
    a, b = st.columns(2)
    with a:
        with st.container(border=True):
            st.markdown("**Site Safety & PPE Audit**  \nUpload a site photo to check helmets, vests, boots and "
                        "harnesses, with hazards ranked by severity.")
        with st.container(border=True):
            st.markdown("**Planning & Valuation**  \nEstimate budget, spend, asset value, steel and cement in "
                        "INR, plus a conceptual rendering prompt.")
    with b:
        with st.container(border=True):
            st.markdown("**Crack Diagnostics**  \nClassify defects, estimate width, see likely causes and repair options.")
        with st.container(border=True):
            st.markdown("**Daily Site Assistant**  \nWeather advisories, a daily checklist and a construction Q&A chatbot.")

    st.subheader("Data flow")
    st.graphviz_chart("""digraph G { rankdir=LR; node [shape=box, style="rounded", fontsize=11];
      Upload -> Validate -> "Gemini (live)" -> "JSON parse + repair" -> Dashboard;
      Validate -> "Demo engine" -> "JSON parse + repair";
      Dashboard -> "JSON report"; }""")
    if not is_live():
        st.info("Try it now: open any module from the sidebar. Everything works in Demo Mode with clearly labelled sample data.")


# ------------------------------------------------------------------ page: safety
def _gauge(score: int) -> go.Figure:
    color = "#2E7D32" if score >= 85 else "#F2B705" if score >= 60 else "#C62828"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=score, number={"suffix": "/100"},
                                 gauge={"axis": {"range": [0, 100]}, "bar": {"color": color}}))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def _upload_and_analyse(label: str, key_prefix: str, button_label: str, analyse_fn, store_key: str) -> None:
    uploaded = st.file_uploader(label, type=["jpg", "jpeg", "png"], key=f"{key_prefix}_upload")
    image = image_hash = None
    if uploaded is not None:
        image, error, image_hash = load_uploaded_image(uploaded)
        if error:
            st.error(error)
        else:
            st.image(image, caption=uploaded.name, width="stretch")
    if st.button(button_label, type="primary", key=f"{key_prefix}_run"):
        if image is None:
            st.error("Upload a valid image first. Results are never generated without an image.")
        else:
            with st.spinner("Analysing image..."):
                result, mode, notice = analyse_fn(st.session_state.gemini, image, image_hash)
            store_result(store_key, result, mode, uploaded.name)
            st.session_state[f"{store_key}_notice"] = notice


def page_safety() -> None:
    page_header("Site Safety & PPE Audit", "Upload a construction-site photo for an AI-assisted PPE and hazard review.")
    mode_banner(is_live())
    _upload_and_analyse("Site photo (JPG, JPEG or PNG, up to 10 MB)", "safety", "Run PPE audit",
                        safety_analysis.analyze_site_image, "safety")
    entry = st.session_state.results["safety"]
    if not entry:
        st.info("Upload a photo and press **Run PPE audit** to see results.")
        disclaimer(safety_analysis.DISCLAIMER)
        return
    data = entry["data"]
    st.divider()
    st.subheader(f"Results for {entry['source_name']}")
    result_source_notice(entry["mode"], st.session_state.get("safety_notice"))

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(_gauge(data["safety_score"]), width="stretch")
    with right:
        st.metric("Safety score", f"{data['safety_score']} / 100")
        kind = {"Compliant": "ok", "Partial Compliance": "warn"}.get(data["overall_status"], "bad")
        st.markdown("Overall status: " + badge_html(data["overall_status"], kind), unsafe_allow_html=True)
        st.progress(data["safety_score"] / 100)

    st.markdown("#### PPE checklist")
    cols = st.columns(4)
    for col, (key, label) in zip(cols, safety_analysis.PPE_ITEMS.items()):
        item = data["ppe_detection"][key]
        kind = {"Detected": "ok", "Not Detected": "bad"}.get(item["status"], "warn")
        with col, st.container(border=True):
            st.markdown(f"**{label}**")
            st.markdown(badge_html(item["status"], kind), unsafe_allow_html=True)
            st.caption(f"Confidence {item['confidence']}%")
            st.progress(item["confidence"] / 100)

    st.markdown("#### Hazards")
    if not data["hazards"]:
        st.success("No hazards were reported for this image.")
    for hazard in data["hazards"]:
        with st.container(border=True):
            st.markdown(f"**{esc(hazard['hazard'])}** &nbsp; {severity_badge(hazard['severity'])}", unsafe_allow_html=True)
            st.write(hazard["description"])
            st.markdown(f"**Corrective action:** {hazard['corrective_action']}")
    st.markdown("#### Recommendations")
    for rec in data["recommendations"] or ["No recommendations returned."]:
        st.markdown(f"- {rec}")
    with st.expander("View raw JSON"):
        st.json(data)
    download_button("Download JSON Report", "ppe_safety_audit", entry, safety_analysis.DISCLAIMER,
                    "ppe_safety_report.json", "dl_safety")
    disclaimer(safety_analysis.DISCLAIMER)


# ------------------------------------------------------------------ page: crack
def page_crack() -> None:
    page_header("Crack Diagnostics & Structural Integrity",
                "Upload a photo of a concrete surface or wall for an initial defect assessment.")
    mode_banner(is_live())
    _upload_and_analyse("Surface photo (JPG, JPEG or PNG, up to 10 MB)", "crack", "Run crack analysis",
                        crack_analysis.analyze_crack_image, "crack")
    entry = st.session_state.results["crack"]
    if not entry:
        st.info("Upload a photo and press **Run crack analysis** to see results.")
        disclaimer(crack_analysis.DISCLAIMER)
        return
    data = entry["data"]
    st.divider()
    st.subheader(f"Results for {entry['source_name']}")
    result_source_notice(entry["mode"], st.session_state.get("crack_notice"))
    st.warning(crack_analysis.DISCLAIMER)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Defect type", data["defect_type"])
    c2.metric("Est. width", f"{data['estimated_crack_width_mm']} mm")
    c3.metric("Confidence", f"{data['confidence']}%")
    with c4:
        st.markdown("Severity")
        st.markdown(severity_badge(data["severity"]), unsafe_allow_html=True)
        st.markdown("Urgency")
        ukind = {"Routine Monitoring": "low", "Schedule Repair": "medium", "Urgent": "high", "Immediate": "critical"}
        st.markdown(badge_html(data["urgency"], ukind.get(data["urgency"], "neutral")), unsafe_allow_html=True)
    st.progress(data["confidence"] / 100, text="Model confidence")

    t1, t2, t3 = st.tabs(["Visual observations", "Possible root causes", "Recommended repairs"])
    for tab, key in zip((t1, t2, t3), ("visual_observations", "possible_root_causes", "recommended_repairs")):
        with tab:
            for item in data[key] or ["Nothing reported."]:
                st.markdown(f"- {item}")
    with st.expander("View raw JSON"):
        st.json(data)
    download_button("Download JSON Report", "crack_diagnostics", entry, crack_analysis.DISCLAIMER,
                    "crack_diagnostics_report.json", "dl_crack")


# ------------------------------------------------------------------ page: planning
def page_planning() -> None:
    page_header("Planning & Real Estate Valuation",
                "Conceptual budget, asset value and material estimates in INR, plus a rendering prompt.")
    st.warning(valuation.DISCLAIMER)
    tab_est, tab_render = st.tabs(["Budget & valuation", "Architectural rendering prompt"])

    with tab_est:
        c1, c2, c3 = st.columns(3)
        structure = c1.selectbox("Structure type", valuation.STRUCTURE_TYPES, key="plan_type")
        area = c2.number_input("Built-up area (sq ft)", min_value=1.0, max_value=float(valuation.MAX_AREA),
                               value=2000.0, step=100.0, key="plan_area")
        tier = c3.selectbox("Location tier", valuation.LOCATION_TIERS, key="plan_tier")
        c4, c5, c6 = st.columns(3)
        completion = c4.slider("Completion (%)", 0, 100, 40, key="plan_completion")
        quality = c5.selectbox("Finish quality", valuation.QUALITY_LEVELS, index=1, key="plan_quality")
        land = c6.number_input("Land value (\u20b9 Lakh, optional)", min_value=0.0, value=0.0, step=5.0, key="plan_land")
        try:
            est = valuation.compute_valuation(structure, area, tier, completion, quality, land)
        except (ValueError, TypeError) as exc:
            st.error(f"Check your inputs: {exc}")
            return
        store_result("valuation", est, "calculation")

        m1, m2, m3 = st.columns(3)
        m1.metric("Estimated total budget", valuation.format_inr(est["total_project_budget_inr"]),
                  help=f"About \u20b9{est['cost_per_sqft_inr']:,} per sq ft")
        m2.metric("Capital expenditure incurred", valuation.format_inr(est["capital_expenditure_incurred_inr"]))
        m3.metric("Current market asset valuation", valuation.format_inr(est["current_market_asset_valuation_inr"]))
        m4, m5, m6 = st.columns(3)
        m4.metric("Steel requirement", f"{est['steel_requirement_tonnes']:,} tonnes")
        m5.metric("Cement requirement", f"{est['cement_requirement_bags']:,} bags",
                  help=f"{est['cement_requirement_tonnes']} tonnes (50 kg bags)")
        m6.metric("Value at completion", valuation.format_inr(est["market_value_at_completion_inr"]))
        st.caption(est["estimate_notice"])

        st.markdown("#### Milestone progress")
        st.progress(completion / 100, text=f"Overall completion: {completion}%")
        for row in est["milestones"]:
            a, b = st.columns([3, 1])
            kind = {"Complete": "ok", "In progress": "warn"}.get(row["state"], "neutral")
            a.progress(row["progress"], text=f"{row['milestone']} ({row['range_percent']})")
            b.markdown(badge_html(row["state"], kind), unsafe_allow_html=True)

        st.markdown("#### Budget breakdown")
        df = pd.DataFrame({"Component": list(est["cost_breakdown_inr"]), "Amount (INR)": list(est["cost_breakdown_inr"].values())})
        fig = go.Figure(go.Pie(labels=df["Component"], values=df["Amount (INR)"], hole=0.5))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        p1, p2 = st.columns([1, 1])
        p1.plotly_chart(fig, width="stretch")
        p2.dataframe(df.assign(Formatted=df["Amount (INR)"].map(valuation.format_inr))[["Component", "Formatted"]],
                     hide_index=True, width="stretch")
        download_button("Download JSON Report", "planning_valuation", st.session_state.results["valuation"],
                        valuation.DISCLAIMER, "planning_valuation_report.json", "dl_valuation")

    with tab_render:
        st.markdown("Generate a detailed prompt describing the building from your planning inputs. "
                    "No image-generation service is connected, so copy the prompt into any text-to-image tool.")
        notes = st.text_area("Optional description (style, materials, surroundings)", max_chars=400, key="render_notes",
                             placeholder="e.g. Passive cooling, brick facade, rooftop terrace")
        prompt_text = valuation.build_architectural_prompt(structure, area, tier, completion, notes)
        st.code(prompt_text, language=None, wrap_lines=True)
        st.caption("Conceptual prompt only. Inputs are taken from the Budget & valuation tab.")


# ------------------------------------------------------------------ page: assistant
def page_assistant() -> None:
    page_header("Daily Site Assistant", "Weather-aware safety advisory and a construction Q&A chatbot.")
    mode_banner(is_live())
    tab_weather, tab_chat = st.tabs(["Weather advisory", "Ask the assistant"])

    with tab_weather:
        condition = st.selectbox("Today's weather condition", weather_advisor.CONDITIONS,
                                 index=weather_advisor.CONDITIONS.index(st.session_state.weather), key="weather_select")
        st.session_state.weather = condition
        adv = weather_advisor.get_advisory(condition)
        c1, c2 = st.columns(2)
        c1.metric("Current condition", adv["condition"])
        with c2:
            st.markdown("Risk level")
            st.markdown(severity_badge(adv["risk_level"]), unsafe_allow_html=True)
        st.info(adv["summary"])
        a, b = st.columns(2)
        with a:
            st.markdown("#### Safety alerts")
            for item in adv["safety_alerts"]:
                st.markdown(f"- {item}")
            st.markdown("#### Prohibited / high-risk activities")
            for item in adv["prohibited_activities"]:
                st.markdown(f"- {item}")
        with b:
            st.markdown("#### Recommended actions")
            for item in adv["recommended_actions"]:
                st.markdown(f"- {item}")
        with st.expander("Daily checklist", expanded=True):
            done = sum(st.checkbox(item, key=f"chk_{condition}_{i}") for i, item in enumerate(adv["daily_checklist"]))
            st.progress(done / len(adv["daily_checklist"]), text=f"{done} of {len(adv['daily_checklist'])} complete")
        st.download_button("Download advisory JSON", to_json_bytes(adv), file_name="weather_advisory.json",
                           mime="application/json", key="dl_weather")
        disclaimer(weather_advisor.DISCLAIMER)

    with tab_chat:
        if not is_live():
            st.caption("Demo Mode: answers come from a built-in knowledge base, not live AI.")
        cols = st.columns(len(EXAMPLE_QUESTIONS))
        for col, q in zip(cols, EXAMPLE_QUESTIONS):
            if col.button(q, key=f"ex_{q}", width="stretch"):
                st.session_state.pending_q = q
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        question = st.chat_input("Ask a construction question", key="chat_box") or st.session_state.pop("pending_q", None)
        if question:
            ctx = {"weather": st.session_state.weather}
            for key in ("safety", "crack"):
                if st.session_state.results[key]:
                    ctx[key] = st.session_state.results[key]["data"]
            with st.chat_message("user"):
                st.markdown(question)
            with st.spinner("Thinking..."):
                reply, mode, notice = answer_question(st.session_state.gemini, question, st.session_state.chat, ctx)
            st.session_state.chat += [{"role": "user", "content": question[:1000]}, {"role": "assistant", "content": reply}]
            with st.chat_message("assistant"):
                if notice:
                    st.warning(notice)
                st.markdown(reply)
                if mode == "demo":
                    st.caption("Demonstration result \u2014 not generated by live AI.")
        if st.session_state.chat and st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat = []
            st.rerun()


# ------------------------------------------------------------------ page: report
def page_report() -> None:
    page_header("Project Report", "Combine every analysis from this session into one JSON file.")
    results = st.session_state.results
    names = {"safety": "PPE audit", "crack": "Crack diagnostics", "valuation": "Planning & valuation"}
    cols = st.columns(3)
    for col, (key, name) in zip(cols, names.items()):
        col.markdown(f"**{name}**")
        col.markdown(badge_html("Included" if results[key] else "Not run yet", "ok" if results[key] else "neutral"),
                     unsafe_allow_html=True)
    if not any(results.values()):
        st.info("Run at least one analysis (or visit Planning & Valuation) to build a report.")
        return
    report = build_consolidated_report(results, weather_advisor.get_advisory(st.session_state.weather))
    if report["demonstration_notice"]:
        st.warning(report["demonstration_notice"] + " (contains demonstration sections)")
    with st.expander("Preview"):
        st.json(report)
    st.download_button("Download consolidated report (JSON)", to_json_bytes(report),
                       file_name="construction_project_report.json", mime="application/json", key="dl_all")
    disclaimer("AI-assisted and conceptual output only. Not a substitute for qualified professional inspection or certification.")


# ------------------------------------------------------------------ main
def main() -> None:
    inject_css()
    init_state()
    page = render_sidebar()
    router = {PAGES[0]: page_overview, PAGES[1]: page_safety, PAGES[2]: page_crack,
              PAGES[3]: page_planning, PAGES[4]: page_assistant, PAGES[5]: page_report}
    try:
        router[page]()
    except Exception:  # last-resort guard: never show a traceback to normal users
        logging.exception("Unhandled error on page %s", page)
        st.error("Something went wrong while displaying this page. Please try again or choose another section.")


main()

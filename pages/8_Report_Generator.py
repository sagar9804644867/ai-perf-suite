"""
Page 8: Report Generator
---------------------------
Auto-populated workflow:
  1) Upload JTL / Aggregate Report CSV -> auto-fills test config
     (samples, success rate, start/end time, duration), response time
     stats, per-API table, and generates response-time/P90/throughput
     charts automatically. No manual data entry.
  2) Connect an APM tool -> auto-fills infra/APM section + comparison
     chart.
  3) App auto-drafts Key Observations + Verdict from the numbers —
     editable, not required.
  4) Optional human input: narrative summary, issues, recommendations,
     bug tracking (judgment calls the app can't make on its own).
  5) Generate -> light-themed HTML report with embedded charts.
"""
import os
import sys
import tempfile
from datetime import datetime, timezone
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.loadtest.aggregate_parser import parse_aggregate_csv, parse_jtl_detailed, overall_stats
from connectors.apm.dynatrace_connector import DynatraceConnector
from connectors.apm.datadog_connector import DatadogConnector
from connectors.apm.newrelic_connector import NewRelicConnector
from connectors.apm.appdynamics_connector import AppDynamicsConnector
from utils.report_generator import (
    TestConfig, Issue, BugTicket, ApiResultRow, ApmSnapshot, ReportData, render_html,
)
from utils import report_charts

st.set_page_config(page_title="Report Generator", page_icon="📄", layout="wide")
st.title("📄 Report Generator")
st.caption("Upload your results, connect APM — the report (data + charts) builds itself.")

for key, default in [
    ("report_api_rows", []), ("report_overall_stats", {}), ("report_apm_snapshots", []),
    ("report_auto_config", {}), ("report_raw_elapsed", []), ("report_timestamps", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Step 1: Upload results — this is the ONLY required step
# ---------------------------------------------------------------------------
st.header("1️⃣ Upload Load Test Results")
c1, c2 = st.columns(2)
result_type = c1.radio("Result file type", ["Raw JTL (recommended — richer report)", "JMeter Aggregate Report CSV"], horizontal=False)
sla_target_ms = c2.number_input("SLA target — P90 (ms)", 100.0, 60000.0, 5000.0)
result_file = st.file_uploader("Upload results file", type=["csv", "jtl"])

if result_file:
    is_jtl = result_type.startswith("Raw JTL")
    suffix = ".jtl" if is_jtl else ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(result_file.read())
        tmp_path = tmp.name
    try:
        if is_jtl:
            parsed = parse_jtl_detailed(tmp_path, sla_target_ms=sla_target_ms)
            rows = parsed.rows
            st.session_state.report_raw_elapsed = parsed.raw_elapsed
            st.session_state.report_timestamps = parsed.timestamps_ms

            start_dt = datetime.fromtimestamp(parsed.start_time_epoch_ms / 1000, tz=timezone.utc) if parsed.start_time_epoch_ms else None
            end_dt = datetime.fromtimestamp(parsed.end_time_epoch_ms / 1000, tz=timezone.utc) if parsed.end_time_epoch_ms else None
            st.session_state.report_auto_config = {
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if start_dt else "",
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if end_dt else "",
                "duration": f"{parsed.duration_sec:.0f}s" if parsed.duration_sec else "",
                "test_date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
                "max_users": parsed.max_threads,
                "total_samples": parsed.total_samples,
                "success_rate_pct": parsed.success_rate_pct,
                "start_epoch_ms": parsed.start_time_epoch_ms,
                "end_epoch_ms": parsed.end_time_epoch_ms,
            }
        else:
            rows = parse_aggregate_csv(tmp_path, sla_target_ms=sla_target_ms)
            st.session_state.report_raw_elapsed = []
            st.session_state.report_timestamps = []
            st.session_state.report_auto_config = {}

        st.session_state.report_api_rows = [
            ApiResultRow(r.api_name, r.samples, r.avg_ms, r.min_ms, r.max_ms,
                         r.p90_ms, r.p95_ms, r.error_rate, r.sla_met)
            for r in rows
        ]
        st.session_state.report_overall_stats = overall_stats(rows)
        if is_jtl:
            st.session_state.report_overall_stats["total_samples"] = st.session_state.report_auto_config.get("total_samples", st.session_state.report_overall_stats.get("total_samples"))
            st.session_state.report_overall_stats["success_rate_pct"] = st.session_state.report_auto_config.get("success_rate_pct", st.session_state.report_overall_stats.get("success_rate_pct"))

        st.success(f"✅ Parsed {len(rows)} API(s), {st.session_state.report_overall_stats.get('total_samples', 0)} total samples.")
        st.dataframe(
            [{"API": r.api_name, "Samples": r.samples, "Avg": r.avg_ms, "P90": r.p90_ms,
              "P95": r.p95_ms, "Error %": r.error_rate, "SLA Met": r.sla_met} for r in rows],
            use_container_width=True,
        )
        if is_jtl:
            st.info(f"Auto-detected: {st.session_state.report_auto_config['start_time']} → "
                    f"{st.session_state.report_auto_config['end_time']} "
                    f"(duration {st.session_state.report_auto_config['duration']}, "
                    f"peak {st.session_state.report_auto_config['max_users']} threads)")
        else:
            st.warning("Aggregate CSV has no timestamps — start/end time and throughput-over-time "
                       "chart need a raw JTL. Everything else is auto-filled.")
    except Exception as e:
        st.error(f"Parse error: {e}")
    finally:
        os.unlink(tmp_path)
elif st.session_state.report_api_rows:
    st.info(f"Using previously uploaded results ({len(st.session_state.report_api_rows)} API rows).")
else:
    st.warning("Upload a results file to continue — everything below builds from this automatically.")

# ---------------------------------------------------------------------------
# Step 2: Connect APM (optional, auto-fills section 4)
# ---------------------------------------------------------------------------
st.header("2️⃣ Connect APM (optional)")

has_test_window = bool(st.session_state.report_auto_config.get("start_epoch_ms"))

with st.expander("Connect an APM tool — metrics auto-pull for the exact test window", expanded=not st.session_state.report_apm_snapshots):
    tool = st.selectbox("APM Tool", ["Dynatrace", "Datadog", "New Relic", "AppDynamics"], key="report_apm_tool")
    base_url = st.text_input("Base URL", key="report_apm_url")
    api_token = st.text_input("API Token / Secret", type="password", key="report_apm_token")
    extra_kwargs = {}
    if tool == "Datadog":
        extra_kwargs["app_key"] = st.text_input("Application Key", type="password", key="report_dd_appkey")
    elif tool == "New Relic":
        extra_kwargs["account_id"] = st.text_input("Account ID", key="report_nr_account")
    elif tool == "AppDynamics":
        extra_kwargs["account_name"] = st.text_input("Account Name", key="report_appd_acct")
        extra_kwargs["client_id"] = st.text_input("API Client ID", key="report_appd_client")
        extra_kwargs["application_name"] = st.text_input("Application Name", key="report_appd_app")

    if has_test_window:
        start_ts = st.session_state.report_auto_config["start_epoch_ms"]
        end_ts = st.session_state.report_auto_config["end_epoch_ms"]
        st.success(f"Will query the exact test window: {st.session_state.report_auto_config['start_time']} "
                   f"→ {st.session_state.report_auto_config['end_time']} "
                   f"({st.session_state.report_auto_config['duration']}) — no lookback guessing needed.")
        minutes_fallback = 30
    else:
        st.info("No JTL timestamps available (aggregate CSV was used) — set a manual lookback window instead.")
        minutes_fallback = st.slider("Lookback (minutes)", 5, 240, 30, key="report_apm_minutes")
        start_ts = end_ts = None

    connector_map = {"Dynatrace": DynatraceConnector, "Datadog": DatadogConnector,
                      "New Relic": NewRelicConnector, "AppDynamics": AppDynamicsConnector}

    dc1, dc2 = st.columns([1, 2])
    if dc1.button("🔍 Discover services", key="report_apm_discover_btn"):
        connector = connector_map[tool](base_url=base_url, api_token=api_token, **extra_kwargs)
        try:
            if connector.test_connection():
                entities = connector.list_entities()
                st.session_state["report_apm_discovered"] = entities
                st.success(f"Found {len(entities)} service(s).")
            else:
                st.error("Connection failed — check credentials.")
        except Exception as e:
            st.error(f"Discovery error: {e}")

    discovered = st.session_state.get("report_apm_discovered", [])
    selected_entities = st.multiselect(
        "Services to pull metrics for (or type one manually below if discovery is unavailable)",
        options=discovered, key="report_apm_selected_entities",
    )
    manual_entity = st.text_input("Or enter a service name manually", key="report_apm_manual_entity")

    if dc2.button("⚡ Auto-fetch ALL metrics for these services", key="report_apm_fetchall_btn", type="primary"):
        entities_to_fetch = list(selected_entities)
        if manual_entity:
            entities_to_fetch.append(manual_entity)
        if not entities_to_fetch:
            st.warning("Select or type at least one service first.")
        else:
            connector = connector_map[tool](base_url=base_url, api_token=api_token, **extra_kwargs)
            if connector.test_connection():
                progress = st.progress(0.0)
                for i, ent in enumerate(entities_to_fetch):
                    try:
                        health = connector.get_service_health(
                            ent, minutes=minutes_fallback,
                            start_epoch_ms=start_ts, end_epoch_ms=end_ts,
                        )
                        snap = ApmSnapshot(
                            tool=tool, entity=ent,
                            response_time_p95=health.response_time_p95,
                            response_time_p99=health.response_time_p99,
                            error_rate_pct=health.error_rate_pct,
                            throughput_rpm=health.throughput_rpm,
                            cpu_pct=health.cpu_pct, memory_pct=health.memory_pct,
                        )
                        st.session_state.report_apm_snapshots.append(snap)
                    except Exception as e:
                        st.error(f"{ent}: {e}")
                    progress.progress((i + 1) / len(entities_to_fetch))
                st.success(f"Pulled metrics for {len(entities_to_fetch)} service(s), "
                           f"{'aligned to the test window' if has_test_window else f'last {minutes_fallback} min'}.")
            else:
                st.error("Connection failed — check credentials.")

if st.session_state.report_apm_snapshots:
    st.dataframe(
        [{"Tool": s.tool, "Entity": s.entity, "P95": s.response_time_p95, "P99": s.response_time_p99,
          "Error %": s.error_rate_pct, "Throughput": s.throughput_rpm, "CPU%": s.cpu_pct, "Mem%": s.memory_pct}
         for s in st.session_state.report_apm_snapshots],
        use_container_width=True,
    )
    if st.button("Clear APM snapshots"):
        st.session_state.report_apm_snapshots = []
        st.rerun()

# ---------------------------------------------------------------------------
# Step 3: Auto-drafted narrative — computed, not typed
# ---------------------------------------------------------------------------
st.header("3️⃣ Auto-Drafted Summary (edit freely)")
stats = st.session_state.report_overall_stats
auto_cfg = st.session_state.report_auto_config
rows = st.session_state.report_api_rows

auto_observations = []
auto_verdict = "Not yet determined"
if stats:
    sla_met_count = sum(1 for r in rows if r.sla_met)
    sla_total = len(rows) or 1
    auto_observations.append(f"{stats.get('total_samples', 0)} total samples, "
                              f"{stats.get('success_rate_pct', 0)}% success rate.")
    auto_observations.append(f"Overall P90 {stats.get('p90_ms', '—')} ms, P95 {stats.get('p95_ms', '—')} ms "
                              f"against a {sla_target_ms:.0f} ms SLA target.")
    auto_observations.append(f"{sla_met_count}/{sla_total} APIs met the SLA threshold.")
    if auto_cfg.get("max_users"):
        auto_observations.append(f"Peak concurrency observed: {auto_cfg['max_users']} threads.")

    error_ok = stats.get("success_rate_pct", 100) >= 99.0
    sla_ok = sla_met_count == sla_total
    auto_verdict = "PASS" if (error_ok and sla_ok) else "PASS (with findings)" if error_ok or sla_ok else "FAIL"

c1, c2 = st.columns([2, 1])
with c1:
    executive_summary = st.text_area(
        "Executive summary", value=(
            f"Load test executed with {stats.get('total_samples', 0)} samples across "
            f"{len(rows)} API(s). Overall success rate {stats.get('success_rate_pct', '—')}%, "
            f"P90 {stats.get('p90_ms', '—')} ms."
        ) if stats else "", key="report_exec_summary",
    )
    key_finding = st.text_area("Key finding", value="", key="report_key_finding")
with c2:
    verdict_options = ["PASS", "PASS (with findings)", "FAIL", "Not yet determined"]
    default_idx = verdict_options.index(auto_verdict) if auto_verdict in verdict_options else 3
    verdict = st.selectbox("Verdict", verdict_options, index=default_idx, key="report_verdict")

st.text_area("Key Observations (auto-drafted, one per line — edit as needed)",
             value="\n".join(auto_observations), key="report_observations", height=120)
key_observations = [o.strip() for o in st.session_state.report_observations.split("\n") if o.strip()]

sla_compliance_note = st.text_input(
    "SLA compliance note", key="report_sla_note",
    value=(f"{sum(1 for r in rows if r.sla_met)}/{len(rows)} APIs met the {sla_target_ms:.0f} ms P90 SLA."
           if rows else "All transactions met the SLA threshold."),
)

infra_notes = st.text_area("Infrastructure / APM narrative notes (optional)", "", key="report_infra_notes")

# ---------------------------------------------------------------------------
# Step 4: Optional human judgment — issues, recommendations, bugs
# ---------------------------------------------------------------------------
st.header("4️⃣ Issues, Recommendations & Bug Tracking (optional)")

st.subheader("Issues Observed")
num_issues = st.number_input("Number of issues", 0, 20, 0, key="report_num_issues")
issues = []
for i in range(num_issues):
    with st.expander(f"Issue {i+1}", expanded=True):
        ic1, ic2 = st.columns(2)
        itype = ic1.text_input("Issue type", key=f"issue_type_{i}")
        sev = ic2.selectbox("Severity", ["High", "Medium", "Low"], key=f"issue_sev_{i}")
        impact = st.text_input("Count / impact", key=f"issue_impact_{i}")
        component = st.text_input("Affected component", key=f"issue_comp_{i}")
        desc = st.text_area("Description", key=f"issue_desc_{i}")
        link = st.text_input("Bug link (optional)", key=f"issue_link_{i}")
        issues.append(Issue(itype, sev, impact, component, desc, link))

st.subheader("Recommendations")
recs_raw = st.text_area("One per line", "", key="report_recommendations")
recommendations = [r.strip() for r in recs_raw.split("\n") if r.strip()]

st.subheader("Bug Tracking")
num_bugs = st.number_input("Number of bug tickets", 0, 20, 0, key="report_num_bugs")
bug_tracking = []
for i in range(num_bugs):
    bc1, bc2, bc3, bc4 = st.columns(4)
    bug_id = bc1.text_input("Bug ID", key=f"bug_id_{i}")
    title = bc2.text_input("Title", key=f"bug_title_{i}")
    sev = bc3.selectbox("Severity", ["High", "Medium", "Low"], key=f"bug_sev_{i}")
    status = bc4.text_input("Status", key=f"bug_status_{i}")
    link = st.text_input("Link", key=f"bug_link_{i}")
    bug_tracking.append(BugTicket(bug_id, title, sev, status, link))

st.header("5️⃣ Report Identity")
c1, c2, c3 = st.columns(3)
test_name = c1.text_input("Test name", "Load Test", key="report_test_name")
test_run_id = c2.text_input("Test Run ID", value=datetime.now().strftime("RUN-%Y%m%d-%H%M"), key="report_test_run_id")
environment = c3.text_input("Environment", "", key="report_environment")
c4, c5, c6 = st.columns(3)
auth_method = c4.text_input("Authentication", "", key="report_auth")
ramp_up = c5.text_input("Ramp-up", "", key="report_rampup")
author = c6.text_input("Report author", "", key="report_author")

# ---------------------------------------------------------------------------
# Step 6: Generate — build charts + assemble
# ---------------------------------------------------------------------------
st.header("6️⃣ Generate Report")
if st.button("🚀 Generate Report", type="primary", disabled=not st.session_state.report_api_rows):
    raw_elapsed = st.session_state.report_raw_elapsed
    timestamps = st.session_state.report_timestamps
    api_rows = st.session_state.report_api_rows

    chart_hist = report_charts.response_time_histogram(raw_elapsed) if raw_elapsed else None
    chart_p90 = report_charts.p90_by_api_chart([r.api_name for r in api_rows], [r.p90_ms for r in api_rows])
    chart_throughput = report_charts.throughput_over_time_chart(timestamps) if timestamps else None
    apm_snaps = st.session_state.report_apm_snapshots
    chart_apm = report_charts.apm_comparison_chart(
        [s.entity for s in apm_snaps], [s.response_time_p95 or 0 for s in apm_snaps],
        [s.response_time_p99 or 0 for s in apm_snaps]
    ) if apm_snaps else None

    cfg = TestConfig(
        test_run_id=test_run_id, test_name=test_name,
        test_date=auto_cfg.get("test_date", ""),
        start_time=auto_cfg.get("start_time", ""), end_time=auto_cfg.get("end_time", ""),
        duration=auto_cfg.get("duration", ""),
        environment=environment, max_users=int(auto_cfg.get("max_users", 0)), ramp_up=ramp_up,
        total_samples=stats.get("total_samples", 0), success_rate_pct=stats.get("success_rate_pct", 0),
        auth_method=auth_method, think_time="", throughput_cap=f"{sla_target_ms:.0f} ms P90",
    )
    data = ReportData(
        config=cfg, executive_summary=st.session_state.report_exec_summary,
        key_finding=st.session_state.report_key_finding, verdict=verdict,
        key_observations=key_observations, issues=issues,
        sla_target_ms=sla_target_ms, sla_compliance_note=st.session_state.report_sla_note,
        overall_stats=stats, api_rows=api_rows, apm_snapshots=apm_snaps,
        infra_notes=infra_notes, recommendations=recommendations, bug_tracking=bug_tracking,
        author=author,
        chart_response_time_histogram=chart_hist, chart_p90_by_api=chart_p90,
        chart_throughput_over_time=chart_throughput, chart_apm_comparison=chart_apm,
    )
    html_report = render_html(data)

    st.success("Report generated ✅")
    st.download_button("⬇ Download report (.html)", html_report,
                        file_name=f"{test_name.replace(' ', '_')}_report.html", mime="text/html")

    st.divider()
    st.subheader("Preview")
    import streamlit.components.v1 as components
    components.html(html_report, height=1000, scrolling=True)
else:
    if not st.session_state.report_api_rows:
        st.info("Upload results in Step 1 first — the Generate button unlocks once data is parsed.")

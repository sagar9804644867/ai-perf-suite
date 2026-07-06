"""
report_generator.py
----------------------
Assembles a full performance test report — same section structure as
your Confluence template (Executive Summary, Test Configuration, Key
Observations, Issues, SLA Compliance, Response Time Stats, Throughput,
APM/Infra Deep Dive, Recommendations, Bug Tracking) — and renders it
as a clean, light-background standalone HTML file.

Fed from three places:
  1. Script Recorder step -> test config basics (target, method mix)
  2. Uploaded JTL/aggregate CSV -> response time + throughput sections
  3. Connected APM tool -> infra/APM deep dive section
  4. Manual fields -> exec summary narrative, observations, issues, recs
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from html import escape as h


@dataclass
class TestConfig:
    test_run_id: str = ""
    test_name: str = ""
    test_date: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: str = ""
    environment: str = ""
    max_users: int = 0
    ramp_up: str = ""
    total_samples: int = 0
    success_rate_pct: float = 0.0
    auth_method: str = ""
    think_time: str = ""
    throughput_cap: str = ""
    extra_notes: str = ""


@dataclass
class Issue:
    issue_type: str
    severity: str  # High / Medium / Low
    impact: str
    affected_component: str
    description: str
    bug_link: str = ""


@dataclass
class BugTicket:
    bug_id: str
    title: str
    severity: str
    status: str
    link: str = ""


@dataclass
class ApiResultRow:
    api_name: str
    samples: int
    avg_ms: float
    min_ms: float
    max_ms: float
    p90_ms: float
    p95_ms: float
    error_rate: float
    sla_met: bool


@dataclass
class ApmSnapshot:
    tool: str
    entity: str
    response_time_p95: Optional[float] = None
    response_time_p99: Optional[float] = None
    error_rate_pct: Optional[float] = None
    throughput_rpm: Optional[float] = None
    cpu_pct: Optional[float] = None
    memory_pct: Optional[float] = None


@dataclass
class ReportData:
    config: TestConfig
    executive_summary: str = ""
    key_finding: str = ""
    verdict: str = ""
    key_observations: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    sla_target_ms: float = 5000.0
    sla_compliance_note: str = ""
    overall_stats: dict = field(default_factory=dict)   # from aggregate_parser.overall_stats
    api_rows: List[ApiResultRow] = field(default_factory=list)
    apm_snapshots: List[ApmSnapshot] = field(default_factory=list)
    infra_notes: str = ""
    recommendations: List[str] = field(default_factory=list)
    bug_tracking: List[BugTicket] = field(default_factory=list)
    author: str = ""
    chart_response_time_histogram: Optional[str] = None
    chart_p90_by_api: Optional[str] = None
    chart_throughput_over_time: Optional[str] = None
    chart_apm_comparison: Optional[str] = None


SEVERITY_COLORS = {"High": "#D64545", "Medium": "#D68A00", "Low": "#2E9E4B"}


def _sla_badge(ok: bool) -> str:
    return ('<span style="color:#2E9E4B;font-weight:600;">✅ Met</span>' if ok
            else '<span style="color:#D64545;font-weight:600;">❌ Missed</span>')


def render_html(data: ReportData) -> str:
    cfg = data.config
    stats = data.overall_stats or {}

    observations_html = "".join(f"<li>{h(o)}</li>" for o in data.key_observations) or "<li><em>None recorded</em></li>"
    recs_html = "".join(f"<li>{h(r)}</li>" for r in data.recommendations) or "<li><em>None recorded</em></li>"

    issues_rows = "".join(f"""
        <tr>
          <td>{i+1}</td>
          <td>{h(iss.issue_type)}</td>
          <td style="color:{SEVERITY_COLORS.get(iss.severity, '#333')};font-weight:600;">{h(iss.severity)}</td>
          <td>{h(iss.impact)}</td>
          <td>{h(iss.affected_component)}</td>
          <td>{h(iss.description)}{' — <a href="' + h(iss.bug_link) + '">Bug link</a>' if iss.bug_link else ''}</td>
        </tr>""" for i, iss in enumerate(data.issues)) or '<tr><td colspan="6"><em>No issues observed</em></td></tr>'

    api_rows_html = "".join(f"""
        <tr>
          <td>{h(r.api_name)}</td>
          <td>{r.samples}</td>
          <td>{r.avg_ms:.0f}</td>
          <td>{r.min_ms:.0f}</td>
          <td>{r.max_ms:.0f}</td>
          <td>{r.p90_ms:.0f}</td>
          <td>{r.p95_ms:.0f}</td>
          <td>{r.error_rate:.2f}%</td>
          <td>{_sla_badge(r.sla_met)}</td>
        </tr>""" for r in data.api_rows) or '<tr><td colspan="9"><em>Upload a JTL/aggregate CSV to populate</em></td></tr>'

    apm_rows_html = "".join(f"""
        <tr>
          <td>{h(a.tool)}</td>
          <td>{h(a.entity)}</td>
          <td>{a.response_time_p95 if a.response_time_p95 is not None else '—'}</td>
          <td>{a.response_time_p99 if a.response_time_p99 is not None else '—'}</td>
          <td>{a.error_rate_pct if a.error_rate_pct is not None else '—'}</td>
          <td>{a.throughput_rpm if a.throughput_rpm is not None else '—'}</td>
          <td>{a.cpu_pct if a.cpu_pct is not None else '—'}</td>
          <td>{a.memory_pct if a.memory_pct is not None else '—'}</td>
        </tr>""" for a in data.apm_snapshots) or '<tr><td colspan="8"><em>Connect an APM tool to populate</em></td></tr>'

    bug_rows_html = "".join(f"""
        <tr>
          <td>{h(b.bug_id)}</td>
          <td>{h(b.title)}</td>
          <td style="color:{SEVERITY_COLORS.get(b.severity, '#333')};font-weight:600;">{h(b.severity)}</td>
          <td>{h(b.status)}</td>
          <td>{'<a href="' + h(b.link) + '">Link</a>' if b.link else '—'}</td>
        </tr>""" for b in data.bug_tracking) or '<tr><td colspan="5"><em>No bugs tracked</em></td></tr>'

    generated_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{h(cfg.test_name or 'Performance Test Report')}</title>
<style>
  body {{ background:#FFFFFF; color:#1A1A1A; font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin:0; padding:0; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:32px 40px; }}
  h1 {{ font-size:26px; border-bottom:3px solid #0F62FE; padding-bottom:10px; }}
  h2 {{ font-size:20px; margin-top:36px; color:#0F62FE; border-bottom:1px solid #E0E4E8; padding-bottom:6px; }}
  h3 {{ font-size:16px; margin-top:22px; color:#333; }}
  table {{ border-collapse:collapse; width:100%; margin:14px 0 22px 0; font-size:13.5px; }}
  th {{ background:#F4F6F8; text-align:left; padding:8px 10px; border:1px solid #E0E4E8; }}
  td {{ padding:8px 10px; border:1px solid #E0E4E8; vertical-align:top; }}
  .meta {{ color:#666; font-size:13px; margin-bottom:18px; }}
  .callout {{ background:#F4F6F8; border-left:4px solid #0F62FE; padding:14px 18px; margin:16px 0; border-radius:4px; }}
  .verdict {{ font-size:18px; font-weight:700; padding:14px 18px; border-radius:4px; margin:18px 0; }}
  .verdict.pass {{ background:#E7F6EC; color:#1E7A34; border-left:4px solid #2E9E4B; }}
  .verdict.fail {{ background:#FCEAEA; color:#A13030; border-left:4px solid #D64545; }}
  ul {{ line-height:1.7; }}
  .badge-row td {{ font-weight:600; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{h(cfg.test_name or 'Performance Test Report')}</h1>
  <div class="meta">Test Run ID: {h(cfg.test_run_id)} &nbsp;|&nbsp; Generated: {generated_ts} &nbsp;|&nbsp; Author: {h(data.author or '—')}</div>

  <h2>1.0 Executive Summary</h2>
  <p>{h(data.executive_summary) or '<em>Add a narrative summary of the test outcome.</em>'}</p>
  <div class="callout"><strong>Key finding:</strong> {h(data.key_finding) or '<em>Not yet recorded</em>'}</div>
  <div class="verdict {'pass' if 'pass' in data.verdict.lower() else 'fail' if data.verdict else ''}">
    Verdict: {h(data.verdict) or 'Not yet determined'}
  </div>

  <h2>1.1 Test Configuration</h2>
  <table>
    <tr><th>Configuration Item</th><th>Value</th></tr>
    <tr><td>Test Run ID</td><td>{h(cfg.test_run_id)}</td></tr>
    <tr><td>Test Date</td><td>{h(cfg.test_date)}</td></tr>
    <tr><td>Start Time</td><td>{h(cfg.start_time)}</td></tr>
    <tr><td>End Time</td><td>{h(cfg.end_time)}</td></tr>
    <tr><td>Test Duration</td><td>{h(cfg.duration)}</td></tr>
    <tr><td>Environment</td><td>{h(cfg.environment)}</td></tr>
    <tr><td>Max Virtual Users</td><td>{cfg.max_users}</td></tr>
    <tr><td>Ramp-up</td><td>{h(cfg.ramp_up)}</td></tr>
    <tr><td>Total HTTP Samples</td><td>{cfg.total_samples}</td></tr>
    <tr><td>Success Rate</td><td>{cfg.success_rate_pct}%</td></tr>
    <tr><td>Authentication</td><td>{h(cfg.auth_method)}</td></tr>
    <tr><td>Think Time</td><td>{h(cfg.think_time)}</td></tr>
    <tr><td>Throughput Cap</td><td>{h(cfg.throughput_cap)}</td></tr>
  </table>
  {f'<p>{h(cfg.extra_notes)}</p>' if cfg.extra_notes else ''}

  <h2>2.0 Key Observations</h2>
  <ul>{observations_html}</ul>

  <h3>2.1 Issues Observed</h3>
  <table>
    <tr><th>#</th><th>Issue Type</th><th>Severity</th><th>Count / Impact</th><th>Affected Component</th><th>Description</th></tr>
    {issues_rows}
  </table>

  <h3>2.2 SLA Compliance</h3>
  <p>SLA target: <strong>P90 ≤ {cfg.throughput_cap or f'{data.sla_target_ms:.0f} ms'}</strong>. {h(data.sla_compliance_note)}</p>

  <h2>3.0 Performance Test Results</h2>
  <h3>3.1 Response Time Statistics</h3>
  <table>
    <tr><th>Metric</th><th>Value (ms)</th></tr>
    <tr><td>Total Samples</td><td>{stats.get('total_samples', '—')}</td></tr>
    <tr><td>Average</td><td>{stats.get('avg_ms', '—')}</td></tr>
    <tr><td>Min</td><td>{stats.get('min_ms', '—')}</td></tr>
    <tr><td>Max</td><td>{stats.get('max_ms', '—')}</td></tr>
    <tr><td>90th Percentile</td><td>{stats.get('p90_ms', '—')}</td></tr>
    <tr><td>95th Percentile</td><td>{stats.get('p95_ms', '—')}</td></tr>
    <tr><td>Success Rate</td><td>{stats.get('success_rate_pct', '—')}%</td></tr>
  </table>

  {f'<img src="data:image/png;base64,{data.chart_response_time_histogram}" style="max-width:100%;margin:10px 0;">' if data.chart_response_time_histogram else ''}

  <h3>3.2 Response Time Details (per API)</h3>
  <table>
    <tr><th>API Name</th><th>Samples</th><th>Avg</th><th>Min</th><th>Max</th><th>P90</th><th>P95</th><th>Error Rate</th><th>SLA Met</th></tr>
    {api_rows_html}
  </table>
  {f'<img src="data:image/png;base64,{data.chart_p90_by_api}" style="max-width:100%;margin:10px 0;">' if data.chart_p90_by_api else ''}

  <h3>3.3 Throughput Over Time</h3>
  {f'<img src="data:image/png;base64,{data.chart_throughput_over_time}" style="max-width:100%;margin:10px 0;">' if data.chart_throughput_over_time else '<p><em>Upload a raw JTL (not aggregate CSV) for a throughput-over-time chart.</em></p>'}

  <h2>4.0 Infrastructure &amp; APM Deep Dive</h2>
  <table>
    <tr><th>Tool</th><th>Entity</th><th>P95 (ms)</th><th>P99 (ms)</th><th>Error Rate %</th><th>Throughput (rpm)</th><th>CPU %</th><th>Memory %</th></tr>
    {apm_rows_html}
  </table>
  {f'<img src="data:image/png;base64,{data.chart_apm_comparison}" style="max-width:100%;margin:10px 0;">' if data.chart_apm_comparison else ''}
  {f'<div class="callout">{h(data.infra_notes)}</div>' if data.infra_notes else ''}

  <h2>5.0 Recommendations</h2>
  <ul>{recs_html}</ul>

  <h2>6.0 Action Items &amp; Bug Tracking</h2>
  <table>
    <tr><th>Bug ID</th><th>Title</th><th>Severity</th><th>Status</th><th>Link</th></tr>
    {bug_rows_html}
  </table>

  <p style="color:#999;font-size:12px;margin-top:40px;">Generated by AI Perf Suite — {generated_ts}</p>
</div>
</body>
</html>"""
    return html

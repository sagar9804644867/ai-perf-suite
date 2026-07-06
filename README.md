# AI Perf Suite

An AI-assisted performance engineering toolkit built with Streamlit —
covering recording-driven load test script generation, unified APM
metrics, load test comparison, SLO analysis, Kubernetes autoscaling
visibility, distributed tracing correlation, CI/CD pipeline status,
and full report generation.

## Modules

| # | Module | Status |
|---|--------|--------|
| 1 | Script Recorder (HAR → JMeter/Gatling/Locust/k6) | ✅ Fully working |
| 2 | APM Metrics (Dynatrace/Datadog/New Relic/AppDynamics) | ✅ Real API integration — needs creds |
| 3 | Load Test Comparator | ✅ Fully working |
| 4 | K8s Cluster View (pods, HPA) | ✅ Needs kubectl access |
| 5 | Distributed Tracing (Jaeger/Zipkin) | ✅ Needs backend URL |
| 6 | Latency & SLO Analyzer | ✅ Fully working |
| 7 | CI/CD Insights (Jenkins/GH Actions/GitLab CI) | ✅ Needs creds |

## Setup

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # fill in credentials once on corporate network
streamlit run app.py
```

## Module 1 walkthrough — Script Recorder

1. Record a flow in Chrome DevTools (Network tab → Preserve log → perform flow →
   right-click → "Save all as HAR with content"), or via Playwright's
   `record_har_path`.
2. Upload the `.har` file on the **Script Recorder** page.
3. Filter to XHR/API calls only (recommended — strips static assets).
4. Download generated `.jmx`, `.scala`, `.py` (Locust), or `.js` (k6) — all
   from the same recorded flow, so JMeter/Gatling/Locust/k6 comparisons are
   apples-to-apples.

## Deploying to Streamlit Community Cloud

Push this repo to GitHub, then deploy `app.py` as the main file from
share.streamlit.io. Add secrets (API tokens) via the Streamlit Cloud
**Secrets** UI instead of committing `.env`.

## Corporate network notes

Once inside your corporate network:
- APM connectors (`connectors/apm/*.py`) are real API integrations — just
  supply base URLs + tokens via `.env` or Streamlit secrets, no code changes.
- K8s module shells out to `kubectl` — make sure it's installed and
  `KUBE_CONTEXT` points at the right cluster.
- Tracing/CI/CD modules assume network access to Jaeger/Zipkin/Jenkins/etc.
  endpoints; if those sit behind a VPN-only address, run Streamlit from a
  machine inside that network.

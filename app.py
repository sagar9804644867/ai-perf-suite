"""
AI Perf Suite
==================================
Multi-page Streamlit utility covering the full JD:
  - Recorded-flow script generation (JMeter/Gatling/Locust/k6)
  - Unified APM metrics (Dynatrace/Datadog/New Relic/AppDynamics)
  - Load test report comparison
  - Latency & SLO analysis (P50/P90/P95/P99, error rate, saturation)
  - Kubernetes cluster/autoscaling view
  - Distributed tracing correlation (Jaeger/Zipkin)
  - CI/CD pipeline insights

Run: streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="AI Perf Suite", page_icon="⚡", layout="wide")

st.title("⚡ AI Perf Suite")
st.caption("Performance Engineering utility: record → test → observe → analyze")

st.markdown("""
Use the sidebar to navigate between modules:

| Module | Status | Covers |
|---|---|---|
| 🎬 Script Recorder | ✅ Working | HAR recording → JMeter/Gatling/Locust/k6 |
| 📊 APM Metrics | 🟡 Stub → wire creds | Dynatrace, Datadog, New Relic, AppDynamics |
| 🧪 Load Test Comparator | 🟡 Stub | Parse & compare JMeter/Gatling/Locust/k6 results |
| 📈 Latency & SLO Analyzer | 🟡 Stub | P50/P90/P95/P99, throughput, error rate, saturation |
| ☸️ K8s Cluster View | 🟡 Stub | kubectl/Helm, namespaces, HPA/autoscaling |
| 🕸️ Distributed Tracing | 🟡 Stub | Jaeger/Zipkin trace correlation |
| 🔧 CI/CD Insights | 🟡 Stub | Jenkins/GitHub Actions/GitLab CI |

Each stub module has working UI + connector interfaces already defined —
plug in credentials via `.env` (see `.env.example`) and the calls go live.
""")

st.info("Start with **🎬 Script Recorder** in the sidebar — record a flow once, "
        "generate scripts for all 4 load tools from it.")

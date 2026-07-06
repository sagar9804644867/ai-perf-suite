"""
Page 3: Load Test Comparator
------------------------------
Upload result files from JMeter (.jtl/.csv), Gatling (simulation.log),
Locust (*_stats_history.csv), or k6 (results.json) and compare
P50/P90/P95/P99, error rate, and throughput across runs — even across
different tools, e.g. comparing a JMeter baseline to a new k6 script.
"""
import os
import sys
import tempfile
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.loadtest.result_parsers import (
    parse_jmeter_jtl, parse_gatling_log, parse_locust_csv, parse_k6_json,
)
from utils.metrics_calc import latency_summary, error_rate_pct

st.set_page_config(page_title="Load Test Comparator", page_icon="🧪", layout="wide")
st.title("🧪 Load Test Comparator")
st.caption("Compare result files across JMeter, Gatling, Locust, and k6 — same view, any tool.")

PARSERS = {
    "JMeter (.jtl/.csv)": parse_jmeter_jtl,
    "Gatling (simulation.log)": parse_gatling_log,
    "Locust (*_stats_history.csv)": parse_locust_csv,
    "k6 (results.json)": parse_k6_json,
}

st.subheader("Add runs to compare")
num_runs = st.number_input("Number of runs to compare", 1, 5, 2)

runs_data = {}
cols = st.columns(num_runs)
for i in range(num_runs):
    with cols[i]:
        st.markdown(f"**Run {i+1}**")
        run_name = st.text_input("Label", value=f"Run {i+1}", key=f"label_{i}")
        tool = st.selectbox("Tool", list(PARSERS.keys()), key=f"tool_{i}")
        uploaded = st.file_uploader("Result file", key=f"file_{i}")
        if uploaded:
            suffix = os.path.splitext(uploaded.name)[1] or ".txt"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                samples = PARSERS[tool](tmp_path)
                runs_data[run_name] = samples
                st.success(f"{len(samples)} samples parsed")
            except Exception as e:
                st.error(f"Parse error: {e}")
            finally:
                os.unlink(tmp_path)

if runs_data:
    st.divider()
    st.subheader("Comparison")

    rows = []
    for run_name, samples in runs_data.items():
        if not samples:
            continue
        latencies = [s.elapsed_ms for s in samples]
        total = len(samples)
        failed = sum(1 for s in samples if not s.success)
        summary = latency_summary(latencies)
        rows.append({
            "Run": run_name,
            "Samples": total,
            "P50 (ms)": summary["p50"],
            "P90 (ms)": summary["p90"],
            "P95 (ms)": summary["p95"],
            "P99 (ms)": summary["p99"],
            "Error Rate %": error_rate_pct(total, failed),
        })

    if rows:
        st.dataframe(rows, use_container_width=True)

        import pandas as pd
        df = pd.DataFrame(rows).set_index("Run")
        st.bar_chart(df[["P50 (ms)", "P90 (ms)", "P95 (ms)", "P99 (ms)"]])
    else:
        st.info("No parsed samples yet — upload at least one valid result file.")
else:
    st.info("Upload result files above (mix and match tools) to see the comparison table + chart.")

"""Page 6: Latency & SLO Analyzer — evaluate P50/P90/P95/P99 & error rate against SLO targets."""
import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.metrics_calc import evaluate_slo, saturation_flag

st.set_page_config(page_title="Latency & SLO Analyzer", page_icon="📈", layout="wide")
st.title("📈 Latency & SLO Analyzer")
st.caption("Set SLO targets, compare against observed metrics (from APM page or manual entry).")

st.subheader("Observed metrics")
c1, c2, c3, c4 = st.columns(4)
p50 = c1.number_input("P50 (ms)", 0.0, value=200.0)
p90 = c2.number_input("P90 (ms)", 0.0, value=450.0)
p95 = c3.number_input("P95 (ms)", 0.0, value=650.0)
p99 = c4.number_input("P99 (ms)", 0.0, value=1200.0)

c5, c6, c7 = st.columns(3)
error_rate = c5.number_input("Error rate (%)", 0.0, 100.0, value=0.3)
cpu = c6.number_input("CPU %", 0.0, 100.0, value=55.0)
memory = c7.number_input("Memory %", 0.0, 100.0, value=60.0)

st.subheader("SLO targets")
t1, t2, t3, t4 = st.columns(4)
target_p95 = t1.number_input("Target P95 (ms)", 0.0, value=500.0)
target_p99 = t2.number_input("Target P99 (ms)", 0.0, value=1000.0)
target_error = t3.number_input("Max error rate (%)", 0.0, value=1.0)
target_cpu = t4.number_input("Max CPU %", 0.0, value=80.0)

if st.button("Evaluate SLOs"):
    results = [
        evaluate_slo("P95 latency", p95, target_p95, lower_is_better=True),
        evaluate_slo("P99 latency", p99, target_p99, lower_is_better=True),
        evaluate_slo("Error rate", error_rate, target_error, lower_is_better=True),
    ]
    sat = saturation_flag(cpu, memory, cpu_threshold=target_cpu)

    st.divider()
    for r in results:
        icon = "✅" if r.passed else "❌"
        st.write(f"{icon} **{r.metric}**: {r.actual} vs target {r.target}  "
                 f"({'+' if r.margin_pct >= 0 else ''}{r.margin_pct}% margin)")

    if sat:
        st.warning(f"⚠️ Saturation signal — CPU {cpu}% / Memory {memory}% at/above threshold. "
                   "Latency spikes here are likely resource-bound, not just code-path slow.")
    else:
        st.success("No saturation signal at current CPU/memory levels.")

    all_passed = all(r.passed for r in results) and not sat
    st.markdown(f"### Overall: {'🟢 PASS' if all_passed else '🔴 FAIL'}")

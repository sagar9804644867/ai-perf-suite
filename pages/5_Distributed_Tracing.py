"""Page 5: Distributed Tracing — Jaeger/Zipkin trace correlation for slow requests."""
import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.tracing.tracing_connector import get_jaeger_traces, get_zipkin_traces, find_slowest_span

st.set_page_config(page_title="Distributed Tracing", page_icon="🕸️", layout="wide")
st.title("🕸️ Distributed Tracing")
st.caption("Correlate a P99 spike down to the specific span causing it.")

backend = st.radio("Tracing backend", ["Jaeger", "Zipkin"], horizontal=True)
base_url = st.text_input("Base URL", placeholder="http://jaeger-query:16686" if backend == "Jaeger" else "http://zipkin:9411")
service = st.text_input("Service name")
limit = st.slider("Trace limit", 5, 100, 20)

if st.button("Fetch traces") and base_url and service:
    try:
        spans = get_jaeger_traces(base_url, service, limit=limit) if backend == "Jaeger" \
            else get_zipkin_traces(base_url, service, limit=limit)

        if spans:
            st.success(f"{len(spans)} spans fetched")
            slowest = find_slowest_span(spans)
            st.metric("Slowest span", f"{slowest.operation} — {slowest.duration_us/1000:.1f} ms",
                      help=f"trace_id: {slowest.trace_id}")

            st.dataframe(
                [{"Trace ID": s.trace_id[:12], "Service": s.service, "Operation": s.operation,
                  "Duration (ms)": round(s.duration_us / 1000, 2)} for s in
                 sorted(spans, key=lambda x: -x.duration_us)[:50]],
                use_container_width=True,
            )
        else:
            st.info("No traces returned for this service/window.")
    except Exception as e:
        st.error(f"Error fetching traces: {e}")
else:
    st.info("Enter tracing backend URL + service name, then fetch — pairs well with a P99 spike from the APM Metrics page.")

"""
Page 2: APM Metrics
--------------------
Unified dashboard across Dynatrace, Datadog, New Relic, and AppDynamics.
Pick a tool, enter credentials (or load from .env), pick an entity,
see health snapshot + timeseries charts.
"""
import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.apm.dynatrace_connector import DynatraceConnector
from connectors.apm.datadog_connector import DatadogConnector
from connectors.apm.newrelic_connector import NewRelicConnector
from connectors.apm.appdynamics_connector import AppDynamicsConnector

st.set_page_config(page_title="APM Metrics", page_icon="📊", layout="wide")
st.title("📊 Unified APM Metrics")
st.caption("Same dashboard, four backends — Dynatrace / Datadog / New Relic / AppDynamics")

tool = st.selectbox("APM Tool", ["Dynatrace", "Datadog", "New Relic", "AppDynamics"])

with st.form("apm_creds"):
    st.subheader(f"{tool} connection")
    base_url = st.text_input("Base URL", placeholder={
        "Dynatrace": "https://abc12345.live.dynatrace.com",
        "Datadog": "https://api.datadoghq.com",
        "New Relic": "https://api.newrelic.com/graphql",
        "AppDynamics": "https://yourdomain.saas.appdynamics.com",
    }[tool])
    api_token = st.text_input("API Token / Secret", type="password")

    extra_kwargs = {}
    if tool == "Datadog":
        extra_kwargs["app_key"] = st.text_input("Application Key", type="password")
    elif tool == "New Relic":
        extra_kwargs["account_id"] = st.text_input("Account ID")
    elif tool == "AppDynamics":
        extra_kwargs["account_name"] = st.text_input("Account Name")
        extra_kwargs["client_id"] = st.text_input("API Client ID")
        extra_kwargs["application_name"] = st.text_input("Application Name")

    entity = st.text_input("Service / Entity name", placeholder="e.g. checkout-service")
    minutes = st.slider("Lookback window (minutes)", 5, 240, 30)
    submitted = st.form_submit_button("Connect & Fetch")

if submitted:
    connector_map = {
        "Dynatrace": DynatraceConnector,
        "Datadog": DatadogConnector,
        "New Relic": NewRelicConnector,
        "AppDynamics": AppDynamicsConnector,
    }
    connector_cls = connector_map[tool]
    connector = connector_cls(base_url=base_url, api_token=api_token, **extra_kwargs)

    with st.spinner("Testing connection..."):
        ok = False
        try:
            ok = connector.test_connection()
        except Exception as e:
            st.error(f"Connection error: {e}")

    if not ok:
        st.error("Could not connect. Check base URL / token / account fields above.")
        st.info("This module ships with a real, working API integration — "
                "once credentials from your corporate network are added, it goes live. "
                "No code changes needed.")
    else:
        st.success(f"Connected to {tool} ✅")

        if entity:
            with st.spinner(f"Fetching health for {entity}..."):
                try:
                    health = connector.get_service_health(entity, minutes=minutes)
                except Exception as e:
                    st.error(f"Error fetching metrics: {e}")
                    health = None

            if health:
                st.subheader(f"Health snapshot — {entity}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("P50 (ms)", health.response_time_p50 or "—")
                c2.metric("P90 (ms)", health.response_time_p90 or "—")
                c3.metric("P95 (ms)", health.response_time_p95 or "—")
                c4.metric("P99 (ms)", health.response_time_p99 or "—")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("Error Rate %", health.error_rate_pct or "—")
                c6.metric("Throughput (rpm)", health.throughput_rpm or "—")
                c7.metric("CPU %", health.cpu_pct or "—")
                c8.metric("Memory %", health.memory_pct or "—")

                st.divider()
                metric_choice = st.selectbox(
                    "Timeseries metric",
                    ["response_time_p95", "response_time_p99", "error_rate_pct", "throughput_rpm"],
                )
                try:
                    series = connector.get_metric_timeseries(entity, metric_choice, minutes=minutes)
                    if series:
                        import pandas as pd
                        df = pd.DataFrame([{"timestamp": p.timestamp, "value": p.value} for p in series])
                        st.line_chart(df.set_index("timestamp"))
                    else:
                        st.info("No data points returned for this window.")
                except Exception as e:
                    st.error(f"Error fetching timeseries: {e}")
        else:
            st.info("Enter a service/entity name above and click Connect & Fetch again to see metrics.")
else:
    st.info("Fill in credentials for your APM tool and click **Connect & Fetch**. "
            "In the corporate network, load these from `.env` instead of typing them each time — "
            "see `utils/config.py`.")

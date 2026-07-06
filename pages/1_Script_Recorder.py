"""
Page 1: Script Recorder
------------------------
Upload a HAR recording (Chrome DevTools "Save all as HAR with content",
or a Playwright HAR export) and generate ready-to-run scripts for
JMeter, Gatling, Locust, and k6 — all from one recorded flow.
"""
import streamlit as st
import tempfile
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.loadtest.script_generator import (
    parse_har, filter_entries,
    generate_jmeter_jmx, generate_gatling_scala,
    generate_locust_py, generate_k6_js,
)

st.set_page_config(page_title="Script Recorder", page_icon="🎬", layout="wide")
st.title("🎬 Script Recorder → Multi-Tool Generator")
st.caption("Record a flow once (HAR), generate JMeter / Gatling / Locust / k6 scripts from it.")

with st.expander("How to record a HAR file", expanded=False):
    st.markdown("""
    **Chrome/Edge DevTools**
    1. Open DevTools → Network tab → check "Preserve log"
    2. Perform the user flow (login, add to cart, checkout, etc.)
    3. Right-click the request list → **Save all as HAR with content**

    **Playwright** (if scripting the recording)
    ```python
    context = browser.new_context(record_har_path="recording.har")
    page = context.new_page()
    # ...perform flow...
    context.close()  # HAR is flushed on close
    ```
    """)

uploaded = st.file_uploader("Upload HAR file", type=["har"])

col1, col2, col3 = st.columns(3)
with col1:
    include_domains = st.text_input("Include domains (comma-separated, blank = all)", "")
with col2:
    xhr_only = st.checkbox("XHR/API calls only (recommended)", value=True)
with col3:
    st.write("")

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".har") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    entries = parse_har(tmp_path)
    domains_list = [d.strip() for d in include_domains.split(",") if d.strip()] or None
    filtered = filter_entries(entries, include_domains=domains_list, xhr_only=xhr_only)

    st.success(f"Parsed {len(entries)} total requests → {len(filtered)} kept after filtering.")

    st.dataframe(
        [{"Method": e.method, "Path": e.path, "Domain": e.domain,
          "Status": e.status, "Time(ms)": round(e.time_ms, 1), "Type": e.resource_type}
         for e in filtered],
        use_container_width=True,
        height=300,
    )

    if not filtered:
        st.warning("No requests matched your filters. Try unchecking 'XHR only' or clearing domain filter.")
    else:
        st.divider()
        st.subheader("Generate scripts")

        tabs = st.tabs(["JMeter (.jmx)", "Gatling (.scala)", "Locust (.py)", "k6 (.js)"])

        with tabs[0]:
            c1, c2, c3 = st.columns(3)
            threads = c1.number_input("Threads (users)", 1, 5000, 50)
            ramp = c2.number_input("Ramp-up (sec)", 1, 3600, 30)
            loops = c3.number_input("Loops", 1, 1000, 1)
            jmx = generate_jmeter_jmx(filtered, thread_count=threads, ramp_up=ramp, loops=loops)
            st.code(jmx[:2000] + ("\n... (truncated preview)" if len(jmx) > 2000 else ""), language="xml")
            st.download_button("⬇ Download recorded_test.jmx", jmx, "recorded_test.jmx", "application/xml")

        with tabs[1]:
            users = st.number_input("Users", 1, 5000, 50, key="gatling_users")
            ramp_g = st.number_input("Ramp (sec)", 1, 3600, 30, key="gatling_ramp")
            scala = generate_gatling_scala(filtered, users=users, ramp_seconds=ramp_g)
            st.code(scala, language="scala")
            st.download_button("⬇ Download RecordedSimulation.scala", scala, "RecordedSimulation.scala", "text/plain")

        with tabs[2]:
            wmin = st.number_input("Min wait (sec)", 0.0, 60.0, 1.0, key="locust_min")
            wmax = st.number_input("Max wait (sec)", 0.0, 60.0, 3.0, key="locust_max")
            locust_py = generate_locust_py(filtered, wait_min=wmin, wait_max=wmax)
            st.code(locust_py, language="python")
            st.download_button("⬇ Download locustfile.py", locust_py, "locustfile.py", "text/x-python")

        with tabs[3]:
            vus = st.number_input("VUs", 1, 5000, 50, key="k6_vus")
            duration = st.text_input("Duration", "1m", key="k6_duration")
            k6_js = generate_k6_js(filtered, vus=vus, duration=duration)
            st.code(k6_js, language="javascript")
            st.download_button("⬇ Download recorded_test.js", k6_js, "recorded_test.js", "text/javascript")

    os.unlink(tmp_path)
else:
    st.info("Upload a .har file to begin. This becomes the source of truth for all 4 generated scripts.")

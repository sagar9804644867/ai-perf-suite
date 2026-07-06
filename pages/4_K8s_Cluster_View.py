"""Page 4: K8s Cluster View — pods, namespaces, HPA/autoscaling status."""
import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.k8s.k8s_connector import list_namespaces, list_pods, list_hpas

st.set_page_config(page_title="K8s Cluster View", page_icon="☸️", layout="wide")
st.title("☸️ Kubernetes Cluster View")
st.caption("Requires a valid kubeconfig context on the machine running Streamlit.")

context = st.text_input("kubectl context (blank = current context)", value="")

if st.button("Load namespaces"):
    try:
        st.session_state["namespaces"] = list_namespaces(context)
    except Exception as e:
        st.error(f"kubectl error: {e}")
        st.info("Make sure `kubectl` is installed and a kubeconfig is set (KUBE_CONTEXT in .env).")

namespaces = st.session_state.get("namespaces", [])
if namespaces:
    ns = st.selectbox("Namespace", namespaces)
    tab1, tab2 = st.tabs(["Pods", "HPA / Autoscaling"])

    with tab1:
        if st.button("Refresh pods"):
            try:
                pods = list_pods(ns, context)
                st.dataframe([{"Pod": p.name, "Status": p.status, "Restarts": p.restarts,
                               "CPU Req": p.cpu_request, "Mem Req": p.memory_request} for p in pods],
                             use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")

    with tab2:
        if st.button("Refresh HPA"):
            try:
                hpas = list_hpas(ns, context)
                if hpas:
                    st.dataframe([{"HPA": h.name, "Current": h.current_replicas, "Desired": h.desired_replicas,
                                   "Min": h.min_replicas, "Max": h.max_replicas,
                                   "Target CPU%": h.target_cpu_pct, "Current CPU%": h.current_cpu_pct}
                                  for h in hpas], use_container_width=True)
                else:
                    st.info("No HPAs found in this namespace.")
            except Exception as e:
                st.error(f"Error: {e}")
else:
    st.info("Click **Load namespaces** to start (needs kubectl access to your cluster).")

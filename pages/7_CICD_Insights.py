"""Page 7: CI/CD Pipeline Insights — Jenkins / GitHub Actions / GitLab CI recent build status."""
import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from connectors.cicd.cicd_connector import get_jenkins_builds, get_github_actions_runs, get_gitlab_pipelines

st.set_page_config(page_title="CI/CD Insights", page_icon="🔧", layout="wide")
st.title("🔧 CI/CD Pipeline Insights")

source = st.selectbox("CI/CD source", ["Jenkins", "GitHub Actions", "GitLab CI"])

with st.form("cicd_form"):
    if source == "Jenkins":
        base_url = st.text_input("Jenkins base URL")
        job_name = st.text_input("Job name")
        user = st.text_input("Username")
        token = st.text_input("API Token", type="password")
    elif source == "GitHub Actions":
        owner = st.text_input("Repo owner")
        repo = st.text_input("Repo name")
        token = st.text_input("GitHub token", type="password")
    else:
        base_url = st.text_input("GitLab base URL", value="https://gitlab.com")
        project_id = st.text_input("Project ID")
        token = st.text_input("GitLab token", type="password")
    limit = st.slider("Recent builds", 1, 20, 5)
    submitted = st.form_submit_button("Fetch builds")

if submitted:
    try:
        if source == "Jenkins":
            builds = get_jenkins_builds(base_url, job_name, user, token, limit)
        elif source == "GitHub Actions":
            builds = get_github_actions_runs(owner, repo, token, limit)
        else:
            builds = get_gitlab_pipelines(base_url, project_id, token, limit)

        if builds:
            st.dataframe(
                [{"Pipeline": b.pipeline_name, "Build #": b.build_number, "Status": b.status,
                  "Duration (s)": b.duration_sec, "URL": b.url} for b in builds],
                use_container_width=True,
            )
        else:
            st.info("No builds returned.")
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Fill in connection details for your CI/CD tool and fetch recent builds.")

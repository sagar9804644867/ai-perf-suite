"""
config.py — centralised credential loading.
Reads from .env (via python-dotenv) so no secrets are hardcoded or
typed into the Streamlit UI in the corporate network.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# Convenience accessors — see .env.example for the full list
DYNATRACE = {"base_url": get("DYNATRACE_BASE_URL"), "api_token": get("DYNATRACE_API_TOKEN")}
DATADOG = {"base_url": get("DATADOG_BASE_URL", "https://api.datadoghq.com"),
           "api_token": get("DATADOG_API_KEY"), "app_key": get("DATADOG_APP_KEY")}
NEW_RELIC = {"base_url": get("NEWRELIC_BASE_URL", "https://api.newrelic.com/graphql"),
             "api_token": get("NEWRELIC_API_KEY"), "account_id": get("NEWRELIC_ACCOUNT_ID")}
APPDYNAMICS = {"base_url": get("APPD_BASE_URL"), "api_token": get("APPD_CLIENT_SECRET"),
               "account_name": get("APPD_ACCOUNT_NAME"), "client_id": get("APPD_CLIENT_ID"),
               "application_name": get("APPD_APPLICATION_NAME")}

KUBE_CONTEXT = get("KUBE_CONTEXT")
PROMETHEUS_URL = get("PROMETHEUS_URL")
GRAFANA_URL = get("GRAFANA_URL")
GRAFANA_API_KEY = get("GRAFANA_API_KEY")
JAEGER_URL = get("JAEGER_URL")
ZIPKIN_URL = get("ZIPKIN_URL")
JENKINS_URL = get("JENKINS_URL")
JENKINS_TOKEN = get("JENKINS_TOKEN")
GITHUB_TOKEN = get("GITHUB_TOKEN")
GITLAB_TOKEN = get("GITLAB_TOKEN")

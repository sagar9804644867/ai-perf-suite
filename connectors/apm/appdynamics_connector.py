"""
appdynamics_connector.py
-------------------------
Uses AppDynamics Controller REST API (metric-data endpoint).
Docs: https://docs.appdynamics.com/appd/24.x/latest/en/extend-appdynamics/appdynamics-apis/metric-and-snapshot-api

Auth: OAuth2 client credentials -> Bearer token, OR basic auth with
      "<username>@<account>" / password (API client recommended for prod).

base_url example: https://<your-domain>.saas.appdynamics.com
Requires extra kwargs: account_name, application_name
"""
import time
import requests
from typing import List
from .base_connector import APMConnector, MetricPoint, ServiceHealth

METRIC_PATH_TEMPLATES = {
    "response_time_p50": "Business Transaction Performance|Business Transactions|{service}|Average Response Time (ms)",
    "response_time_p90": "Business Transaction Performance|Business Transactions|{service}|95th Percentile Response Time (ms)",
    "response_time_p95": "Business Transaction Performance|Business Transactions|{service}|95th Percentile Response Time (ms)",
    "response_time_p99": "Business Transaction Performance|Business Transactions|{service}|99th Percentile Response Time (ms)",
    "error_rate_pct": "Business Transaction Performance|Business Transactions|{service}|Errors per Minute",
    "throughput_rpm": "Business Transaction Performance|Business Transactions|{service}|Calls per Minute",
    "cpu_pct": "Application Infrastructure Performance|{service}|Hardware Resources|CPU|%Busy",
    "memory_pct": "Application Infrastructure Performance|{service}|Hardware Resources|Memory|Used %",
}


class AppDynamicsConnector(APMConnector):
    name = "AppDynamics"

    def __init__(self, base_url, api_token, **kwargs):
        super().__init__(base_url, api_token, **kwargs)
        self._access_token = None
        self._token_expiry = 0

    def _get_oauth_token(self) -> str:
        """Client-credentials OAuth flow. api_token here is the client secret;
        pass client_id via extra kwarg."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        account_name = self.extra.get("account_name")
        client_id = self.extra.get("client_id")
        r = requests.post(
            f"{self.base_url}/controller/api/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": f"{client_id}@{account_name}",
                "client_secret": self.api_token,
            },
            headers={"Content-Type": "application/vnd.appd.cntrl+protobuf;v=1"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 300) - 30
        return self._access_token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_oauth_token()}"}

    def test_connection(self) -> bool:
        try:
            token = self._get_oauth_token()
            return bool(token)
        except requests.RequestException:
            return False

    def list_entities(self) -> List[str]:
        account_name = self.extra.get("account_name")
        app_name = self.extra.get("application_name")
        r = requests.get(
            f"{self.base_url}/controller/rest/applications/{app_name}/business-transactions",
            headers=self._headers(), params={"output": "JSON"}, timeout=20,
        )
        if r.status_code != 200:
            return []
        return [bt.get("name") for bt in r.json()]

    def get_metric_timeseries(
        self, entity: str, metric_name: str, minutes: int = 60,
        start_epoch_ms=None, end_epoch_ms=None,
    ) -> List[MetricPoint]:
        app_name = self.extra.get("application_name")
        template = METRIC_PATH_TEMPLATES.get(metric_name)
        if not template:
            return []
        metric_path = template.format(service=entity)
        params = {"metric-path": metric_path, "output": "JSON"}
        if start_epoch_ms and end_epoch_ms:
            params["time-range-type"] = "BETWEEN_TIMES"
            params["start-time"] = int(start_epoch_ms)
            params["end-time"] = int(end_epoch_ms)
        else:
            params["time-range-type"] = "BEFORE_NOW"
            params["duration-in-mins"] = minutes

        r = requests.get(
            f"{self.base_url}/controller/rest/applications/{app_name}/metric-data",
            headers=self._headers(), params=params, timeout=20,
        )
        r.raise_for_status()
        points = []
        for metric in r.json():
            for dp in metric.get("metricValues", []):
                points.append(MetricPoint(
                    timestamp=str(dp.get("startTimeInMillis")),
                    value=float(dp.get("value", 0)),
                    entity=entity, metric_name=metric_name,
                ))
        return points

    def get_service_health(
        self, entity: str, minutes: int = 30, start_epoch_ms=None, end_epoch_ms=None,
    ) -> ServiceHealth:
        health = ServiceHealth(entity=entity)
        for field_name in METRIC_PATH_TEMPLATES:
            try:
                pts = self.get_metric_timeseries(
                    entity, field_name, minutes=minutes,
                    start_epoch_ms=start_epoch_ms, end_epoch_ms=end_epoch_ms,
                )
                if pts:
                    avg_val = sum(p.value for p in pts) / len(pts)
                    setattr(health, field_name, round(avg_val, 2))
            except requests.RequestException:
                continue
        return health

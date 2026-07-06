"""
dynatrace_connector.py
-----------------------
Uses Dynatrace Environment API v2 (Metrics + Entities).
Docs: https://docs.dynatrace.com/docs/dynatrace-api/environment-api/metric-v2

Auth: API token with scopes `metrics.read`, `entities.read`
Header: Authorization: Api-Token <token>

base_url example: https://abc12345.live.dynatrace.com
"""
import requests
from typing import List
from .base_connector import APMConnector, MetricPoint, ServiceHealth

# Common Dynatrace built-in metric keys used for the standard health snapshot
METRIC_MAP = {
    "response_time_p50": "builtin:service.response.time:percentile(50)",
    "response_time_p90": "builtin:service.response.time:percentile(90)",
    "response_time_p95": "builtin:service.response.time:percentile(95)",
    "response_time_p99": "builtin:service.response.time:percentile(99)",
    "error_rate_pct": "builtin:service.errors.total.rate",
    "throughput_rpm": "builtin:service.requestCount.total",
    "cpu_pct": "builtin:tech.generic.cpu.usage",
    "memory_pct": "builtin:tech.generic.mem.usage",
}


class DynatraceConnector(APMConnector):
    name = "Dynatrace"

    def _headers(self):
        return {"Authorization": f"Api-Token {self.api_token}"}

    def test_connection(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/v2/entities",
                              headers=self._headers(),
                              params={"pageSize": 1}, timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_entities(self) -> List[str]:
        r = requests.get(
            f"{self.base_url}/api/v2/entities",
            headers=self._headers(),
            params={"entitySelector": "type(SERVICE)", "pageSize": 100},
            timeout=15,
        )
        r.raise_for_status()
        return [e["displayName"] for e in r.json().get("entities", [])]

    def get_metric_timeseries(
        self, entity: str, metric_name: str, minutes: int = 60,
        start_epoch_ms=None, end_epoch_ms=None,
    ) -> List[MetricPoint]:
        metric_selector = METRIC_MAP.get(metric_name, metric_name)
        params = {
            "metricSelector": metric_selector,
            "entitySelector": f'type(SERVICE),entityName.equals("{entity}")',
            "resolution": "1m",
        }
        if start_epoch_ms and end_epoch_ms:
            # Dynatrace accepts absolute epoch milliseconds directly
            params["from"] = int(start_epoch_ms)
            params["to"] = int(end_epoch_ms)
        else:
            params["from"] = f"now-{minutes}m"

        r = requests.get(
            f"{self.base_url}/api/v2/metrics/query",
            headers=self._headers(), params=params, timeout=20,
        )
        r.raise_for_status()
        points = []
        for result in r.json().get("result", []):
            for series in result.get("data", []):
                for ts, val in zip(series.get("timestamps", []), series.get("values", [])):
                    if val is not None:
                        points.append(MetricPoint(
                            timestamp=str(ts), value=float(val),
                            entity=entity, metric_name=metric_name,
                        ))
        return points

    def get_service_health(
        self, entity: str, minutes: int = 30, start_epoch_ms=None, end_epoch_ms=None,
    ) -> ServiceHealth:
        health = ServiceHealth(entity=entity)
        for field_name, metric_key in METRIC_MAP.items():
            try:
                pts = self.get_metric_timeseries(
                    entity, field_name, minutes=minutes,
                    start_epoch_ms=start_epoch_ms, end_epoch_ms=end_epoch_ms,
                )
                if pts:
                    # Use the average across the window rather than just the
                    # last point — a single "latest value" is misleading when
                    # the window is a historical test run, not "right now".
                    avg_val = sum(p.value for p in pts) / len(pts)
                    setattr(health, field_name, round(avg_val, 2))
            except requests.RequestException:
                continue
        return health

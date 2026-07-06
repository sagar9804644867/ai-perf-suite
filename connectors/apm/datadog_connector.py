"""
datadog_connector.py
---------------------
Uses Datadog Metrics API v1 (query) + APM/trace service metrics.
Docs: https://docs.datadoghq.com/api/latest/metrics/#query-timeseries-points

Auth needs BOTH:
  DD-API-KEY    (api_token param)
  DD-APPLICATION-KEY (pass via extra kwarg app_key=...)

base_url example: https://api.datadoghq.com  (or https://api.datadoghq.eu for EU org)
"""
import time
import requests
from typing import List
from .base_connector import APMConnector, MetricPoint, ServiceHealth

# Datadog APM metrics are namespaced trace.<service>.request / errors / duration
METRIC_TEMPLATES = {
    "response_time_p50": "trace.{service}.request.duration.by.resource_name.p50",
    "response_time_p90": "trace.{service}.request.duration.by.resource_name.p90",
    "response_time_p95": "trace.{service}.request.duration.by.resource_name.p95",
    "response_time_p99": "trace.{service}.request.duration.by.resource_name.p99",
    "error_rate_pct": "trace.{service}.request.errors",
    "throughput_rpm": "trace.{service}.request.hits",
    "cpu_pct": "system.cpu.user{{service:{service}}}",
    "memory_pct": "system.mem.pct_usable{{service:{service}}}",
}


class DatadogConnector(APMConnector):
    name = "Datadog"

    def _headers(self):
        return {
            "DD-API-KEY": self.api_token,
            "DD-APPLICATION-KEY": self.extra.get("app_key", ""),
        }

    def test_connection(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/v1/validate", headers=self._headers(), timeout=10)
            return r.status_code == 200 and r.json().get("valid", False)
        except requests.RequestException:
            return False

    def list_entities(self) -> List[str]:
        # APM services list endpoint (requires apm_read scope)
        r = requests.get(
            f"{self.base_url}/api/v1/service_dependencies",
            headers=self._headers(), timeout=15,
        )
        if r.status_code != 200:
            return []
        return list(r.json().keys())

    def get_metric_timeseries(
        self, entity: str, metric_name: str, minutes: int = 60,
        start_epoch_ms=None, end_epoch_ms=None,
    ) -> List[MetricPoint]:
        query_template = METRIC_TEMPLATES.get(metric_name, metric_name)
        query = query_template.format(service=entity) if "{service}" in query_template else query_template

        if start_epoch_ms and end_epoch_ms:
            from_ts, to_ts = int(start_epoch_ms / 1000), int(end_epoch_ms / 1000)
        else:
            now = int(time.time())
            from_ts, to_ts = now - minutes * 60, now

        r = requests.get(
            f"{self.base_url}/api/v1/query",
            headers=self._headers(),
            params={"from": from_ts, "to": to_ts, "query": query},
            timeout=20,
        )
        r.raise_for_status()
        points = []
        for series in r.json().get("series", []):
            for ts, val in series.get("pointlist", []):
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
        for field_name in METRIC_TEMPLATES:
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

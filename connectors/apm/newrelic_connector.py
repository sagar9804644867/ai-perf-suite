"""
newrelic_connector.py
----------------------
Uses New Relic NerdGraph (GraphQL) API — the modern unified API surface
for APM data, replacing the older REST v2 API.
Docs: https://docs.newrelic.com/docs/apis/nerdgraph/get-started/introduction-new-relic-nerdgraph

Auth: User API key in header 'Api-Key'
Requires: account_id passed via extra kwarg (New Relic account ID, not app ID)

base_url is fixed: https://api.newrelic.com/graphql (base_url param can be
left as this value, or the EU endpoint https://api.eu.newrelic.com/graphql)
"""
import requests
from typing import List
from .base_connector import APMConnector, MetricPoint, ServiceHealth

NRQL_TEMPLATES = {
    "response_time_p50": "SELECT percentile(duration, 50) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "response_time_p90": "SELECT percentile(duration, 90) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "response_time_p95": "SELECT percentile(duration, 95) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "response_time_p99": "SELECT percentile(duration, 99) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "error_rate_pct": "SELECT percentage(count(*), WHERE error IS true) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "throughput_rpm": "SELECT rate(count(*), 1 minute) FROM Transaction WHERE appName = '{service}' {time_clause} TIMESERIES",
    "cpu_pct": "SELECT average(cpuPercent) FROM SystemSample WHERE appName = '{service}' {time_clause} TIMESERIES",
    "memory_pct": "SELECT average(memoryUsedPercent) FROM SystemSample WHERE appName = '{service}' {time_clause} TIMESERIES",
}


class NewRelicConnector(APMConnector):
    name = "New Relic"

    def _headers(self):
        return {"Api-Key": self.api_token, "Content-Type": "application/json"}

    def _run_nrql(self, nrql: str):
        account_id = self.extra.get("account_id")
        query = """
        query($accountId: Int!, $nrql: Nrql!) {
          actor {
            account(id: $accountId) {
              nrql(query: $nrql) {
                results
              }
            }
          }
        }
        """
        r = requests.post(
            self.base_url,
            headers=self._headers(),
            json={"query": query, "variables": {"accountId": int(account_id), "nrql": nrql}},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])

    def test_connection(self) -> bool:
        try:
            results = self._run_nrql("SELECT count(*) FROM Transaction SINCE 5 MINUTES AGO")
            return results is not None
        except requests.RequestException:
            return False

    def list_entities(self) -> List[str]:
        query = """
        {
          actor {
            entitySearch(query: "type = 'APPLICATION'") {
              results { entities { name } }
            }
          }
        }
        """
        r = requests.post(self.base_url, headers=self._headers(), json={"query": query}, timeout=20)
        if r.status_code != 200:
            return []
        entities = (r.json().get("data", {}).get("actor", {})
                    .get("entitySearch", {}).get("results", {}).get("entities", []))
        return [e["name"] for e in entities]

    def get_metric_timeseries(
        self, entity: str, metric_name: str, minutes: int = 60,
        start_epoch_ms=None, end_epoch_ms=None,
    ) -> List[MetricPoint]:
        template = NRQL_TEMPLATES.get(metric_name)
        if not template:
            return []
        if start_epoch_ms and end_epoch_ms:
            time_clause = f"SINCE {int(start_epoch_ms)} UNTIL {int(end_epoch_ms)}"
        else:
            time_clause = f"SINCE {minutes} MINUTES AGO"
        nrql = template.format(service=entity, time_clause=time_clause)
        results = self._run_nrql(nrql)
        points = []
        for row in results:
            ts = row.get("beginTimeSeconds") or row.get("endTimeSeconds")
            value = next((v for k, v in row.items() if k not in ("beginTimeSeconds", "endTimeSeconds")), None)
            if value is not None:
                points.append(MetricPoint(timestamp=str(ts), value=float(value),
                                           entity=entity, metric_name=metric_name))
        return points

    def get_service_health(
        self, entity: str, minutes: int = 30, start_epoch_ms=None, end_epoch_ms=None,
    ) -> ServiceHealth:
        health = ServiceHealth(entity=entity)
        for field_name in NRQL_TEMPLATES:
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

"""
tracing_connector.py
----------------------
Jaeger and Zipkin query APIs — used to correlate a slow request
(flagged by APM P99 spike) down to the specific span/service causing it.

Jaeger Query API: GET /api/traces?service=...&operation=...&lookback=1h
Zipkin API:       GET /api/v2/traces?serviceName=...&limit=...
"""
import requests
from dataclasses import dataclass
from typing import List


@dataclass
class Span:
    trace_id: str
    span_id: str
    service: str
    operation: str
    duration_us: float
    start_time_us: float


def get_jaeger_traces(base_url: str, service: str, operation: str = "",
                       lookback: str = "1h", limit: int = 20) -> List[Span]:
    params = {"service": service, "lookback": lookback, "limit": limit}
    if operation:
        params["operation"] = operation
    r = requests.get(f"{base_url}/api/traces", params=params, timeout=15)
    r.raise_for_status()
    spans = []
    for trace in r.json().get("data", []):
        for span in trace.get("spans", []):
            proc = trace.get("processes", {}).get(span.get("processID", ""), {})
            spans.append(Span(
                trace_id=trace.get("traceID", ""),
                span_id=span.get("spanID", ""),
                service=proc.get("serviceName", service),
                operation=span.get("operationName", ""),
                duration_us=span.get("duration", 0),
                start_time_us=span.get("startTime", 0),
            ))
    return spans


def get_zipkin_traces(base_url: str, service_name: str, limit: int = 20) -> List[Span]:
    r = requests.get(f"{base_url}/api/v2/traces",
                      params={"serviceName": service_name, "limit": limit}, timeout=15)
    r.raise_for_status()
    spans = []
    for trace in r.json():
        for span in trace:
            local = span.get("localEndpoint", {})
            spans.append(Span(
                trace_id=span.get("traceId", ""),
                span_id=span.get("id", ""),
                service=local.get("serviceName", service_name),
                operation=span.get("name", ""),
                duration_us=span.get("duration", 0),
                start_time_us=span.get("timestamp", 0),
            ))
    return spans


def find_slowest_span(spans: List[Span]) -> Span:
    return max(spans, key=lambda s: s.duration_us) if spans else None

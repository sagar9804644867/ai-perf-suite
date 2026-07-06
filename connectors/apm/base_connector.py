"""
base_connector.py
------------------
Common interface all APM connectors implement, so the Streamlit page
can treat Dynatrace/Datadog/New Relic/AppDynamics interchangeably.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MetricPoint:
    timestamp: str      # ISO8601
    value: float
    entity: str          # service/host/process name
    metric_name: str     # e.g. "response_time_p95", "error_rate", "cpu_usage"
    unit: str = ""


@dataclass
class ServiceHealth:
    entity: str
    response_time_p50: Optional[float] = None
    response_time_p90: Optional[float] = None
    response_time_p95: Optional[float] = None
    response_time_p99: Optional[float] = None
    error_rate_pct: Optional[float] = None
    throughput_rpm: Optional[float] = None
    cpu_pct: Optional[float] = None
    memory_pct: Optional[float] = None
    apdex: Optional[float] = None


class APMConnector(ABC):
    """All connectors take (base_url/account, token) at init and expose
    the same three methods, so the UI layer never branches on tool type."""

    name: str = "base"

    def __init__(self, base_url: str, api_token: str, **kwargs):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.extra = kwargs  # e.g. app_key for New Relic, account_name for AppD

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if credentials/base_url are valid."""
        ...

    @abstractmethod
    def get_service_health(
        self, entity: str, minutes: int = 30,
        start_epoch_ms: Optional[int] = None, end_epoch_ms: Optional[int] = None,
    ) -> ServiceHealth:
        """Return a rolled-up health snapshot for one service/entity.

        If start_epoch_ms/end_epoch_ms are given, the connector queries
        that EXACT window (e.g. the actual test run duration from a JTL)
        instead of a relative "last N minutes" window. This is what makes
        report generation automatic — no lookback guessing needed once
        the test's start/end time is known.
        """
        ...

    @abstractmethod
    def get_metric_timeseries(
        self, entity: str, metric_name: str, minutes: int = 60,
        start_epoch_ms: Optional[int] = None, end_epoch_ms: Optional[int] = None,
    ) -> List[MetricPoint]:
        """Return a timeseries for charting. Same absolute-window override
        as get_service_health."""
        ...

    @abstractmethod
    def list_entities(self) -> List[str]:
        """Return discoverable services/hosts/processes for a dropdown."""
        ...

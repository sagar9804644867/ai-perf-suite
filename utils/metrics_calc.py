"""
metrics_calc.py
-----------------
Shared math for latency percentiles, error rate, throughput, and
saturation — used by the Load Test Comparator and Latency/SLO Analyzer
pages, and to cross-check APM-reported percentiles against raw samples.
"""
import statistics
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class SLOResult:
    metric: str
    target: float
    actual: float
    passed: bool
    margin_pct: float  # positive = under target (good) for latency; adjust per metric


def percentile(data: Sequence[float], p: float) -> float:
    """Nearest-rank percentile. p in [0, 100]."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def latency_summary(samples_ms: Sequence[float]) -> dict:
    if not samples_ms:
        return {"p50": 0, "p90": 0, "p95": 0, "p99": 0, "mean": 0, "max": 0, "min": 0}
    return {
        "p50": round(percentile(samples_ms, 50), 1),
        "p90": round(percentile(samples_ms, 90), 1),
        "p95": round(percentile(samples_ms, 95), 1),
        "p99": round(percentile(samples_ms, 99), 1),
        "mean": round(statistics.fmean(samples_ms), 1),
        "max": round(max(samples_ms), 1),
        "min": round(min(samples_ms), 1),
    }


def error_rate_pct(total_requests: int, failed_requests: int) -> float:
    if total_requests == 0:
        return 0.0
    return round((failed_requests / total_requests) * 100, 3)


def throughput_rpm(total_requests: int, duration_seconds: float) -> float:
    if duration_seconds <= 0:
        return 0.0
    return round((total_requests / duration_seconds) * 60, 1)


def saturation_flag(cpu_pct: float, memory_pct: float, cpu_threshold: float = 80.0,
                     memory_threshold: float = 80.0) -> bool:
    """True if either resource is at/above threshold — a saturation signal
    worth correlating against latency spikes."""
    return cpu_pct >= cpu_threshold or memory_pct >= memory_threshold


def evaluate_slo(metric_name: str, actual: float, target: float, lower_is_better: bool = True) -> SLOResult:
    if lower_is_better:
        passed = actual <= target
        margin_pct = round(((target - actual) / target) * 100, 1) if target else 0.0
    else:
        passed = actual >= target
        margin_pct = round(((actual - target) / target) * 100, 1) if target else 0.0
    return SLOResult(metric=metric_name, target=target, actual=actual, passed=passed, margin_pct=margin_pct)

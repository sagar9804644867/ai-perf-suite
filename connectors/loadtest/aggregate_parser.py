"""
aggregate_parser.py
---------------------
Parses the two common JMeter exports into the same per-API rollup shape
used in section "3.2 Response Time Details" of the report template:
API Name | Samples | Avg | Min | Max | P90 | P95 | Error Rate | SLA Met

Supports:
  1. JMeter's built-in "Aggregate Report" listener -> Save Table Data (CSV)
     columns: Label,# Samples,Average,Min,Max,Std. Dev.,Error %,Throughput,...
     (no percentiles by default unless "90% Line" etc. columns were added)
  2. Raw .jtl results file -> percentiles computed per label from samples
"""
import csv
from dataclasses import dataclass, field
from typing import Dict, List
from utils.metrics_calc import percentile, error_rate_pct


@dataclass
class ApiRow:
    api_name: str
    samples: int
    avg_ms: float
    min_ms: float
    max_ms: float
    p90_ms: float
    p95_ms: float
    error_rate: float
    sla_target_ms: float = 5000.0

    @property
    def sla_met(self) -> bool:
        return self.p90_ms <= self.sla_target_ms


def parse_aggregate_csv(path: str, sla_target_ms: float = 5000.0) -> List[ApiRow]:
    """JMeter Aggregate Report 'Save Table Data' export."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            def g(*keys, default=0.0):
                for k in keys:
                    if k in row and row[k] not in (None, ""):
                        return row[k]
                return default

            samples = int(float(g("# Samples", "Samples", default=0)))
            error_pct_raw = g("Error %", "Error%", default="0")
            error_pct = float(str(error_pct_raw).replace("%", "") or 0)

            rows.append(ApiRow(
                api_name=row.get("Label", "unknown"),
                samples=samples,
                avg_ms=float(g("Average", default=0)),
                min_ms=float(g("Min", default=0)),
                max_ms=float(g("Max", default=0)),
                p90_ms=float(g("90% Line", "pct1ResponseTime", default=0)),
                p95_ms=float(g("95% Line", "pct2ResponseTime", default=0)),
                error_rate=error_pct,
                sla_target_ms=sla_target_ms,
            ))
    return rows


def parse_jtl_to_aggregate(path: str, sla_target_ms: float = 5000.0) -> List[ApiRow]:
    """Raw .jtl results -> compute per-label rollup with real percentiles."""
    by_label: Dict[str, List[dict]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label", "unknown")
            by_label.setdefault(label, []).append(row)

    rows = []
    for label, samples in by_label.items():
        elapsed = [float(s.get("elapsed", 0)) for s in samples]
        failed = sum(1 for s in samples if s.get("success", "true").lower() != "true")
        rows.append(ApiRow(
            api_name=label,
            samples=len(samples),
            avg_ms=round(sum(elapsed) / len(elapsed), 1) if elapsed else 0,
            min_ms=min(elapsed) if elapsed else 0,
            max_ms=max(elapsed) if elapsed else 0,
            p90_ms=round(percentile(elapsed, 90), 1),
            p95_ms=round(percentile(elapsed, 95), 1),
            error_rate=error_rate_pct(len(samples), failed),
            sla_target_ms=sla_target_ms,
        ))
    return rows


@dataclass
class ParsedRun:
    """Everything auto-derivable from a raw JTL — feeds Test Configuration
    and the report charts without the user typing anything."""
    rows: List[ApiRow]
    raw_elapsed: List[float]              # every sample's elapsed ms, for histogram
    timestamps_ms: List[float]            # every sample's epoch ms, for throughput-over-time
    start_time_epoch_ms: float = 0.0
    end_time_epoch_ms: float = 0.0
    duration_sec: float = 0.0
    max_threads: int = 0
    total_samples: int = 0
    success_rate_pct: float = 100.0


def parse_jtl_detailed(path: str, sla_target_ms: float = 5000.0) -> ParsedRun:
    """Single pass over a raw .jtl that gives us both the per-API rollup
    AND the raw data needed for charts and auto-filled test config."""
    from collections import defaultdict
    by_label: Dict[str, List[dict]] = defaultdict(list)
    raw_elapsed: List[float] = []
    timestamps: List[float] = []
    max_threads = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label", "unknown")
            by_label[label].append(row)
            try:
                raw_elapsed.append(float(row.get("elapsed", 0)))
            except (ValueError, TypeError):
                pass
            try:
                timestamps.append(float(row.get("timeStamp", 0)))
            except (ValueError, TypeError):
                pass
            try:
                threads = int(row.get("allThreads", 0))
                max_threads = max(max_threads, threads)
            except (ValueError, TypeError):
                pass

    rows = []
    for label, samples in by_label.items():
        elapsed = [float(s.get("elapsed", 0)) for s in samples]
        failed = sum(1 for s in samples if s.get("success", "true").lower() != "true")
        rows.append(ApiRow(
            api_name=label,
            samples=len(samples),
            avg_ms=round(sum(elapsed) / len(elapsed), 1) if elapsed else 0,
            min_ms=min(elapsed) if elapsed else 0,
            max_ms=max(elapsed) if elapsed else 0,
            p90_ms=round(percentile(elapsed, 90), 1),
            p95_ms=round(percentile(elapsed, 95), 1),
            error_rate=error_rate_pct(len(samples), failed),
            sla_target_ms=sla_target_ms,
        ))

    total_samples = len(raw_elapsed)
    total_failed = sum(1 for lbl_samples in by_label.values() for s in lbl_samples
                        if s.get("success", "true").lower() != "true")
    start_ts = min(timestamps) if timestamps else 0.0
    end_ts = max(timestamps) if timestamps else 0.0
    err_pct = error_rate_pct(total_samples, total_failed)

    return ParsedRun(
        rows=rows,
        raw_elapsed=raw_elapsed,
        timestamps_ms=timestamps,
        start_time_epoch_ms=start_ts,
        end_time_epoch_ms=end_ts,
        duration_sec=round((end_ts - start_ts) / 1000, 1) if end_ts > start_ts else 0.0,
        max_threads=max_threads,
        total_samples=total_samples,
        success_rate_pct=round(100 - err_pct, 2),
    )


def overall_stats(rows: List[ApiRow]) -> dict:
    """Section 3.1 rollup across all APIs — weighted by sample count."""
    total_samples = sum(r.samples for r in rows) or 1
    weighted_avg = sum(r.avg_ms * r.samples for r in rows) / total_samples
    return {
        "total_samples": total_samples,
        "avg_ms": round(weighted_avg, 1),
        "min_ms": min((r.min_ms for r in rows), default=0),
        "max_ms": max((r.max_ms for r in rows), default=0),
        "p90_ms": round(sum(r.p90_ms * r.samples for r in rows) / total_samples, 1),
        "p95_ms": round(sum(r.p95_ms * r.samples for r in rows) / total_samples, 1),
        "success_rate_pct": round(100 - (sum(r.error_rate * r.samples for r in rows) / total_samples), 2),
    }

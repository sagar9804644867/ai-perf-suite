"""
result_parsers.py
-------------------
Parse result/report output from each load tool into a common
sample list so they can be compared side by side, independent of
which tool produced them.

Supported inputs:
  - JMeter:  .jtl / .csv results file (fieldnames: timeStamp,elapsed,label,responseCode,success,...)
  - Gatling: simulation.log (tab-separated, REQUEST lines)
  - Locust:  --csv export -> *_stats_history.csv
  - k6:      --out json=results.json (NDJSON, Point metrics)
"""
import csv
import json
from dataclasses import dataclass
from typing import List


@dataclass
class Sample:
    label: str
    elapsed_ms: float
    success: bool
    timestamp_ms: float = 0.0


def parse_jmeter_jtl(path: str) -> List[Sample]:
    samples = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                samples.append(Sample(
                    label=row.get("label", "unknown"),
                    elapsed_ms=float(row.get("elapsed", 0)),
                    success=row.get("success", "true").lower() == "true",
                    timestamp_ms=float(row.get("timeStamp", 0)),
                ))
            except (ValueError, TypeError):
                continue
    return samples


def parse_gatling_log(path: str) -> List[Sample]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            # Gatling REQUEST lines: REQUEST <scenario> <userId> <reqName> <start> <end> <status>
            if len(parts) >= 6 and parts[0] == "REQUEST":
                try:
                    req_name = parts[3]
                    start, end = float(parts[4]), float(parts[5])
                    status = parts[6] if len(parts) > 6 else "OK"
                    samples.append(Sample(
                        label=req_name,
                        elapsed_ms=end - start,
                        success=(status.upper() == "OK"),
                        timestamp_ms=start,
                    ))
                except (ValueError, IndexError):
                    continue
    return samples


def parse_locust_csv(stats_history_path: str) -> List[Sample]:
    """Locust's *_stats_history.csv has rolling aggregates, not per-request
    samples, so each row becomes one representative sample per name/timestamp
    using the average response time — good enough for trend comparison."""
    samples = []
    with open(stats_history_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                total_failures = float(row.get("Total Failure Count", 0))
                total_requests = float(row.get("Total Request Count", 1)) or 1
                samples.append(Sample(
                    label=row.get("Name", "Aggregated"),
                    elapsed_ms=float(row.get("Total Average Response Time", 0)),
                    success=(total_failures / total_requests) < 0.01,
                    timestamp_ms=float(row.get("Timestamp", 0)),
                ))
            except (ValueError, TypeError):
                continue
    return samples


def parse_k6_json(path: str) -> List[Sample]:
    """k6 --out json=results.json produces NDJSON; we pull http_req_duration Points."""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "Point" and obj.get("metric") == "http_req_duration":
                data = obj.get("data", {})
                tags = data.get("tags", {})
                samples.append(Sample(
                    label=tags.get("name", tags.get("url", "unknown")),
                    elapsed_ms=float(data.get("value", 0)),
                    success=tags.get("status", "200") not in ("0",) and not str(tags.get("status", "")).startswith(("4", "5")),
                    timestamp_ms=0.0,
                ))
    return samples

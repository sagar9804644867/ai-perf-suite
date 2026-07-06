"""
report_charts.py
------------------
Generates the charts that go into the report — response time
distribution, P90/P95 by API, throughput over time, APM comparison.
Rendered as base64 PNGs so the final HTML report is a single
self-contained file (no external chart JS needed to view it).
"""
import base64
import io
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LIGHT_BG = "#FFFFFF"
GRID_COLOR = "#E0E4E8"
PRIMARY = "#0F62FE"
ACCENT = "#D97757"


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=LIGHT_BG)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _style_axes(ax):
    ax.set_facecolor(LIGHT_BG)
    ax.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors="#444444", labelsize=9)


def response_time_histogram(samples_ms: List[float], title: str = "Response Time Distribution") -> Optional[str]:
    if not samples_ms:
        return None
    fig, ax = plt.subplots(figsize=(8, 3.5), facecolor=LIGHT_BG)
    ax.hist(samples_ms, bins=30, color=PRIMARY, alpha=0.85, edgecolor="white")
    ax.set_title(title, fontsize=12, color="#1A1A1A")
    ax.set_xlabel("Response time (ms)", fontsize=10)
    ax.set_ylabel("Frequency", fontsize=10)
    _style_axes(ax)
    return _fig_to_base64(fig)


def p90_by_api_chart(api_names: List[str], p90_values: List[float],
                      title: str = "P90 Response Time by API") -> Optional[str]:
    if not api_names:
        return None
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.4 * len(api_names))), facecolor=LIGHT_BG)
    y_pos = range(len(api_names))
    ax.barh(y_pos, p90_values, color=PRIMARY, alpha=0.85)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(api_names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("P90 (ms)", fontsize=10)
    ax.set_title(title, fontsize=12, color="#1A1A1A")
    _style_axes(ax)
    return _fig_to_base64(fig)


def throughput_over_time_chart(timestamps_ms: List[float], bucket_seconds: int = 30,
                                title: str = "Throughput Over Time") -> Optional[str]:
    """Buckets raw sample timestamps into a requests-per-bucket time series."""
    if not timestamps_ms or len(timestamps_ms) < 2:
        return None
    start = min(timestamps_ms)
    buckets = {}
    for ts in timestamps_ms:
        bucket = int((ts - start) / 1000 // bucket_seconds)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    xs = sorted(buckets.keys())
    ys = [buckets[x] for x in xs]
    x_seconds = [x * bucket_seconds for x in xs]

    fig, ax = plt.subplots(figsize=(9, 3.5), facecolor=LIGHT_BG)
    ax.plot(x_seconds, ys, color=PRIMARY, linewidth=2)
    ax.fill_between(x_seconds, ys, color=PRIMARY, alpha=0.15)
    ax.set_xlabel("Elapsed test time (sec)", fontsize=10)
    ax.set_ylabel(f"Requests / {bucket_seconds}s", fontsize=10)
    ax.set_title(title, fontsize=12, color="#1A1A1A")
    _style_axes(ax)
    return _fig_to_base64(fig)


def apm_comparison_chart(entities: List[str], p95_values: List[float], p99_values: List[float],
                          title: str = "APM Response Time (P95 vs P99)") -> Optional[str]:
    if not entities:
        return None
    fig, ax = plt.subplots(figsize=(8, 3.5), facecolor=LIGHT_BG)
    x = range(len(entities))
    width = 0.35
    ax.bar([i - width / 2 for i in x], p95_values, width, label="P95", color=PRIMARY, alpha=0.85)
    ax.bar([i + width / 2 for i in x], p99_values, width, label="P99", color=ACCENT, alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(entities, fontsize=9, rotation=15, ha="right")
    ax.set_ylabel("ms", fontsize=10)
    ax.set_title(title, fontsize=12, color="#1A1A1A")
    ax.legend(frameon=False, fontsize=9)
    _style_axes(ax)
    return _fig_to_base64(fig)

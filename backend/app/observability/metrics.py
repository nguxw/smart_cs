from __future__ import annotations

import threading
from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]]
        self._histograms = defaultdict(list)

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._histograms[key].append(value)

    def render_prometheus(self) -> str:
        lines: list[str] = [
            "# HELP smartcs_request_total HTTP requests handled by the API.",
            "# TYPE smartcs_request_total counter",
            "# HELP smartcs_request_latency_ms HTTP request latency in milliseconds.",
            "# TYPE smartcs_request_latency_ms summary",
            "# HELP smartcs_tool_call_total Tool calls executed by the governed runtime.",
            "# TYPE smartcs_tool_call_total counter",
            "# HELP smartcs_eval_run_total Eval runs executed by the API or CI.",
            "# TYPE smartcs_eval_run_total counter",
        ]
        with self._lock:
            counters = dict(self._counters)
            histograms = {key: list(values) for key, values in self._histograms.items()}
        for (name, labels), value in sorted(counters.items()):
            lines.append(f"{name}{_labels(labels)} {value}")
        for (name, labels), values in sorted(histograms.items()):
            if not values:
                continue
            count = len(values)
            total = sum(values)
            sorted_values = sorted(values)
            p95 = sorted_values[min(count - 1, int(count * 0.95))]
            label_text = _labels(labels)
            lines.append(f"{name}_count{label_text} {count}")
            lines.append(f"{name}_sum{label_text} {total}")
            lines.append(f"{name}_p95{label_text} {p95}")
        return "\n".join(lines) + "\n"


def _labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    encoded = ",".join(f'{key}="{value}"' for key, value in labels)
    return "{" + encoded + "}"


metrics_registry = MetricsRegistry()

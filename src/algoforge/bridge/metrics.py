"""Prometheus metrics for trading system observability.

Exposes key metrics for Grafana dashboards:
- Signal processing latency
- Order fill latency
- Event queue depth
- Active positions count
- Total P&L
"""

import time
from dataclasses import dataclass, field


@dataclass
class MetricPoint:
    """A single metric observation."""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


class TradingMetrics:
    """Collects and exposes trading system metrics.

    In production with prometheus_client installed, these would be
    real Prometheus Histogram/Gauge/Counter objects. This implementation
    stores metrics in-memory for testing and provides a /metrics compatible output.
    """

    def __init__(self) -> None:
        self._histograms: dict[str, list[float]] = {
            "signal_latency_ms": [],
            "order_fill_latency_ms": [],
        }
        self._gauges: dict[str, float] = {
            "event_queue_depth": 0,
            "active_positions": 0,
            "total_pnl": 0.0,
            "capital_allocation_pct": 0.0,
        }
        self._counters: dict[str, int] = {
            "orders_submitted_total": 0,
            "orders_filled_total": 0,
            "orders_rejected_total": 0,
            "signals_generated_total": 0,
        }

    def observe_latency(self, metric_name: str, value_ms: float) -> None:
        """Record a latency observation.

        Args:
            metric_name: 'signal_latency_ms' or 'order_fill_latency_ms'.
            value_ms: Latency in milliseconds.
        """
        if metric_name in self._histograms:
            self._histograms[metric_name].append(value_ms)
            # Keep last 1000 observations
            if len(self._histograms[metric_name]) > 1000:
                self._histograms[metric_name] = self._histograms[metric_name][-1000:]

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: Metric name (e.g., 'active_positions').
            value: Current value.
        """
        self._gauges[name] = value

    def increment_counter(self, name: str, amount: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: Counter name (e.g., 'orders_filled_total').
            amount: Amount to increment.
        """
        if name in self._counters:
            self._counters[name] += amount

    def get_metrics_text(self) -> str:
        """Generate Prometheus-compatible metrics text.

        Returns:
            String in Prometheus exposition format.
        """
        lines = []
        lines.append("# HELP algoforge Trading system metrics")
        lines.append("")

        # Gauges
        for name, value in self._gauges.items():
            lines.append(f"# TYPE algoforge_{name} gauge")
            lines.append(f"algoforge_{name} {value}")

        # Counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE algoforge_{name} counter")
            lines.append(f"algoforge_{name} {value}")

        # Histogram summaries
        for name, values in self._histograms.items():
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                lines.append(f"# TYPE algoforge_{name} summary")
                lines.append(f'algoforge_{name}{{quantile="0.5"}} {sorted_vals[n // 2]:.2f}')
                lines.append(f'algoforge_{name}{{quantile="0.95"}} {sorted_vals[int(n * 0.95)]:.2f}')
                lines.append(f'algoforge_{name}{{quantile="0.99"}} {sorted_vals[int(n * 0.99)]:.2f}')
                lines.append(f"algoforge_{name}_count {n}")

        return "\n".join(lines) + "\n"

    def get_summary(self) -> dict:
        """Get a dict summary of all metrics for dashboard consumption."""
        summary: dict = {}
        summary.update(self._gauges)
        summary.update(self._counters)

        for name, values in self._histograms.items():
            if values:
                summary[f"{name}_p50"] = sorted(values)[len(values) // 2]
                summary[f"{name}_p95"] = sorted(values)[int(len(values) * 0.95)]
            else:
                summary[f"{name}_p50"] = 0.0
                summary[f"{name}_p95"] = 0.0

        return summary

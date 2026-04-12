from __future__ import annotations

from collections import Counter


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters = Counter()

    def inc(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def render_prometheus(self, queue_depth: int, open_incidents: int) -> str:
        lines = [
            "# HELP agent_control_plane_requests_total Total application events counted by the control plane.",
            "# TYPE agent_control_plane_requests_total counter",
        ]
        for key, value in sorted(self.counters.items()):
            lines.append(f'agent_control_plane_requests_total{{event="{key}"}} {value}')
        lines.extend(
            [
                "# HELP agent_control_plane_queue_depth Replay jobs waiting to be processed.",
                "# TYPE agent_control_plane_queue_depth gauge",
                f"agent_control_plane_queue_depth {queue_depth}",
                "# HELP agent_control_plane_open_incidents Open incidents visible to the control plane.",
                "# TYPE agent_control_plane_open_incidents gauge",
                f"agent_control_plane_open_incidents {open_incidents}",
            ]
        )
        return "\n".join(lines) + "\n"

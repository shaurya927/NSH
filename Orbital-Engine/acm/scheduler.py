from __future__ import annotations

from dataclasses import dataclass

from .maneuver import apply_delta_v
from .store import get_object_by_id, pop_due_maneuvers


@dataclass(frozen=True)
class SchedulerConfig:
    tick_s: float = 10.0


def execute(current_time_s: float) -> int:
    """Execute all maneuvers whose burn time has been reached.

    Logic:
    - Loop through scheduled maneuvers
    - If burn time reached, attempt to apply delta-v and remove from queue

    Args:
        current_time_s: current simulation time in seconds.

    Returns:
        Number of maneuvers successfully executed.
    """
    now = float(current_time_s)
    executed = 0

    due = pop_due_maneuvers(now)
    for m in due:
        obj = get_object_by_id(m.object_id)
        if obj is not None and apply_delta_v(obj, m.delta_v_km_s):
            executed += 1

    return executed


class Scheduler:
    """Orchestrates periodic propagation, collision checks, and maneuver plans.

    For now, it only executes scheduled maneuvers; propagation/collision will be
    added in later steps.
    """

    def __init__(self, cfg: SchedulerConfig) -> None:
        self._cfg = cfg
        self.executed_maneuvers: int = 0

    def tick(self) -> None:
        """Run one scheduling tick at the configured cadence."""
        self.executed_maneuvers += execute(self._cfg.tick_s)


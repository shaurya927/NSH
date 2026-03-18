from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ScheduledManeuver:
    object_id: str
    epoch_s: float
    # Delta-v expressed in RTN frame (km/s).
    delta_v_rtn_km_s: np.ndarray
    # Whether this maneuver requires ground LOS at execution time.
    requires_los: bool = False


class ManeuverScheduler:
    """Time-based O(log n) maneuver scheduler using a min-heap."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, ScheduledManeuver]] = []
        self._seq: int = 0
        # Minimum separation between scheduled burns for the same object.
        self.cooldown_s: float = 600.0
        self._last_epoch_by_object: dict[str, float] = {}

    def schedule(self, maneuver: ScheduledManeuver) -> None:
        epoch = float(maneuver.epoch_s)
        last = self._last_epoch_by_object.get(maneuver.object_id)
        if last is not None and abs(epoch - last) < float(self.cooldown_s):
            raise ValueError("maneuver schedule conflict: cooldown window violated for object")

        self._seq += 1
        heapq.heappush(self._heap, (epoch, self._seq, maneuver))
        self._last_epoch_by_object[maneuver.object_id] = epoch

    def pop_due(self, now_s: float) -> list[ScheduledManeuver]:
        now = float(now_s)
        out: list[ScheduledManeuver] = []
        while self._heap and self._heap[0][0] <= now:
            _, _, m = heapq.heappop(self._heap)
            out.append(m)
        return out

    def __len__(self) -> int:
        return len(self._heap)

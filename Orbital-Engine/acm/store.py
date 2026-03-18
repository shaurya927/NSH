from __future__ import annotations

import heapq
from typing import Any

import numpy as np

from .maneuver import Maneuver
from .models import SpaceObject, SpaceObjectType


OBJECTS: dict[str, SpaceObject] = {}
SCHEDULED_MANEUVERS: list[tuple[float, int, Maneuver]] = []
_MANEUVER_SEQ = 0


def add_or_update(obj: SpaceObject) -> SpaceObject:
    """Add a new object or update an existing one.

    Uses a global dict for O(1) lookup by id.
    """
    OBJECTS[obj.id] = obj
    return obj


def get_all() -> list[SpaceObject]:
    """Return all objects (order not guaranteed)."""
    return list(OBJECTS.values())


def get_satellites() -> list[SpaceObject]:
    """Return satellite objects only."""
    # This is linear in number of objects; for typical ratios it's fine.
    # If needed later, we can maintain an additional index of satellite ids.
    return [o for o in OBJECTS.values() if o.type == SpaceObjectType.SATELLITE]


def get_object_by_id(id: str) -> SpaceObject | None:
    """Fetch an object by id in O(1) time."""
    return OBJECTS.get(id)


def schedule_maneuver(maneuver: Maneuver) -> None:
    """Push a maneuver into a min-heap ordered by burn epoch."""
    global _MANEUVER_SEQ
    _MANEUVER_SEQ += 1
    heapq.heappush(SCHEDULED_MANEUVERS, (float(maneuver.epoch_s), _MANEUVER_SEQ, maneuver))


def get_scheduled_maneuvers() -> list[Maneuver]:
    """Return scheduled maneuvers sorted by execution time."""
    ordered = sorted(SCHEDULED_MANEUVERS, key=lambda it: (it[0], it[1]))
    return [entry[2] for entry in ordered]


def pop_due_maneuvers(now_s: float) -> list[Maneuver]:
    """Pop and return all maneuvers with epoch <= now_s."""
    now = float(now_s)
    out: list[Maneuver] = []
    while SCHEDULED_MANEUVERS and SCHEDULED_MANEUVERS[0][0] <= now:
        _, _, m = heapq.heappop(SCHEDULED_MANEUVERS)
        out.append(m)
    return out


def export_state_vectors() -> tuple[list[SpaceObject], np.ndarray, np.ndarray]:
    """Return object references with packed r/v arrays for vectorized propagation."""
    objs = list(OBJECTS.values())
    if not objs:
        empty = np.empty((0, 3), dtype=np.float64)
        return objs, empty, empty

    r = np.stack([o.r for o in objs], axis=0).astype(np.float64, copy=False)
    v = np.stack([o.v for o in objs], axis=0).astype(np.float64, copy=False)
    return objs, r, v


def import_state_vectors(objs: list[SpaceObject], r: np.ndarray, v: np.ndarray) -> None:
    """Write vectorized propagation results back into object instances."""
    if len(objs) == 0:
        return
    if r.shape != v.shape or r.shape != (len(objs), 3):
        raise ValueError("r and v must be shape (N,3) and match objs length")

    for i, obj in enumerate(objs):
        obj.r = r[i]
        obj.v = v[i]


def clear() -> None:
    """Clear in-memory store (useful for tests/dev)."""
    OBJECTS.clear()
    SCHEDULED_MANEUVERS.clear()
    global _MANEUVER_SEQ
    _MANEUVER_SEQ = 0


def _dump_debug() -> dict[str, Any]:
    """Internal helper for debugging/inspection."""
    return {
        "objects": {k: repr(v) for k, v in OBJECTS.items()},
        "scheduled_maneuvers": [repr(m[2]) for m in SCHEDULED_MANEUVERS],
    }

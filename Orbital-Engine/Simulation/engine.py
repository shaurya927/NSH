from __future__ import annotations

import logging
from typing import Protocol

from Physics.integrator import rk4_step


LOGGER = logging.getLogger("orbital_engine.simulation")


class HasState(Protocol):
    state: object

class SimulationEngine:
    def __init__(self):
        self.objects: list[HasState] = []

    def add_object(self, obj):
        self.objects.append(obj)
        LOGGER.debug("object_added name=%s total=%d", getattr(obj, "name", "unknown"), len(self.objects))

    def step(self, dt):
        if dt <= 0:
            raise ValueError("dt must be > 0")

        # Keep this loop minimal; integration cost dominates per object.
        for obj in self.objects:
            obj.state = rk4_step(obj.state, dt)
        LOGGER.debug("step_complete dt=%s object_count=%d", dt, len(self.objects))
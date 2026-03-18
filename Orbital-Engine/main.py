import logging
from dataclasses import dataclass

from Physics.vector import Vec3
from Physics.state import State
from Simulation.engine import SimulationEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("orbital_engine.demo")


@dataclass(slots=True)
class SpaceObject:
    name: str
    state: State

# Example: Circular orbit (LEO)
r0 = Vec3(7000, 0, 0)      # km
v0 = Vec3(0, 7.5, 0)       # km/s

sat = SpaceObject("SAT-1", State(r0, v0))

engine = SimulationEngine()
engine.add_object(sat)

# simulate
dt = 10  # seconds
steps = 1000
for i in range(steps):
    engine.step(dt)

    pos = sat.state.r
    # Throttle output to keep simulation I/O from dominating runtime.
    if i % 20 == 0 or i == steps - 1:
        LOGGER.info("t=%ss x=%.2f y=%.2f z=%.2f", i * dt, pos.x, pos.y, pos.z)
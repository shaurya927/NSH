from dataclasses import dataclass

from Physics.vector import Vec3


@dataclass(slots=True)
class State:
    """Cartesian state in ECI coordinates."""

    r: Vec3  # position (km)
    v: Vec3  # velocity (km/s)
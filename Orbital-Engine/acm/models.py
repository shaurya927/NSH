from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator


Vector3 = Annotated[list[float], Field(min_length=3, max_length=3)]


class SpaceObjectType(str, Enum):
    SATELLITE = "SATELLITE"
    DEBRIS = "DEBRIS"


@dataclass(slots=True)
class SpaceObject:
    """In-memory domain model for a simulated object.

    Fields:
    - id: unique string identifier
    - type: SATELLITE or DEBRIS
    - r: position vector (km), shape (3,)
    - v: velocity vector (km/s), shape (3,)
    - mass: kg (default 550)
    - fuel: kg, satellites only (default 50); debris always has None
    """

    id: str
    type: SpaceObjectType
    r: np.ndarray
    v: np.ndarray
    mass: float = 550.0
    fuel: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("SpaceObject.id must be a non-empty string")

        if isinstance(self.type, str):
            self.type = SpaceObjectType(self.type)  # type: ignore[assignment]

        self.r = np.asarray(self.r, dtype=np.float64)
        self.v = np.asarray(self.v, dtype=np.float64)
        if self.r.shape != (3,) or self.v.shape != (3,):
            raise ValueError("SpaceObject.r and SpaceObject.v must be shape (3,)")

        self.mass = float(self.mass)
        if self.mass <= 0.0:
            raise ValueError("SpaceObject.mass must be > 0")

        if self.type == SpaceObjectType.SATELLITE:
            if self.fuel is None:
                self.fuel = 50.0
            self.fuel = float(self.fuel)
            if self.fuel < 0.0:
                raise ValueError("SpaceObject.fuel must be >= 0 for satellites")
        else:
            # Debris has no fuel by definition.
            self.fuel = None

    def __repr__(self) -> str:
        r = np.array2string(self.r, precision=3, separator=",", suppress_small=False)
        v = np.array2string(self.v, precision=3, separator=",", suppress_small=False)
        fuel = "None" if self.fuel is None else f"{self.fuel:.3f}"
        return (
            "SpaceObject("
            f"id={self.id!r}, type={self.type.value}, "
            f"r_km={r}, v_km_s={v}, mass_kg={self.mass:.3f}, fuel_kg={fuel}"
            ")"
        )


class SpaceObjectUpsert(BaseModel):
    """API schema for creating/updating a space object."""

    id: str = Field(min_length=1, max_length=128)
    type: Literal["SATELLITE", "DEBRIS"] = "SATELLITE"
    r_km: Vector3
    v_km_s: Vector3
    mass_kg: float = Field(default=550.0, gt=0.0)
    fuel_kg: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_fuel_by_type(self) -> "SpaceObjectUpsert":
        if self.type == "DEBRIS":
            self.fuel_kg = None
        elif self.fuel_kg is None:
            self.fuel_kg = 50.0
        return self

    def to_domain(self) -> SpaceObject:
        return SpaceObject(
            id=self.id,
            type=SpaceObjectType(self.type),
            r=np.asarray(self.r_km, dtype=np.float64),
            v=np.asarray(self.v_km_s, dtype=np.float64),
            mass=float(self.mass_kg),
            fuel=None if self.type == "DEBRIS" else float(self.fuel_kg or 0.0),
        )


class SpaceObjectOut(BaseModel):
    id: str
    type: Literal["SATELLITE", "DEBRIS"]
    r_km: Vector3
    v_km_s: Vector3
    mass_kg: float
    fuel_kg: float | None

    @staticmethod
    def from_domain(obj: SpaceObject) -> "SpaceObjectOut":
        return SpaceObjectOut(
            id=obj.id,
            type=obj.type.value,
            r_km=[float(x) for x in obj.r.tolist()],
            v_km_s=[float(x) for x in obj.v.tolist()],
            mass_kg=float(obj.mass),
            fuel_kg=None if obj.fuel is None else float(obj.fuel),
        )


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["acm"] = "acm"


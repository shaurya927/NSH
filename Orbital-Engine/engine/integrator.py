from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .physics import acceleration_many


@dataclass(slots=True)
class RK4Workspace:
    """Reusable arrays to reduce per-step allocations."""

    capacity: int = 0
    k1_v: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    k2_v: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    k3_v: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    k4_v: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    r2: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    v2: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    r3: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    v3: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    r4: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    v4: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    out_r: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))
    out_v: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float64))

    def ensure_capacity(self, n: int) -> None:
        if n <= self.capacity:
            return
        self.capacity = max(1, int(n))
        shape = (self.capacity, 3)
        self.k1_v = np.empty(shape, dtype=np.float64)
        self.k2_v = np.empty(shape, dtype=np.float64)
        self.k3_v = np.empty(shape, dtype=np.float64)
        self.k4_v = np.empty(shape, dtype=np.float64)
        self.r2 = np.empty(shape, dtype=np.float64)
        self.v2 = np.empty(shape, dtype=np.float64)
        self.r3 = np.empty(shape, dtype=np.float64)
        self.v3 = np.empty(shape, dtype=np.float64)
        self.r4 = np.empty(shape, dtype=np.float64)
        self.v4 = np.empty(shape, dtype=np.float64)
        self.out_r = np.empty(shape, dtype=np.float64)
        self.out_v = np.empty(shape, dtype=np.float64)



def rk4_step_many(r_km: np.ndarray, v_km_s: np.ndarray, dt_s: float, workspace: RK4Workspace | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized RK4 integrator for coupled (r, v) state."""
    r0 = np.asarray(r_km, dtype=np.float64)
    v0 = np.asarray(v_km_s, dtype=np.float64)
    if r0.ndim != 2 or v0.ndim != 2 or r0.shape != v0.shape or r0.shape[1] != 3:
        raise ValueError("r_km and v_km_s must both be shape (N,3)")

    dt = float(dt_s)
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt_s must be a finite positive float")

    n = int(r0.shape[0])
    if n == 0:
        return r0.copy(), v0.copy()

    ws = workspace or RK4Workspace()
    ws.ensure_capacity(n)

    r = r0
    v = v0
    r2 = ws.r2[:n]
    v2 = ws.v2[:n]
    r3 = ws.r3[:n]
    v3 = ws.v3[:n]
    r4 = ws.r4[:n]
    v4 = ws.v4[:n]
    k1_v = ws.k1_v[:n]
    k2_v = ws.k2_v[:n]
    k3_v = ws.k3_v[:n]
    k4_v = ws.k4_v[:n]
    out_r = ws.out_r[:n]
    out_v = ws.out_v[:n]

    half = 0.5 * dt

    acceleration_many(r, out=k1_v)

    np.multiply(v, half, out=r2)
    np.add(r, r2, out=r2)
    np.multiply(k1_v, half, out=v2)
    np.add(v, v2, out=v2)
    acceleration_many(r2, out=k2_v)

    np.multiply(v2, half, out=r3)
    np.add(r, r3, out=r3)
    np.multiply(k2_v, half, out=v3)
    np.add(v, v3, out=v3)
    acceleration_many(r3, out=k3_v)

    np.multiply(v3, dt, out=r4)
    np.add(r, r4, out=r4)
    np.multiply(k3_v, dt, out=v4)
    np.add(v, v4, out=v4)
    acceleration_many(r4, out=k4_v)

    w = dt / 6.0

    # out_r = r + w * (v + 2*v2 + 2*v3 + v4)
    np.multiply(v2, 2.0, out=out_r)
    out_r += v
    out_r += v3 * 2.0
    out_r += v4
    out_r *= w
    out_r += r

    # out_v = v + w * (k1 + 2*k2 + 2*k3 + k4)
    np.multiply(k2_v, 2.0, out=out_v)
    out_v += k1_v
    out_v += k3_v * 2.0
    out_v += k4_v
    out_v *= w
    out_v += v

    return out_r, out_v

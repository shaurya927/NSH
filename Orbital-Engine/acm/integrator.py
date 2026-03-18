from __future__ import annotations

import numpy as np

from .physics import J2, MU_KM3_S2, RE_KM, acceleration


def _acceleration_many(r_km: np.ndarray) -> np.ndarray:
    """Compute acceleration for a batch of positions.

    Input shape is (N, 3), output shape is (N, 3).
    """
    r = np.asarray(r_km, dtype=np.float64)
    if r.ndim != 2 or r.shape[1] != 3:
        raise ValueError("r_km must be shape (N,3)")

    x = r[:, 0]
    y = r[:, 1]
    z = r[:, 2]

    r2 = x * x + y * y + z * z
    r1 = np.sqrt(r2)

    inv_r2 = 1.0 / r2
    inv_r3 = inv_r2 / r1

    ax = -MU_KM3_S2 * x * inv_r3
    ay = -MU_KM3_S2 * y * inv_r3
    az = -MU_KM3_S2 * z * inv_r3

    z2 = z * z
    term = 5.0 * z2 * inv_r2
    inv_r5 = inv_r3 * inv_r2
    f = 1.5 * J2 * MU_KM3_S2 * (RE_KM * RE_KM) * inv_r5

    ax = ax + f * x * (term - 1.0)
    ay = ay + f * y * (term - 1.0)
    az = az + f * z * (term - 3.0)

    return np.column_stack((ax, ay, az)).astype(np.float64, copy=False)

def rk4(r_km: np.ndarray, v_km_s: np.ndarray, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Integrate one RK4 step for the coupled state (r, v).

    Dynamics:
        dr/dt = v
        dv/dt = a(r)

    Args:
        r_km: position (km), shape (3,)
        v_km_s: velocity (km/s), shape (3,)
        dt_s: step size (s)

    Returns:
        (r_next_km, v_next_km_s) as float64 arrays, both shape (3,).
    """
    r0 = np.asarray(r_km, dtype=np.float64)
    v0 = np.asarray(v_km_s, dtype=np.float64)
    if r0.shape != (3,) or v0.shape != (3,):
        raise ValueError("r_km and v_km_s must be shape (3,)")

    dt = float(dt_s)
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt_s must be a finite positive float")

    half = 0.5 * dt

    # k1
    a1 = acceleration(r0)
    k1_r = v0
    k1_v = a1

    # k2
    r2 = r0 + half * k1_r
    v2 = v0 + half * k1_v
    a2 = acceleration(r2)
    k2_r = v2
    k2_v = a2

    # k3
    r3 = r0 + half * k2_r
    v3 = v0 + half * k2_v
    a3 = acceleration(r3)
    k3_r = v3
    k3_v = a3

    # k4
    r4 = r0 + dt * k3_r
    v4 = v0 + dt * k3_v
    a4 = acceleration(r4)
    k4_r = v4
    k4_v = a4

    w = dt / 6.0
    r_next = r0 + w * (k1_r + 2.0 * k2_r + 2.0 * k3_r + k4_r)
    v_next = v0 + w * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)
    return r_next, v_next


def rk4_many(r_km: np.ndarray, v_km_s: np.ndarray, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized RK4 propagation for many objects.

    Args:
        r_km: positions (N,3)
        v_km_s: velocities (N,3)
        dt_s: step size in seconds

    Returns:
        (r_next, v_next) with shapes (N,3)
    """
    r0 = np.asarray(r_km, dtype=np.float64)
    v0 = np.asarray(v_km_s, dtype=np.float64)

    if r0.ndim != 2 or v0.ndim != 2 or r0.shape != v0.shape or r0.shape[1] != 3:
        raise ValueError("r_km and v_km_s must both be shape (N,3)")

    dt = float(dt_s)
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt_s must be a finite positive float")

    half = 0.5 * dt

    a1 = _acceleration_many(r0)
    k1_r = v0
    k1_v = a1

    r2 = r0 + half * k1_r
    v2 = v0 + half * k1_v
    a2 = _acceleration_many(r2)
    k2_r = v2
    k2_v = a2

    r3 = r0 + half * k2_r
    v3 = v0 + half * k2_v
    a3 = _acceleration_many(r3)
    k3_r = v3
    k3_v = a3

    r4 = r0 + dt * k3_r
    v4 = v0 + dt * k3_v
    a4 = _acceleration_many(r4)
    k4_r = v4
    k4_v = a4

    w = dt / 6.0
    r_next = r0 + w * (k1_r + 2.0 * k2_r + 2.0 * k3_r + k4_r)
    v_next = v0 + w * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)
    return r_next, v_next


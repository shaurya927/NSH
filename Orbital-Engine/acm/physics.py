from __future__ import annotations

import numpy as np

# Constants (km, s) for Earth gravity + J2 perturbation.
MU_KM3_S2: float = 398600.4418
RE_KM: float = 6378.137
J2: float = 1.08263e-3


def acceleration(r_km: np.ndarray) -> np.ndarray:
    """Compute total acceleration (km/s^2) from Earth gravity + J2.

    Args:
        r_km: position vector (km), shape (3,)

    Returns:
        a_km_s2: acceleration vector (km/s^2), shape (3,)

    Notes:
        Designed to be fast:
        - caches r^2, 1/r^3, 1/r^5
        - avoids repeated norms/divisions
    """
    r = np.asarray(r_km, dtype=np.float64)
    if r.shape != (3,):
        raise ValueError("r_km must be shape (3,)")

    x, y, z = float(r[0]), float(r[1]), float(r[2])
    r2 = x * x + y * y + z * z
    r1 = np.sqrt(r2)

    inv_r2 = 1.0 / r2
    inv_r3 = inv_r2 / r1

    # Two-body gravity: a = -mu * r / r^3
    ax = -MU_KM3_S2 * x * inv_r3
    ay = -MU_KM3_S2 * y * inv_r3
    az = -MU_KM3_S2 * z * inv_r3

    # J2 perturbation
    # a_J2 = (3/2) J2 mu Re^2 / r^5 * [ x*(5*z^2/r^2 - 1),
    #                                   y*(5*z^2/r^2 - 1),
    #                                   z*(5*z^2/r^2 - 3) ]
    z2 = z * z
    term = 5.0 * z2 * inv_r2
    inv_r5 = inv_r3 * inv_r2  # 1/r^5 = (1/r^3)*(1/r^2)
    f = 1.5 * J2 * MU_KM3_S2 * (RE_KM * RE_KM) * inv_r5

    ax += f * x * (term - 1.0)
    ay += f * y * (term - 1.0)
    az += f * z * (term - 3.0)

    return np.array([ax, ay, az], dtype=np.float64)


def eom_eci_cartesian(t_s: float, x: np.ndarray) -> np.ndarray:
    """Equations of motion for a single object in Cartesian coordinates.

    State vector x is shape (6,) float64: [rx,ry,rz,vx,vy,vz] in km and km/s.
    """
    r = x[:3]
    v = x[3:]
    a = acceleration(r)
    return np.concatenate((v, a), dtype=np.float64)


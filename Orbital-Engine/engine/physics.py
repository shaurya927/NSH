from __future__ import annotations

import numpy as np

# Earth constants in km/s units.
MU_KM3_S2: float = 398600.4418
RE_KM: float = 6378.137
J2: float = 1.08263e-3



def acceleration_many(r_km: np.ndarray, out: np.ndarray | None = None) -> np.ndarray:
    """Compute two-body + J2 acceleration for N objects.

    Args:
        r_km: positions, shape (N, 3), units km.

    Returns:
        accelerations, shape (N, 3), units km/s^2.
    """
    r = np.asarray(r_km, dtype=np.float64)
    if r.ndim != 2 or r.shape[1] != 3:
        raise ValueError("r_km must be shape (N,3)")

    n = int(r.shape[0])
    if out is None:
        a = np.empty((n, 3), dtype=np.float64)
    else:
        if out.shape != (n, 3):
            raise ValueError("out must be shape (N,3)")
        a = out

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
    j2_factor = 1.5 * J2 * MU_KM3_S2 * (RE_KM * RE_KM) * inv_r5

    ax += j2_factor * x * (term - 1.0)
    ay += j2_factor * y * (term - 1.0)
    az += j2_factor * z * (term - 3.0)

    a[:, 0] = ax
    a[:, 1] = ay
    a[:, 2] = az
    return a

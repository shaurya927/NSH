"""
Scalar acceleration and equations-of-motion for the ACM module.

Perturbations included:
  1. Two-body (Keplerian) gravity
  2. J2 oblateness
  3. J4, J6 higher-order zonal harmonics
  4. Exponential atmospheric drag
  5. Solar Radiation Pressure (SRP)

All units: positions in km, velocities in km/s, accelerations in km/s^2.
"""

from __future__ import annotations

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Constants (km, s)
# ──────────────────────────────────────────────────────────────────────────────
MU_KM3_S2: float = 398600.4418
RE_KM: float = 6378.137
J2: float = 1.08263e-3
J4: float = -1.61098e-6
J6: float = 5.40e-7

# Atmospheric drag
RHO0_KG_M3: float = 2.803e-12
H0_KM: float = 400.0
SCALE_HEIGHT_KM: float = 58.515
CD: float = 2.2
SAT_AREA_M2: float = 10.0
OMEGA_EARTH: float = 7.2921159e-5

# SRP
P_SRP_N_M2: float = 4.56e-6
CR: float = 1.2
SAT_SRP_AREA_M2: float = 10.0

DEFAULT_MASS_KG: float = 550.0


def acceleration(
    r_km: np.ndarray,
    v_km_s: np.ndarray | None = None,
    mass_kg: float = DEFAULT_MASS_KG,
) -> np.ndarray:
    """Compute total acceleration (km/s^2) for a single object.

    Args:
        r_km: position vector (km), shape (3,)
        v_km_s: velocity vector (km/s), shape (3,). If provided, drag is included.
        mass_kg: spacecraft mass in kg. Used for drag and SRP.

    Returns:
        a_km_s2: acceleration vector (km/s^2), shape (3,)
    """
    r = np.asarray(r_km, dtype=np.float64)
    if r.shape != (3,):
        raise ValueError("r_km must be shape (3,)")

    x, y, z = float(r[0]), float(r[1]), float(r[2])
    r2 = x * x + y * y + z * z
    r1 = np.sqrt(r2)

    inv_r2 = 1.0 / r2
    inv_r3 = inv_r2 / r1

    # ── Two-body gravity ─────────────────────────────────────────────────
    ax = -MU_KM3_S2 * x * inv_r3
    ay = -MU_KM3_S2 * y * inv_r3
    az = -MU_KM3_S2 * z * inv_r3

    # ── J2 ───────────────────────────────────────────────────────────────
    z2 = z * z
    term = 5.0 * z2 * inv_r2
    inv_r5 = inv_r3 * inv_r2
    f = 1.5 * J2 * MU_KM3_S2 * (RE_KM * RE_KM) * inv_r5

    ax += f * x * (term - 1.0)
    ay += f * y * (term - 1.0)
    az += f * z * (term - 3.0)

    # ── J4 ───────────────────────────────────────────────────────────────
    inv_r7 = inv_r5 * inv_r2
    z4 = z2 * z2
    f4 = -0.625 * J4 * MU_KM3_S2 * (RE_KM ** 4) * inv_r7
    term_xy = 3.0 - 42.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 ** 2)
    term_z4 = 15.0 - 70.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 ** 2)

    ax += f4 * x * term_xy
    ay += f4 * y * term_xy
    az += f4 * z * term_z4

    # ── J6 ───────────────────────────────────────────────────────────────
    inv_r9 = inv_r7 * inv_r2
    z6 = z4 * z2
    f6 = J6 * MU_KM3_S2 * (RE_KM ** 6) * inv_r9 / 16.0
    t6_xy = -(35.0 * z6 * inv_r2 ** 3 - 945.0 * z4 * inv_r2 ** 2
              + 3150.0 * z2 * inv_r2 - 1575.0)
    t6_z = -(693.0 * z6 * inv_r2 ** 3 - 1890.0 * z4 * inv_r2 ** 2
             + 4725.0 * z2 * inv_r2 - 3150.0)

    ax += f6 * x * t6_xy
    ay += f6 * y * t6_xy
    az += f6 * z * t6_z

    # ── Solar Radiation Pressure ─────────────────────────────────────────
    in_shadow = (x < 0.0) and (np.sqrt(y * y + z * z) < RE_KM)
    if not in_shadow:
        srp_acc = P_SRP_N_M2 * CR * SAT_SRP_AREA_M2 / mass_kg / 1000.0
        ax -= srp_acc

    # ── Atmospheric Drag ─────────────────────────────────────────────────
    if v_km_s is not None:
        v = np.asarray(v_km_s, dtype=np.float64)
        altitude_km = r1 - RE_KM

        if 0.0 <= altitude_km <= 1000.0:
            rho = RHO0_KG_M3 * np.exp(-(altitude_km - H0_KM) / SCALE_HEIGHT_KM)

            vrel_x = float(v[0]) + OMEGA_EARTH * y
            vrel_y = float(v[1]) - OMEGA_EARTH * x
            vrel_z = float(v[2])

            vrel_mag = np.sqrt(vrel_x ** 2 + vrel_y ** 2 + vrel_z ** 2)
            if vrel_mag > 1e-12:
                vrel_m_s = vrel_mag * 1000.0
                drag_acc = 0.5 * rho * CD * SAT_AREA_M2 * (vrel_m_s ** 2) / mass_kg / 1000.0

                ax -= drag_acc * (vrel_x / vrel_mag)
                ay -= drag_acc * (vrel_y / vrel_mag)
                az -= drag_acc * (vrel_z / vrel_mag)

    return np.array([ax, ay, az], dtype=np.float64)


def eom_eci_cartesian(t_s: float, x: np.ndarray) -> np.ndarray:
    """Equations of motion for a single object in Cartesian coordinates.

    State vector x is shape (6,) float64: [rx,ry,rz,vx,vy,vz] in km and km/s.
    """
    r = x[:3]
    v = x[3:]
    a = acceleration(r, v_km_s=v)
    return np.concatenate((v, a), dtype=np.float64)

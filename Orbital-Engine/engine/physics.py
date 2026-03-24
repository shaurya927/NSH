"""
Vectorized acceleration models for the ACM simulation engine.

Perturbations included (all computed in vectorized NumPy for N objects):
  1. Two-body (Keplerian) gravity
  2. J2 oblateness
  3. J4 and J6 higher-order zonal harmonics
  4. Exponential atmospheric drag
  5. Solar Radiation Pressure (SRP) with cylindrical shadow

All units: positions in km, velocities in km/s, accelerations in km/s^2.
"""

from __future__ import annotations

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
MU_KM3_S2: float = 398600.4418
RE_KM: float = 6378.137
J2: float = 1.08263e-3
J4: float = -1.61098e-6
J6: float = 5.40e-7

# Atmospheric drag (exponential model at ~400 km reference altitude)
RHO0_KG_M3: float = 2.803e-12      # kg/m^3
H0_KM: float = 400.0               # km
SCALE_HEIGHT_KM: float = 58.515    # km
CD: float = 2.2                     # drag coefficient
SAT_AREA_M2: float = 10.0          # m^2 cross-section
OMEGA_EARTH: float = 7.2921159e-5  # rad/s Earth rotation rate

# Solar Radiation Pressure
P_SRP_N_M2: float = 4.56e-6        # N/m^2 at 1 AU
CR: float = 1.2                     # reflectivity coefficient
SAT_SRP_AREA_M2: float = 10.0      # m^2 effective area

# Default mass (used when per-object mass is not provided)
DEFAULT_MASS_KG: float = 550.0


def acceleration_many(
    r_km: np.ndarray,
    out: np.ndarray | None = None,
    v_km_s: np.ndarray | None = None,
    mass_kg: np.ndarray | None = None,
) -> np.ndarray:
    """Compute total acceleration for N objects with all perturbation models.

    Args:
        r_km: positions, shape (N, 3), units km.
        out: optional pre-allocated output array, shape (N, 3).
        v_km_s: velocities, shape (N, 3), units km/s.
                 If provided, atmospheric drag is included.
        mass_kg: per-object mass, shape (N,), units kg.
                  If None, DEFAULT_MASS_KG is used for drag/SRP.

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

    # ── Two-body gravity ─────────────────────────────────────────────────
    ax = -MU_KM3_S2 * x * inv_r3
    ay = -MU_KM3_S2 * y * inv_r3
    az = -MU_KM3_S2 * z * inv_r3

    # ── J2 perturbation ──────────────────────────────────────────────────
    z2 = z * z
    term_j2 = 5.0 * z2 * inv_r2
    inv_r5 = inv_r3 * inv_r2
    j2_factor = 1.5 * J2 * MU_KM3_S2 * (RE_KM * RE_KM) * inv_r5

    ax += j2_factor * x * (term_j2 - 1.0)
    ay += j2_factor * y * (term_j2 - 1.0)
    az += j2_factor * z * (term_j2 - 3.0)

    # ── J4 perturbation ──────────────────────────────────────────────────
    inv_r7 = inv_r5 * inv_r2
    z4 = z2 * z2
    j4_factor = -0.625 * J4 * MU_KM3_S2 * (RE_KM ** 4) * inv_r7
    term_j4_xy = 3.0 - 42.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 * inv_r2)
    term_j4_z = 15.0 - 70.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 * inv_r2)

    ax += j4_factor * x * term_j4_xy
    ay += j4_factor * y * term_j4_xy
    az += j4_factor * z * term_j4_z

    # ── J6 perturbation ──────────────────────────────────────────────────
    inv_r9 = inv_r7 * inv_r2
    z6 = z4 * z2
    j6_factor = J6 * MU_KM3_S2 * (RE_KM ** 6) * inv_r9 / 16.0

    p1_xy = 35.0 * z6 * (inv_r2 ** 3)
    p2_xy = -945.0 * z4 * (inv_r2 * inv_r2)
    p3_xy = 3150.0 * z2 * inv_r2
    p4_xy = -1575.0
    term_j6_xy = -(p1_xy + p2_xy + p3_xy + p4_xy)

    p1_z = 693.0 * z6 * (inv_r2 ** 3)
    p2_z = -1890.0 * z4 * (inv_r2 * inv_r2)
    p3_z = 4725.0 * z2 * inv_r2
    p4_z = -3150.0
    term_j6_z = -(p1_z + p2_z + p3_z + p4_z)

    ax += j6_factor * x * term_j6_xy
    ay += j6_factor * y * term_j6_xy
    az += j6_factor * z * term_j6_z

    # ── Solar Radiation Pressure ─────────────────────────────────────────
    # Simplified: Sun at +X infinity, push is in -X.
    # Cylindrical shadow model: if x < 0 and sqrt(y^2+z^2) < RE, in shadow.
    if mass_kg is not None:
        m = np.asarray(mass_kg, dtype=np.float64)
    else:
        m = np.full(n, DEFAULT_MASS_KG, dtype=np.float64)

    srp_acc = P_SRP_N_M2 * CR * SAT_SRP_AREA_M2 / m / 1000.0  # km/s^2

    in_shadow = (x < 0.0) & (np.sqrt(y * y + z * z) < RE_KM)
    srp_acc = np.where(in_shadow, 0.0, srp_acc)

    ax -= srp_acc  # push away from Sun (-X direction)
    # ay, az contributions are zero in this simplified model

    # ── Atmospheric Drag ─────────────────────────────────────────────────
    if v_km_s is not None:
        v = np.asarray(v_km_s, dtype=np.float64)
        altitude_km = r1 - RE_KM

        # Only apply drag where altitude is in [0, 1000] km range.
        drag_mask = (altitude_km >= 0.0) & (altitude_km <= 1000.0)

        if np.any(drag_mask):
            # Exponential density model.
            rho = np.where(
                drag_mask,
                RHO0_KG_M3 * np.exp(-(altitude_km - H0_KM) / SCALE_HEIGHT_KM),
                0.0,
            )

            # Velocity relative to co-rotating atmosphere.
            # v_atm = omega x r = [-omega*y, omega*x, 0]
            vrel_x = v[:, 0] + OMEGA_EARTH * y  # v_x - (-omega*y)
            vrel_y = v[:, 1] - OMEGA_EARTH * x  # v_y - omega*x
            vrel_z = v[:, 2]

            vrel_mag_km_s = np.sqrt(vrel_x ** 2 + vrel_y ** 2 + vrel_z ** 2)
            vrel_mag_m_s = vrel_mag_km_s * 1000.0

            # Avoid division by zero.
            safe_vrel = np.where(vrel_mag_km_s > 1e-12, vrel_mag_km_s, 1.0)

            # Drag acceleration magnitude (km/s^2).
            # a_drag = -0.5 * rho * Cd * A * v_rel^2 / mass  (in m/s^2)
            # then convert to km/s^2.
            drag_acc = 0.5 * rho * CD * SAT_AREA_M2 * (vrel_mag_m_s ** 2) / m / 1000.0

            # Apply drag opposite to relative velocity direction.
            ax -= drag_acc * (vrel_x / safe_vrel)
            ay -= drag_acc * (vrel_y / safe_vrel)
            az -= drag_acc * (vrel_z / safe_vrel)

    a[:, 0] = ax
    a[:, 1] = ay
    a[:, 2] = az
    return a

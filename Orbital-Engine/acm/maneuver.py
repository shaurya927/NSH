from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import SpaceObject, SpaceObjectType


Isp_S: float = 300.0
G0_M_S2: float = 9.80665
MAX_DV_KM_S: float = 0.015


def _unit(vec: np.ndarray, name: str) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float64)
    if v.shape != (3,):
        raise ValueError(f"{name} must be shape (3,)")
    n = float(np.linalg.norm(v))
    if not np.isfinite(n) or n <= 0.0:
        raise ValueError(f"{name} must have finite non-zero norm")
    return v / n


def rtn_to_eci(dv_rtn: np.ndarray, r_km: np.ndarray, v_km_s: np.ndarray) -> np.ndarray:
    """Convert a delta-v vector from RTN frame to ECI.

    RTN definition (per requirement):
    - R = normalized position
    - T = normalized velocity
    - N = R × T

    Implementation detail:
    - N is normalized.
    - To ensure an orthonormal basis even when v is not perfectly perpendicular
      to r, we recompute T as (N × R) after forming N. This keeps R fixed and
      makes (R, T, N) orthonormal while keeping T in the orbital plane.

    Args:
        dv_rtn: delta-v in RTN frame (km/s), shape (3,) as [dR, dT, dN]
        r_km: position vector (km), shape (3,)
        v_km_s: velocity vector (km/s), shape (3,)

    Returns:
        dv_eci: delta-v in ECI frame (km/s), shape (3,)
    """
    dv = np.asarray(dv_rtn, dtype=np.float64)
    if dv.shape != (3,):
        raise ValueError("dv_rtn must be shape (3,)")

    R = _unit(r_km, "r_km")
    T0 = _unit(v_km_s, "v_km_s")

    N_raw = np.cross(R, T0)
    N = _unit(N_raw, "R×T")
    T = np.cross(N, R)  # already unit-length if R and N are unit and orthogonal

    # dv_eci = dR*R + dT*T + dN*N
    return dv[0] * R + dv[1] * T + dv[2] * N


@dataclass(frozen=True)
class Maneuver:
    """Impulsive maneuver in Cartesian velocity space."""

    object_id: str
    epoch_s: float
    delta_v_km_s: np.ndarray  # shape (3,)


def apply_delta_v(obj: SpaceObject, dv: np.ndarray) -> bool:
    """Apply an impulsive delta-v to an object (satellites only).

    Rules:
    - dv is in km/s and must be shape (3,)
    - max dv magnitude is 0.015 km/s
    - fuel burn follows rocket equation with Isp=300s, g0=9.80665 m/s^2

    Updates in-place:
    - velocity (km/s)
    - fuel (kg)
    - mass (kg)
    """
    if obj.type != SpaceObjectType.SATELLITE:
        return False
    if obj.fuel is None:
        return False

    dv_km_s = np.asarray(dv, dtype=np.float64)
    if dv_km_s.shape != (3,):
        raise ValueError("dv must be a NumPy vector of shape (3,)")

    dv_mag_km_s = float(np.linalg.norm(dv_km_s))
    if not np.isfinite(dv_mag_km_s):
        raise ValueError("dv magnitude must be finite")
    if dv_mag_km_s > MAX_DV_KM_S:
        return False

    # dm = m * (1 - exp(-|dv| / (Isp * g0)))
    dv_mag_m_s = dv_mag_km_s * 1000.0
    ve_m_s = Isp_S * G0_M_S2
    dm = float(obj.mass) * (1.0 - float(np.exp(-dv_mag_m_s / ve_m_s)))

    if dm < 0.0:
        return False
    if dm > float(obj.fuel) + 1e-12:
        return False

    obj.v = obj.v + dv_km_s
    obj.fuel = float(obj.fuel) - dm
    obj.mass = float(obj.mass) - dm

    # Numerical safety: clamp tiny negatives.
    if obj.fuel < 0.0:
        obj.fuel = 0.0
    if obj.mass <= 0.0:
        return False
    return True


def plan_avoidance_maneuvers(
    object_ids: list[str],
    close_pairs: np.ndarray,
) -> list[Maneuver]:
    """Plan collision avoidance maneuvers.

    Implemented in a later step; kept separate from collision detection so
    strategies (impulsive, continuous thrust, constraints) can evolve.
    """
    raise NotImplementedError("Maneuver planning not implemented yet")


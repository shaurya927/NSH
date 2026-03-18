from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Isp_S: float = 300.0
G0_M_S2: float = 9.80665
MAX_DV_KM_S: float = 0.015


@dataclass(frozen=True, slots=True)
class ManeuverConfig:
    max_dv_km_s: float = MAX_DV_KM_S
    isp_s: float = Isp_S
    g0_m_s2: float = G0_M_S2


def _normalize_rows(v: np.ndarray, eps: float = 1e-12) -> tuple[np.ndarray, np.ndarray]:
    """Normalize row vectors and return (unit, norm)."""
    arr = np.asarray(v, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("input must be shape (N,3)")

    norm = np.sqrt(np.einsum("ij,ij->i", arr, arr))
    if np.any(~np.isfinite(norm)):
        raise ValueError("non-finite vector norm encountered")

    safe = np.maximum(norm, eps)
    return arr / safe[:, None], norm


def rtn_basis_many(r_km: np.ndarray, v_km_s: np.ndarray, eps: float = 1e-12) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute RTN basis for many states.

    Definition:
        R = normalized position
        T = normalized velocity (orthonormalized via N x R)
        N = normalized cross(R, T)
    """
    r = np.asarray(r_km, dtype=np.float64)
    v = np.asarray(v_km_s, dtype=np.float64)
    if r.shape != v.shape or r.ndim != 2 or r.shape[1] != 3:
        raise ValueError("r_km and v_km_s must be shape (N,3)")

    R, r_norm = _normalize_rows(r, eps=eps)
    if np.any(r_norm <= eps):
        raise ValueError("cannot build RTN basis with near-zero position norm")

    T0, v_norm = _normalize_rows(v, eps=eps)
    if np.any(v_norm <= eps):
        raise ValueError("cannot build RTN basis with near-zero velocity norm")

    N_raw = np.cross(R, T0)
    n_norm = np.sqrt(np.einsum("ij,ij->i", N_raw, N_raw))

    # Handle near-collinearity between R and T0 with a deterministic fallback axis.
    bad = n_norm <= eps
    if np.any(bad):
        helper = np.zeros_like(R)
        helper[:, 0] = 1.0
        near_x = np.abs(R[:, 0]) > 0.9
        helper[near_x, 0] = 0.0
        helper[near_x, 1] = 1.0
        N_raw[bad] = np.cross(R[bad], helper[bad])
        n_norm = np.sqrt(np.einsum("ij,ij->i", N_raw, N_raw))

    N = N_raw / np.maximum(n_norm, eps)[:, None]
    T = np.cross(N, R)
    T, _ = _normalize_rows(T, eps=eps)
    return R, T, N


def rtn_to_eci_many(dv_rtn_km_s: np.ndarray, r_km: np.ndarray, v_km_s: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Convert delta-v vectors from RTN frame to ECI frame in batch."""
    dv = np.asarray(dv_rtn_km_s, dtype=np.float64)
    if dv.ndim != 2 or dv.shape[1] != 3:
        raise ValueError("dv_rtn_km_s must be shape (N,3)")

    R, T, N = rtn_basis_many(r_km, v_km_s, eps=eps)
    return dv[:, [0]] * R + dv[:, [1]] * T + dv[:, [2]] * N



def apply_burn_batch(
    v_km_s: np.ndarray,
    mass_kg: np.ndarray,
    fuel_kg: np.ndarray,
    sat_indices: np.ndarray,
    delta_v_km_s: np.ndarray,
    cfg: ManeuverConfig | None = None,
) -> int:
    """Apply impulsive burns to satellites in vectorized form.

    Arrays are updated in-place for valid maneuvers.
    Input delta-v is expected in ECI frame.
    """
    if cfg is None:
        cfg = ManeuverConfig()

    idx = np.asarray(sat_indices, dtype=np.int64)
    dv = np.asarray(delta_v_km_s, dtype=np.float64)
    if idx.ndim != 1:
        raise ValueError("sat_indices must be 1D")
    if dv.ndim != 2 or dv.shape[1] != 3 or dv.shape[0] != idx.shape[0]:
        raise ValueError("delta_v_km_s must be shape (M,3) matching sat_indices")
    if idx.size == 0:
        return 0

    current_v = v_km_s[idx]
    current_mass = mass_kg[idx]
    current_fuel = fuel_kg[idx]

    dv_mag_km_s = np.linalg.norm(dv, axis=1)
    finite = np.isfinite(dv_mag_km_s)
    cap = float(cfg.max_dv_km_s)
    under_cap = dv_mag_km_s <= cap + 1e-12

    # Numerically clip vectors that are microscopically above the cap.
    over = finite & (dv_mag_km_s > cap) & under_cap
    if np.any(over):
        scale = (cap / dv_mag_km_s[over])[:, None]
        dv[over] = dv[over] * scale
        dv_mag_km_s[over] = cap

    ve = float(cfg.isp_s) * float(cfg.g0_m_s2)
    dm = current_mass * (1.0 - np.exp(-(dv_mag_km_s * 1000.0) / ve))

    feasible = finite & under_cap & np.isfinite(dm) & (dm >= 0.0) & (dm <= current_fuel + 1e-12)
    if not np.any(feasible):
        return 0

    ok_idx = idx[feasible]
    ok_dv = dv[feasible]
    ok_dm = dm[feasible]

    v_km_s[ok_idx] = v_km_s[ok_idx] + ok_dv
    fuel_kg[ok_idx] = np.maximum(0.0, fuel_kg[ok_idx] - ok_dm)
    mass_kg[ok_idx] = mass_kg[ok_idx] - ok_dm
    return int(ok_idx.size)

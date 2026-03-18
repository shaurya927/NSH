from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .models import SpaceObject, SpaceObjectType
from .physics import MU_KM3_S2, RE_KM


@dataclass(frozen=True, slots=True)
class OrbitSamplingConfig:
    """Sampling ranges for 'realistic enough' stable Earth orbits.

    All angles are in radians. Distances in km.
    """

    # Keep perigee safely above atmosphere.
    min_perigee_alt_km: float = 300.0
    max_perigee_alt_km: float = 1400.0

    # Mild eccentricities for 'stable' LEO-like orbits.
    max_ecc_sat: float = 0.001
    max_ecc_debris: float = 0.02

    # Inclination range (0..pi).
    min_inc_rad: float = 0.0
    max_inc_rad: float = np.pi

    # Optional cap on apogee altitude to avoid extreme ellipses.
    max_apogee_alt_km: float = 2000.0


def _rot1(a: float) -> np.ndarray:
    ca = float(np.cos(a))
    sa = float(np.sin(a))
    return np.array([[1.0, 0.0, 0.0], [0.0, ca, -sa], [0.0, sa, ca]], dtype=np.float64)


def _rot3(a: float) -> np.ndarray:
    ca = float(np.cos(a))
    sa = float(np.sin(a))
    return np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def keplerian_to_eci(
    a_km: float,
    e: float,
    inc_rad: float,
    raan_rad: float,
    argp_rad: float,
    nu_rad: float,
    mu_km3_s2: float = MU_KM3_S2,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert Keplerian elements to ECI r,v (km, km/s)."""
    a = float(a_km)
    e = float(e)
    if not (a > 0.0 and 0.0 <= e < 1.0):
        raise ValueError("invalid (a,e)")

    p = a * (1.0 - e * e)
    cnu = float(np.cos(nu_rad))
    snu = float(np.sin(nu_rad))
    r_pf_mag = p / (1.0 + e * cnu)

    r_pf = np.array([r_pf_mag * cnu, r_pf_mag * snu, 0.0], dtype=np.float64)
    v_pf = np.array(
        [
            -np.sqrt(mu_km3_s2 / p) * snu,
            np.sqrt(mu_km3_s2 / p) * (e + cnu),
            0.0,
        ],
        dtype=np.float64,
    )

    q = _rot3(raan_rad) @ _rot1(inc_rad) @ _rot3(argp_rad)
    r_eci = q @ r_pf
    v_eci = q @ v_pf
    return r_eci, v_eci


def _sample_orbit(rng: np.random.Generator, cfg: OrbitSamplingConfig, max_e: float) -> tuple[np.ndarray, np.ndarray]:
    # Sample perigee altitude; compute rp.
    per_alt = float(rng.uniform(cfg.min_perigee_alt_km, cfg.max_perigee_alt_km))
    rp = RE_KM + per_alt

    # Sample eccentricity and ensure apogee does not exceed cap.
    e = float(rng.uniform(0.0, max_e))
    a = rp / (1.0 - e)  # rp = a(1-e)
    ra = a * (1.0 + e)
    if ra - RE_KM > cfg.max_apogee_alt_km:
        # Reduce e to satisfy apogee cap while keeping rp fixed.
        ra_cap = RE_KM + cfg.max_apogee_alt_km
        # Solve ra = a(1+e), rp = a(1-e) => a = (ra+rp)/2, e = (ra-rp)/(ra+rp)
        a = 0.5 * (ra_cap + rp)
        e = (ra_cap - rp) / (ra_cap + rp)

    inc = float(rng.uniform(cfg.min_inc_rad, cfg.max_inc_rad))
    raan = float(rng.uniform(0.0, 2.0 * np.pi))
    argp = float(rng.uniform(0.0, 2.0 * np.pi))
    nu = float(rng.uniform(0.0, 2.0 * np.pi))

    r, v = keplerian_to_eci(a, e, inc, raan, argp, nu)
    return r, v


def generate_objects(
    n_satellites: int = 50,
    n_debris: int = 10_000,
    seed: int = 7,
    cfg: OrbitSamplingConfig | None = None,
) -> list[SpaceObject]:
    """Generate a mixed population of satellites and debris with stable-ish orbits."""
    if cfg is None:
        cfg = OrbitSamplingConfig()

    rng = np.random.default_rng(int(seed))
    out: list[SpaceObject] = []

    for i in range(int(n_satellites)):
        r, v = _sample_orbit(rng, cfg, max_e=cfg.max_ecc_sat)
        out.append(
            SpaceObject(
                id=f"SAT-{i:03d}",
                type=SpaceObjectType.SATELLITE,
                r=r,
                v=v,
                mass=550.0,
                fuel=50.0,
            )
        )

    for i in range(int(n_debris)):
        r, v = _sample_orbit(rng, cfg, max_e=cfg.max_ecc_debris)
        out.append(
            SpaceObject(
                id=f"DEB-{i:05d}",
                type=SpaceObjectType.DEBRIS,
                r=r,
                v=v,
                mass=1.0,
                fuel=None,
            )
        )

    return out


def export_telemetry_json(objects: list[SpaceObject], path: str | Path) -> None:
    """Export objects to the `/api/telemetry` payload format."""
    payload = {
        "objects": [
            {
                "id": o.id,
                "type": o.type.value,
                "r_km": [float(x) for x in o.r.tolist()],
                "v_km_s": [float(x) for x in o.v.tolist()],
                "mass_kg": float(o.mass),
                "fuel_kg": None if o.fuel is None else float(o.fuel),
            }
            for o in objects
        ]
    }
    p = Path(path)
    p.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    objs = generate_objects()
    export_telemetry_json(objs, Path("telemetry_seed7.json"))
    # Quick sanity stats (velocities should be ~7-8 km/s for LEO).
    vmag = np.array([float(np.linalg.norm(o.v)) for o in objs], dtype=np.float64)
    rmag = np.array([float(np.linalg.norm(o.r)) for o in objs], dtype=np.float64)
    print(
        "generated",
        len(objs),
        "v_km_s[min/mean/max]=",
        float(vmag.min()),
        float(vmag.mean()),
        float(vmag.max()),
        "r_km[min/mean/max]=",
        float(rmag.min()),
        float(rmag.mean()),
        float(rmag.max()),
    )


from __future__ import annotations

import logging
from time import perf_counter

import numpy as np

from engine import ACMEngine
from engine.utils import EngineConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("engine.system_validation")


def _generate_test_telemetry(num_sats: int, num_debris: int) -> dict[str, object]:
    """Generate a synthetic constellation for system validation.

    - Satellites: circular-ish LEO ring with evenly spaced RAAN.
    - Debris: shell around the same altitude with small perturbations.
    """
    objects: list[dict[str, object]] = []

    radius_km = 7000.0
    v_mag_km_s = 7.5
    sat_fuel_kg = 50.0
    sat_mass_kg = 550.0

    # Satellites on a simple equatorial ring.
    for i in range(num_sats):
        theta = 2.0 * np.pi * (i / max(1, num_sats))
        r = np.array([radius_km * np.cos(theta), radius_km * np.sin(theta), 0.0], dtype=float)
        v = np.array([-v_mag_km_s * np.sin(theta), v_mag_km_s * np.cos(theta), 0.0], dtype=float)
        objects.append(
            {
                "id": f"SAT-{i:03d}",
                "type": "SATELLITE",
                "r_km": r.tolist(),
                "v_km_s": v.tolist(),
                "mass_kg": sat_mass_kg,
                "fuel_kg": sat_fuel_kg,
            }
        )

    # Debris cloud near the same shell, with mild radial and vertical spread.
    rng = np.random.default_rng(seed=12345)
    ang = rng.uniform(0.0, 2.0 * np.pi, size=num_debris)
    dr = rng.normal(0.0, 50.0, size=num_debris)  # +/- 50 km spread
    dz = rng.normal(0.0, 50.0, size=num_debris)

    r_base = radius_km + dr
    x = r_base * np.cos(ang)
    y = r_base * np.sin(ang)
    z = dz
    r_deb = np.stack([x, y, z], axis=1)

    # Velocity: tangential with small random perturbations.
    v_tan = v_mag_km_s * (r_deb[:, [1, 0]] / np.linalg.norm(r_deb[:, :2], axis=1, keepdims=True))
    vx = -v_tan[:, 0]
    vy = v_tan[:, 1]
    vz = rng.normal(0.0, 0.01, size=num_debris)
    v_deb = np.stack([vx, vy, vz], axis=1)

    for i in range(num_debris):
        objects.append(
            {
                "id": f"DEB-{i:05d}",
                "type": "DEBRIS",
                "r_km": r_deb[i].tolist(),
                "v_km_s": v_deb[i].tolist(),
                "mass_kg": 1.0,
            }
        )

    return {"objects": objects}


def run_validation() -> None:
    """Run a 24-hour system validation scenario and print summary metrics."""
    num_sats = 50
    num_debris = 10_000

    cfg = EngineConfig(
        # Use float32 state for performance.
        state_dtype="float32",
        # Keep station-keeping and auto-avoidance enabled to exercise logic.
        enable_station_keeping=True,
        enable_auto_avoidance=True,
        # Enable TCA prediction so ACA can plan from conjunctions.
        enable_tca_prediction=True,
        # Use a modest candidate radius to keep KDTree work bounded.
        conjunction_candidate_radius_km=2.0,
        max_conjunction_results=1000,
    )

    engine = ACMEngine(cfg)

    telemetry = _generate_test_telemetry(num_sats, num_debris)
    ingest_info = engine.ingest_telemetry(telemetry)
    LOGGER.info("ingested objects: %s", ingest_info)

    # Track initial total fuel across all satellites.
    initial_fuel_total = 0.0
    for i, sid in enumerate(engine._sat.ids):
        initial_fuel_total += float(engine._sat.fuel[i])

    # Run a single 24-hour step.
    sim_duration_s = 24.0 * 3600.0
    t0 = perf_counter()
    result = engine.step_simulation(sim_duration_s)
    elapsed_ms = (perf_counter() - t0) * 1000.0

    LOGGER.info("step_simulation finished in %.2f ms", elapsed_ms)

    # Collisions and avoidance.
    collisions = result.get("collisions_detected", [])
    auto_sequences = result.get("autonomous_maneuvers", [])
    collisions_avoided = len(auto_sequences)

    # Fuel usage: difference between initial and remaining satellite fuel.
    remaining_fuel_total = 0.0
    for i, sid in enumerate(engine._sat.ids):
        remaining_fuel_total += float(engine._sat.fuel[i])
    total_fuel_used = initial_fuel_total - remaining_fuel_total

    # Uptime: compute average station-keeping uptime fraction.
    sk_report = engine._build_station_keeping_report() if cfg.enable_station_keeping else []
    uptime_fracs = []
    for row in sk_report:
        up = float(row.get("uptime_s", 0.0))
        out = float(row.get("outage_s", 0.0))
        denom = up + out
        if denom > 0.0:
            uptime_fracs.append(up / denom)
    uptime_pct = (sum(uptime_fracs) / len(uptime_fracs) * 100.0) if uptime_fracs else 100.0

    print("=== System Validation Summary ===")
    print(f"Satellites: {num_sats}, Debris: {num_debris}")
    print(f"Simulation duration: {sim_duration_s/3600.0:.1f} h")
    print(f"Engine step wall-clock: {elapsed_ms:.2f} ms")
    print(f"Collisions detected: {len(collisions)}")
    print(f"Collisions avoided (autonomous sequences): {collisions_avoided}")
    print(f"Total fuel used (kg): {total_fuel_used:.3f}")
    print(f"Average uptime (station-keeping) %%: {uptime_pct:.2f}")


if __name__ == "__main__":
    run_validation()

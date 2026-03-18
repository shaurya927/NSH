from __future__ import annotations

import base64
import logging
import os
import zlib
from dataclasses import dataclass

import numpy as np


def get_logger(name: str = "engine") -> logging.Logger:
    """Return a configured package logger."""
    level_name = os.getenv("ACM_ENGINE_LOG_LEVEL", "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Configuration for ACMEngine internals."""

    integration_tick_s: float = 10.0
    initial_capacity: int = 2048
    scheduler_latency_s: float = 10.0
    collision_distance_km: float = 0.1
    collision_max_pairs: int = 5_000_000
    # Predictive conjunction assessment settings.
    collision_future_horizon_s: float = 86_400.0  # 24 hours
    # Keep disabled by default in step loop for large-scale real-time latency.
    enable_tca_prediction: bool = False
    # KDTree pre-filter radius for conjunction candidate generation.
    conjunction_candidate_radius_km: float = 5.0
    # Risk level thresholds by miss distance.
    risk_critical_km: float = 0.1
    risk_medium_km: float = 1.0
    risk_low_km: float = 5.0
    max_conjunction_results: int = 2_000

    # Autonomous collision avoidance controls.
    enable_auto_avoidance: bool = True
    auto_avoidance_safe_miss_km: float = 1.0
    auto_avoidance_max_dv_km_s: float = 0.015  # 15 m/s
    auto_avoidance_cooldown_s: float = 600.0
    auto_avoidance_min_tca_s: float = 60.0
    auto_avoidance_margin_factor: float = 1.10

    # Station-keeping controls.
    enable_station_keeping: bool = True
    # Maximum allowed distance between current position and nominal slot.
    station_keeping_radius_km: float = 10.0
    # Characteristic correction timescale used to size recovery burns.
    station_keeping_recovery_timescale_s: float = 3600.0
    # Fraction of max_dv_km_s to use for station-keeping burns.
    station_keeping_max_dv_fraction: float = 0.5

    # Communication / LOS constraints.
    enable_comm_constraints: bool = True

    max_step_ticks: int = 100_000
    debris_compression_level: int = 6
    # float32 substantially lowers memory bandwidth for large constellations.
    state_dtype: str = "float32"



def as_vec3_array(value: object, field: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != (3,):
        raise ValueError(f"{field} must be length-3")
    return arr



def compute_lat_lon_deg(positions_km: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute spherical lat/lon from Cartesian coordinates."""
    pos = np.asarray(positions_km, dtype=np.float64)
    if pos.ndim != 2 or pos.shape[1] != 3:
        raise ValueError("positions_km must be shape (N,3)")

    x = pos[:, 0]
    y = pos[:, 1]
    z = pos[:, 2]
    rho = np.sqrt(x * x + y * y + z * z)
    lat = np.degrees(np.arcsin(np.clip(z / rho, -1.0, 1.0)))
    lon = np.degrees(np.arctan2(y, x))
    return lat, lon



def compress_positions_b64(positions_km: np.ndarray, compression_level: int = 6) -> dict[str, object]:
    """Serialize Nx3 positions to compact zlib+base64 payload."""
    pos = np.asarray(positions_km, dtype=np.float32)
    if pos.ndim != 2 or pos.shape[1] != 3:
        raise ValueError("positions_km must be shape (N,3)")

    if pos.shape[0] == 0:
        return {
            "count": 0,
            "encoding": "zlib+base64",
            "dtype": "float32",
            "shape": [0, 3],
            "data": "",
        }

    raw = pos.tobytes(order="C")
    comp = zlib.compress(raw, level=int(compression_level))
    return {
        "count": int(pos.shape[0]),
        "encoding": "zlib+base64",
        "dtype": "float32",
        "shape": [int(pos.shape[0]), 3],
        "data": base64.b64encode(comp).decode("ascii"),
    }

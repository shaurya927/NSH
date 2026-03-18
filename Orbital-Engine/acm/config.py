from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Runtime configuration for ACM simulation loops.

    Values are intentionally environment-driven so large-scale runs can tune
    behavior without code changes.
    """

    integration_tick_s: float = 10.0
    max_step_ticks: int = 100_000
    collision_distance_km: float = 0.1
    collision_block_size: int = 2048
    collision_max_pairs: int = 5_000_000
    prefer_kdtree: bool = True



def load_simulation_config() -> SimulationConfig:
    """Load simulation config from environment variables."""

    def _float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        return float(raw)

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        return int(raw)

    def _bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    return SimulationConfig(
        integration_tick_s=_float("ACM_INTEGRATION_TICK_S", 10.0),
        max_step_ticks=_int("ACM_MAX_STEP_TICKS", 100_000),
        collision_distance_km=_float("ACM_COLLISION_DISTANCE_KM", 0.1),
        collision_block_size=_int("ACM_COLLISION_BLOCK_SIZE", 2048),
        collision_max_pairs=_int("ACM_COLLISION_MAX_PAIRS", 5_000_000),
        prefer_kdtree=_bool("ACM_COLLISION_PREFER_KDTREE", True),
    )



def configure_logging() -> logging.Logger:
    """Configure package logger once and return it."""

    level_name = os.getenv("ACM_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("acm")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger

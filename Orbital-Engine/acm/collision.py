from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .models import SpaceObject

try:
    from scipy.spatial import cKDTree  # type: ignore

    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    cKDTree = None  # type: ignore
    _HAS_SCIPY = False


@dataclass(frozen=True)
class CollisionConfig:
    """Broadphase collision screening configuration."""

    # Collision threshold (km). Requirement: 0.1 km.
    collision_distance_km: float = 0.1

    # Work chunking to avoid allocating an NxN distance matrix.
    block_size: int = 1024

    # Safety cap: prevents pathological output sizes.
    max_pairs: int = 5_000_000

    # Prefer SciPy KD-tree when available (recommended for 10k+ objects).
    prefer_kdtree: bool = True


class Broadphase(Protocol):
    def detect_pairs(self, positions_km: np.ndarray, threshold_km: float) -> np.ndarray: ...


class KDTreeBroadphase:
    """KD-tree broadphase using SciPy's highly optimized cKDTree."""

    def __init__(self) -> None:
        if not _HAS_SCIPY:
            raise RuntimeError(
                "SciPy is not available. Install it (e.g. `pip install scipy`) "
                "or disable KD-tree usage."
            )

    def detect_pairs(self, positions_km: np.ndarray, threshold_km: float) -> np.ndarray:
        pos = np.asarray(positions_km, dtype=np.float64)
        if pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions_km must be shape (N,3)")

        n = int(pos.shape[0])
        if n < 2:
            return np.empty((0, 2), dtype=np.int32)

        thr = float(threshold_km)
        if not np.isfinite(thr) or thr <= 0.0:
            return np.empty((0, 2), dtype=np.int32)

        tree = cKDTree(pos)  # type: ignore[misc]
        # query_pairs returns unique (i,j) with i<j, so no duplicate filtering needed.
        pairs_set = tree.query_pairs(r=thr, output_type="set")
        if not pairs_set:
            return np.empty((0, 2), dtype=np.int32)

        pairs = np.fromiter((p for ij in pairs_set for p in ij), dtype=np.int32)
        pairs = pairs.reshape(-1, 2)
        return pairs


class ChunkedNaiveBroadphase:
    """Naive O(N^2) broadphase, implemented in chunks.

    This keeps memory bounded (no NxN matrix) and is easy to replace with a KD-tree.
    """

    def __init__(self, block_size: int = 1024) -> None:
        self._block_size = int(block_size)
        if self._block_size <= 0:
            raise ValueError("block_size must be > 0")

    def detect_pairs(self, positions_km: np.ndarray, threshold_km: float) -> np.ndarray:
        pos = np.asarray(positions_km, dtype=np.float64)
        if pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions_km must be shape (N,3)")

        n = int(pos.shape[0])
        if n < 2:
            return np.empty((0, 2), dtype=np.int32)

        thr2 = float(threshold_km) ** 2
        if thr2 <= 0.0:
            return np.empty((0, 2), dtype=np.int32)

        # Precompute ||r||^2 once; then use ||a-b||^2 = ||a||^2 + ||b||^2 - 2 a·b.
        norms2 = np.einsum("ij,ij->i", pos, pos)  # shape (N,)

        pairs_i: list[np.ndarray] = []
        pairs_j: list[np.ndarray] = []

        bs = self._block_size
        for i0 in range(0, n - 1, bs):
            i1 = min(i0 + bs, n - 1)
            a = pos[i0:i1]  # (B,3)
            a2 = norms2[i0:i1]  # (B,)

            # Distances to all points; we’ll later mask out j <= i for uniqueness.
            # dist2 shape: (B, N)
            dist2 = a2[:, None] + norms2[None, :] - 2.0 * (a @ pos.T)

            # For each row k, valid columns are (i0+k+1 ... N-1)
            rows = i1 - i0
            col_idx = np.arange(n, dtype=np.int32)[None, :]
            row_global = (i0 + np.arange(rows, dtype=np.int32))[:, None]
            upper = col_idx > row_global

            hit = upper & (dist2 < thr2)
            if np.any(hit):
                ii, jj = np.nonzero(hit)
                pairs_i.append((ii + i0).astype(np.int32, copy=False))
                pairs_j.append(jj.astype(np.int32, copy=False))

        if not pairs_i:
            return np.empty((0, 2), dtype=np.int32)

        out_i = np.concatenate(pairs_i)
        out_j = np.concatenate(pairs_j)
        return np.stack((out_i, out_j), axis=1).astype(np.int32, copy=False)


def compute_tca(obj1: SpaceObject, obj2: SpaceObject) -> tuple[float, float]:
    """Compute time of closest approach (TCA) and miss distance.

    Uses constant relative velocity (linear motion) approximation:
        r_rel(t) = r0 + v0 * t
        t_ca = - (r0 · v0) / ||v0||^2

    Returns:
        (t_ca_s, d_ca_km)

    Notes:
        - If relative speed is ~0, returns (0, current distance).
        - t_ca can be negative (closest approach occurred in the past).
    """
    r0 = (obj2.r - obj1.r).astype(np.float64, copy=False)
    v0 = (obj2.v - obj1.v).astype(np.float64, copy=False)

    v2 = float(np.dot(v0, v0))
    if v2 <= 0.0 or not np.isfinite(v2):
        d0 = float(np.linalg.norm(r0))
        return 0.0, d0

    t_ca = -float(np.dot(r0, v0)) / v2
    r_ca = r0 + v0 * t_ca
    d_ca = float(np.linalg.norm(r_ca))
    return t_ca, d_ca


def detect_predicted_collisions(
    objects: list[SpaceObject],
    horizon_s: float,
    cfg: CollisionConfig | None = None,
) -> list[tuple[str, str, float, float]]:
    """Predict collisions within a future horizon using TCA (linear approximation).

    Strategy:
    - Broadphase: find nearby *candidate* pairs using a radius inflated by
      max object speed within the horizon.
    - Narrowphase: for each candidate pair, compute TCA and miss distance.

    Returns:
        List of (id_a, id_b, t_ca_s, d_ca_km) for pairs where:
            0 <= t_ca_s <= horizon_s and d_ca_km < collision_distance_km
    """
    if cfg is None:
        cfg = CollisionConfig()

    n = len(objects)
    if n < 2:
        return []

    horizon = float(horizon_s)
    if not np.isfinite(horizon) or horizon <= 0.0:
        raise ValueError("horizon_s must be a finite positive float")

    positions = np.stack([o.r for o in objects], axis=0).astype(np.float64, copy=False)
    velocities = np.stack([o.v for o in objects], axis=0).astype(np.float64, copy=False)
    ids = [o.id for o in objects]

    # Inflate broadphase radius by worst-case travel during the horizon.
    speeds = np.linalg.norm(velocities, axis=1)
    vmax = float(np.max(speeds)) if speeds.size else 0.0
    search_radius = float(cfg.collision_distance_km) + vmax * horizon

    if cfg.prefer_kdtree and _HAS_SCIPY:
        broadphase: Broadphase = KDTreeBroadphase()
    else:
        broadphase = ChunkedNaiveBroadphase(block_size=cfg.block_size)

    candidate_pairs = broadphase.detect_pairs(positions, search_radius)
    if candidate_pairs.shape[0] > cfg.max_pairs:
        candidate_pairs = candidate_pairs[: cfg.max_pairs]

    out: list[tuple[str, str, float, float]] = []
    thr = float(cfg.collision_distance_km)
    for i, j in candidate_pairs:
        oi = objects[int(i)]
        oj = objects[int(j)]
        t_ca, d_ca = compute_tca(oi, oj)
        if 0.0 <= t_ca <= horizon and d_ca < thr:
            a, b = ids[int(i)], ids[int(j)]
            if a > b:
                a, b = b, a
            out.append((a, b, t_ca, d_ca))
    return out


def detect_collisions(objects: list[SpaceObject], cfg: CollisionConfig | None = None) -> list[tuple[str, str]]:
    """Detect collision pairs based on a fixed distance threshold.

    Logic:
        If ||r_i - r_j|| < 0.1 km, report (id_i, id_j).

    Returns:
        List of (id_a, id_b) pairs (each pair is unique; order is arbitrary).

    Designed so the broadphase can be swapped (KD-tree vs fallback).
    """
    if cfg is None:
        cfg = CollisionConfig()

    n = len(objects)
    if n < 2:
        return []

    positions = np.stack([o.r for o in objects], axis=0).astype(np.float64, copy=False)
    ids = [o.id for o in objects]

    if cfg.prefer_kdtree and _HAS_SCIPY:
        broadphase: Broadphase = KDTreeBroadphase()
    else:
        broadphase = ChunkedNaiveBroadphase(block_size=cfg.block_size)

    pairs = broadphase.detect_pairs(positions, cfg.collision_distance_km)

    if pairs.shape[0] > cfg.max_pairs:
        pairs = pairs[: cfg.max_pairs]

    return [(ids[int(i)], ids[int(j)]) for i, j in pairs]


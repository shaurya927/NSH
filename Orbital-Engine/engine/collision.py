from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True, slots=True)
class CollisionConfig:
    collision_distance_km: float = 0.1
    max_pairs: int = 5_000_000
    # KDTree candidate search radius for conjunction assessment.
    conjunction_candidate_radius_km: float = 50.0
    risk_critical_km: float = 0.1
    risk_medium_km: float = 1.0
    risk_low_km: float = 5.0
    max_conjunction_results: int = 20_000


class CollisionEngine:
    """KDTree collision detector with optional TCA prediction."""

    def __init__(self, cfg: CollisionConfig | None = None) -> None:
        self._cfg = cfg or CollisionConfig()

    def detect_pairs(self, positions_km: np.ndarray) -> np.ndarray:
        pos = np.asarray(positions_km, dtype=np.float64)
        if pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions_km must be shape (N,3)")

        n = int(pos.shape[0])
        if n < 2:
            return np.empty((0, 2), dtype=np.int32)

        tree = cKDTree(pos)
        pairs = tree.query_pairs(
            r=float(self._cfg.collision_distance_km),
            output_type="ndarray",
        )
        if pairs.size == 0:
            return np.empty((0, 2), dtype=np.int32)
        if pairs.shape[0] > self._cfg.max_pairs:
            pairs = pairs[: self._cfg.max_pairs]
        return pairs.astype(np.int32, copy=False)

    def assess_conjunctions(
        self,
        ids: list[str],
        positions_km: np.ndarray,
        velocities_km_s: np.ndarray,
        horizon_s: float,
    ) -> list[dict[str, object]]:
        """Predict conjunctions using linear relative motion and TCA.

        Uses:
            t_ca = - (r_rel dot v_rel) / |v_rel|^2
            r_closest = r_rel + v_rel * t_ca

        Returns compact risk-tagged records.
        """
        pos = np.asarray(positions_km, dtype=np.float64)
        vel = np.asarray(velocities_km_s, dtype=np.float64)
        if pos.shape != vel.shape or pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions_km and velocities_km_s must be shape (N,3)")

        n = int(pos.shape[0])
        if n < 2:
            return []

        horizon = float(horizon_s)
        if not np.isfinite(horizon) or horizon <= 0.0:
            raise ValueError("horizon_s must be finite and > 0")

        candidate_radius = float(self._cfg.conjunction_candidate_radius_km)
        if not np.isfinite(candidate_radius) or candidate_radius <= 0.0:
            candidate_radius = float(self._cfg.risk_low_km)

        tree = cKDTree(pos)
        pairs = tree.query_pairs(r=candidate_radius, output_type="ndarray")
        if pairs.size == 0:
            return []
        if pairs.shape[0] > self._cfg.max_pairs:
            pairs = pairs[: self._cfg.max_pairs]

        i = pairs[:, 0]
        j = pairs[:, 1]

        r_rel = pos[j] - pos[i]
        v_rel = vel[j] - vel[i]

        v2 = np.einsum("ij,ij->i", v_rel, v_rel)
        rv = np.einsum("ij,ij->i", r_rel, v_rel)

        # TCA with clamp t >= 0 and t <= horizon.
        t_ca = np.zeros_like(v2)
        moving = v2 > 0.0
        t_ca[moving] = -rv[moving] / v2[moving]
        np.clip(t_ca, 0.0, horizon, out=t_ca)

        r_ca = r_rel + v_rel * t_ca[:, None]
        d_ca = np.sqrt(np.einsum("ij,ij->i", r_ca, r_ca))

        low_thr = float(self._cfg.risk_low_km)
        med_thr = float(self._cfg.risk_medium_km)
        crit_thr = float(self._cfg.risk_critical_km)
        hit = d_ca < low_thr
        if not np.any(hit):
            return []

        pairs_h = pairs[hit]
        t_h = t_ca[hit]
        d_h = d_ca[hit]

        risk = np.full(d_h.shape, "LOW", dtype=object)
        risk[d_h < med_thr] = "MEDIUM"
        risk[d_h < crit_thr] = "CRITICAL"

        # Sort by severity (miss distance) then by earliest TCA.
        order = np.lexsort((t_h, d_h))
        if order.size > self._cfg.max_conjunction_results:
            order = order[: self._cfg.max_conjunction_results]

        out: list[dict[str, object]] = []
        for k in order:
            a = int(pairs_h[k, 0])
            b = int(pairs_h[k, 1])
            id_a = ids[a]
            id_b = ids[b]
            if id_a > id_b:
                id_a, id_b = id_b, id_a
            out.append(
                {
                    "object_a": id_a,
                    "object_b": id_b,
                    "tca_s": float(t_h[k]),
                    "miss_distance_km": float(d_h[k]),
                    "risk_level": str(risk[k]),
                }
            )

        return out

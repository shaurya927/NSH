from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Literal

import numpy as np

from .collision import CollisionConfig, CollisionEngine
from .integrator import RK4Workspace, rk4_step_many
from .maneuver import ManeuverConfig, apply_burn_batch, rtn_basis_many, rtn_to_eci_many
from .scheduler import ManeuverScheduler, ScheduledManeuver
from .utils import EngineConfig, as_vec3_array, compress_positions_b64, compute_lat_lon_deg, get_logger


ObjectType = Literal["SATELLITE", "DEBRIS"]


@dataclass(slots=True)
class _ObjectRecord:
    object_id: str
    object_type: ObjectType
    r: np.ndarray
    v: np.ndarray
    mass: float
    fuel: float | None


@dataclass(slots=True)
class _GroundStation:
    station_id: str
    lat_rad: float
    lon_rad: float
    min_elev_rad: float


class _PopulationStore:
    """Dense array-backed storage for one object population."""

    def __init__(self, population: ObjectType, initial_capacity: int, dtype: np.dtype) -> None:
        self.population = population
        self.size: int = 0
        self.capacity: int = max(1, int(initial_capacity))
        self.dtype = dtype

        self.ids: list[str] = []
        self.id_to_index: dict[str, int] = {}

        self.r = np.empty((self.capacity, 3), dtype=dtype)
        self.v = np.empty((self.capacity, 3), dtype=dtype)
        self.mass = np.empty((self.capacity,), dtype=dtype)
        self.fuel = np.empty((self.capacity,), dtype=dtype) if population == "SATELLITE" else None

    def _ensure_capacity(self, target_size: int) -> None:
        if target_size <= self.capacity:
            return
        new_capacity = self.capacity
        while new_capacity < target_size:
            new_capacity *= 2

        self.r = self._resize_2d(self.r, new_capacity)
        self.v = self._resize_2d(self.v, new_capacity)
        self.mass = self._resize_1d(self.mass, new_capacity)
        if self.fuel is not None:
            self.fuel = self._resize_1d(self.fuel, new_capacity)
        self.capacity = new_capacity

    @staticmethod
    def _resize_2d(arr: np.ndarray, new_capacity: int) -> np.ndarray:
        out = np.empty((new_capacity, arr.shape[1]), dtype=arr.dtype)
        out[: arr.shape[0]] = arr
        return out

    @staticmethod
    def _resize_1d(arr: np.ndarray, new_capacity: int) -> np.ndarray:
        out = np.empty((new_capacity,), dtype=arr.dtype)
        out[: arr.shape[0]] = arr
        return out

    def remove(self, object_id: str) -> bool:
        idx = self.id_to_index.get(object_id)
        if idx is None:
            return False

        last = self.size - 1
        if idx != last:
            self.r[idx] = self.r[last]
            self.v[idx] = self.v[last]
            self.mass[idx] = self.mass[last]
            if self.fuel is not None:
                self.fuel[idx] = self.fuel[last]

            moved_id = self.ids[last]
            self.ids[idx] = moved_id
            self.id_to_index[moved_id] = idx

        self.ids.pop()
        del self.id_to_index[object_id]
        self.size -= 1
        return True

    def upsert(self, rec: _ObjectRecord) -> int:
        idx = self.id_to_index.get(rec.object_id)
        if idx is None:
            self._ensure_capacity(self.size + 1)
            idx = self.size
            self.size += 1
            self.ids.append(rec.object_id)
            self.id_to_index[rec.object_id] = idx

        self.r[idx] = rec.r
        self.v[idx] = rec.v
        self.mass[idx] = rec.mass
        if self.fuel is not None:
            self.fuel[idx] = float(rec.fuel if rec.fuel is not None else 0.0)
        return idx

    @property
    def r_active(self) -> np.ndarray:
        return self.r[: self.size]

    @property
    def v_active(self) -> np.ndarray:
        return self.v[: self.size]

    @property
    def mass_active(self) -> np.ndarray:
        return self.mass[: self.size]

    @property
    def fuel_active(self) -> np.ndarray:
        if self.fuel is None:
            raise ValueError("debris store has no fuel array")
        return self.fuel[: self.size]


class ACMEngine:
    """Production-grade modular simulation engine entrypoint.

    Responsibilities:
    - dense object storage for satellite/debris populations
    - vectorized propagation
    - O(log n) time-based maneuver scheduling
    - KDTree collision detection + TCA prediction support
    - compact snapshots for frontend consumption
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self.logger = get_logger("engine.ACMEngine")
        self._state_dtype = np.dtype(self.config.state_dtype)

        self.current_time_s: float = 0.0

        self._sat = _PopulationStore("SATELLITE", self.config.initial_capacity, self._state_dtype)
        self._deb = _PopulationStore("DEBRIS", self.config.initial_capacity, self._state_dtype)

        # Fast global lookup that external systems can rely on.
        self.id_to_index: dict[str, tuple[ObjectType, int]] = {}

        self._scheduler = ManeuverScheduler()
        self._maneuver_cfg = ManeuverConfig()
        self._cooldown_until_s: dict[str, float] = {}

        # Station-keeping state (per-satellite).
        self._nominal_slots_r: dict[str, np.ndarray] = {}
        self._sk_uptime_s: dict[str, float] = {}
        self._sk_outage_s: dict[str, float] = {}
        self._sk_status: dict[str, str] = {}
        self._sk_last_deviation_km: dict[str, float] = {}
        self._sk_recovery_pending: set[str] = set()

        # Fuel / end-of-life tracking (per-satellite).
        self._initial_fuel_kg: dict[str, float] = {}
        self._eol_state: dict[str, str] = {}
        self._eol_graveyard_epoch_s: dict[str, float] = {}

        self._collision = CollisionEngine(
            CollisionConfig(
                collision_distance_km=self.config.collision_distance_km,
                max_pairs=self.config.collision_max_pairs,
                conjunction_candidate_radius_km=self.config.conjunction_candidate_radius_km,
                risk_critical_km=self.config.risk_critical_km,
                risk_medium_km=self.config.risk_medium_km,
                risk_low_km=self.config.risk_low_km,
                max_conjunction_results=self.config.max_conjunction_results,
            )
        )

        self._rk4_ws_sat = RK4Workspace()
        self._combined_capacity = 0
        self._combined_r = np.empty((0, 3), dtype=self._state_dtype)
        self._combined_v = np.empty((0, 3), dtype=self._state_dtype)

        # Ground station set for LOS / communication constraints.
        self._ground_stations: list[_GroundStation] = []

        # Per-step maneuver accounting.
        self._last_burn_epoch_s: dict[str, float] = {}

        # Trajectory history (for frontend visualization).
        self._traj_history_dt_s: float = 60.0  # sample period
        self._traj_history_horizon_s: float = 90.0 * 60.0  # 90 minutes
        self._traj_history_last_sample_s: float = 0.0
        self._traj_history: dict[str, list[tuple[float, np.ndarray]]] = {}

    def ingest_telemetry(self, data: dict[str, object]) -> dict[str, int]:
        """Ingest telemetry into dense arrays.

        Input shape:
            {"objects": [{"id", "type", "r_km", "v_km_s", "mass_kg", "fuel_kg"}, ...]}
        """
        t0 = perf_counter()
        raw_objects = data.get("objects")
        if not isinstance(raw_objects, list):
            raise ValueError("telemetry payload must include objects list")

        upserted = 0
        for raw in raw_objects:
            rec = self._parse_record(raw)

            # If type changed since last upsert, remove old slot before inserting.
            existing = self.id_to_index.get(rec.object_id)
            if existing is not None and existing[0] != rec.object_type:
                self._store_for(existing[0]).remove(rec.object_id)
                del self.id_to_index[rec.object_id]
                # Clean up any satellite-specific metadata when population changes.
                if existing[0] == "SATELLITE":
                    self._clear_satellite_metadata(rec.object_id)

            store = self._store_for(rec.object_type)
            idx = store.upsert(rec)
            self.id_to_index[rec.object_id] = (rec.object_type, idx)
            upserted += 1

            # Initialize nominal orbital slot for newly seen satellites.
            if rec.object_type == "SATELLITE" and rec.object_id not in self._nominal_slots_r:
                # First ingested position becomes the reference slot by default.
                self._nominal_slots_r[rec.object_id] = rec.r.astype(np.float64, copy=True)
                self._sk_uptime_s.setdefault(rec.object_id, 0.0)
                self._sk_outage_s.setdefault(rec.object_id, 0.0)
                self._sk_status.setdefault(rec.object_id, "NOMINAL")
                self._sk_last_deviation_km.setdefault(rec.object_id, 0.0)

            # Track initial fuel for EOL thresholding.
            if rec.object_type == "SATELLITE":
                fuel0 = float(rec.fuel if rec.fuel is not None else 0.0)
                prev = self._initial_fuel_kg.get(rec.object_id)
                if prev is None or fuel0 > prev:
                    self._initial_fuel_kg[rec.object_id] = fuel0
                self._eol_state.setdefault(rec.object_id, "ACTIVE")

                # Initialize trajectory history container for this satellite.
                self._traj_history.setdefault(rec.object_id, [])

        # Rebuild global index for entries potentially moved by swap-remove.
        self._rebuild_global_index()

        self.logger.info(
            "ingest_telemetry upserted=%d total=%d sat=%d debris=%d elapsed_ms=%.2f",
            upserted,
            self.object_count,
            self._sat.size,
            self._deb.size,
            (perf_counter() - t0) * 1000.0,
        )
        return {
            "objects_upserted": upserted,
            "objects_total": self.object_count,
            "satellites_total": self._sat.size,
            "debris_total": self._deb.size,
        }

    def load_ground_stations(self, data: dict[str, object]) -> dict[str, int]:
        """Load or replace the ground station dataset.

        Expected shape:
            {"stations": [{"id", "lat_deg", "lon_deg", "min_elev_deg"}, ...]}
        """
        raw_stations = data.get("stations")
        if not isinstance(raw_stations, list):
            raise ValueError("ground station payload must include stations list")

        stations: list[_GroundStation] = []
        for raw in raw_stations:
            if not isinstance(raw, dict):
                raise ValueError("each station must be a dict")
            sid = str(raw.get("id", "")).strip() or "GS"
            try:
                lat_deg = float(raw.get("lat_deg"))
                lon_deg = float(raw.get("lon_deg"))
                min_el_deg = float(raw.get("min_elev_deg", 0.0))
            except (TypeError, ValueError) as exc:
                raise ValueError("lat_deg, lon_deg, and min_elev_deg must be numeric") from exc

            lat_rad = np.deg2rad(lat_deg)
            lon_rad = np.deg2rad(lon_deg)
            min_el_rad = np.deg2rad(min_el_deg)
            stations.append(_GroundStation(station_id=sid, lat_rad=lat_rad, lon_rad=lon_rad, min_elev_rad=min_el_rad))

        self._ground_stations = stations
        self.logger.info("ground_stations_loaded count=%d", len(stations))
        return {"stations_loaded": len(stations)}

    def schedule_maneuver(self, data: dict[str, object]) -> dict[str, float]:
        """Schedule a maneuver for future execution."""
        object_id = str(data.get("object_id", ""))
        if not object_id:
            raise ValueError("object_id is required")

        # Backward compatible input handling:
        # - preferred key: delta_v_rtn_km_s
        # - legacy key: delta_v_km_s (interpreted as RTN)
        raw_dv = data.get("delta_v_rtn_km_s")
        field_name = "delta_v_rtn_km_s"
        if raw_dv is None:
            raw_dv = data.get("delta_v_km_s")
            field_name = "delta_v_km_s"
        if raw_dv is None:
            raise ValueError("delta_v_rtn_km_s is required")

        dv_rtn = as_vec3_array(raw_dv, field_name)
        epoch = data.get("epoch_s")
        # Enforce a minimum communication latency for externally scheduled maneuvers.
        latency = float(self.config.scheduler_latency_s)
        earliest = self.current_time_s + latency
        burn_time = float(epoch) if epoch is not None else earliest
        if burn_time < earliest:
            burn_time = earliest

        # Communication constraints: require line-of-sight to at least one ground
        # station at scheduling time when enabled.
        if self.config.enable_comm_constraints and self._ground_stations:
            slot = self.id_to_index.get(object_id)
            if slot is None or slot[0] != "SATELLITE":
                raise ValueError("maneuvers can only be scheduled for active satellites under comm constraints")
            if not self._has_los_for_sat_index(slot[1]):
                raise ValueError("cannot schedule maneuver: no line-of-sight to any ground station (below min elevation)")

        self._scheduler.schedule(
            ScheduledManeuver(
                object_id=object_id,
                epoch_s=burn_time,
                delta_v_rtn_km_s=dv_rtn,
                requires_los=True,
            )
        )
        self.logger.debug(
            "maneuver_scheduled_rtn object_id=%s burn_time_s=%.3f dv_rtn=[%.6f,%.6f,%.6f] queue=%d",
            object_id,
            burn_time,
            float(dv_rtn[0]),
            float(dv_rtn[1]),
            float(dv_rtn[2]),
            len(self._scheduler),
        )
        return {"scheduled_for_time_s": burn_time}

    def step_simulation(self, step_seconds: float) -> dict[str, object]:
        """Advance simulation in fixed-size ticks with vectorized internals."""
        t0 = perf_counter()
        step = float(step_seconds)
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("step_seconds must be finite and > 0")

        dt = float(self.config.integration_tick_s)
        ticks = int(step // dt)
        if ticks > int(self.config.max_step_ticks):
            raise ValueError(
                f"requested ticks ({ticks}) exceeds max_step_ticks ({self.config.max_step_ticks})"
            )

        collisions: set[tuple[str, str]] = set()
        conjunctions: list[dict[str, object]] = []
        maneuvers_executed = 0
        autonomous_sequences: list[dict[str, object]] = []

        for _ in range(ticks):
            self._propagate(dt)
            self.current_time_s += dt

            due = self._scheduler.pop_due(self.current_time_s)
            maneuvers_executed += self._execute_maneuvers(due)

            # Update station-keeping status and metrics each tick.
            self._update_station_keeping(dt)

            # Sample trajectory history for past 90-minute visualization.
            self._update_trajectory_history()

        # Handle end-of-life removals after all ticks and burns.
        self._finalize_eol_removals()

        ids, pos, vel = self._combined_state()
        coll_pairs = self._collision.detect_pairs(pos)
        if coll_pairs.size:
            for i, j in coll_pairs:
                a = ids[int(i)]
                b = ids[int(j)]
                collisions.add((a, b) if a < b else (b, a))

        if self.config.enable_tca_prediction and self.config.collision_future_horizon_s > 0.0:
            conjunctions = self._collision.assess_conjunctions(
                ids=ids,
                positions_km=pos,
                velocities_km_s=vel,
                horizon_s=float(self.config.collision_future_horizon_s),
            )
            if self.config.enable_auto_avoidance:
                autonomous_sequences = self._plan_autonomous_avoidance(conjunctions)

        station_keeping = self._build_station_keeping_report() if self.config.enable_station_keeping else []

        # Simple maneuver accounting for this step: executed count is already
        # tracked via maneuvers_executed; rejected/conflict counts are
        # reflected by scheduler/validation exceptions at schedule time.
        maneuver_stats = {
            "executed": maneuvers_executed,
        }

        result = {
            "ticks": ticks,
            "collisions_detected": sorted(collisions),
            "predicted_conjunctions": conjunctions,
            "autonomous_maneuvers": autonomous_sequences,
            "maneuvers_executed": maneuvers_executed,
            "maneuver_stats": maneuver_stats,
            "station_keeping": station_keeping,
            "simulation_time_s": self.current_time_s,
        }
        sk_out_of_bounds = sum(1 for sk in station_keeping if sk.get("status") == "OUT_OF_BOUNDS")
        self.logger.info(
            "step_simulation step_s=%.3f ticks=%d objects=%d collisions=%d conjunctions=%d auto_planned=%d maneuvers=%d sk_out_of_bounds=%d elapsed_ms=%.2f",
            step,
            ticks,
            self.object_count,
            len(collisions),
            len(conjunctions),
            len(autonomous_sequences),
            maneuvers_executed,
            sk_out_of_bounds,
            (perf_counter() - t0) * 1000.0,
        )
        return result

    def _update_station_keeping(self, dt: float) -> None:
        """Update station-keeping status, metrics, and recovery plans.

        For each satellite:
        - Ensure it has a nominal slot (first ingested position by default).
        - Compute distance to nominal slot.
        - Classify as NOMINAL or OUT_OF_BOUNDS based on configured radius.
        - Accumulate uptime/outage durations.
        - If OUT_OF_BOUNDS and no recovery is pending, schedule a recovery maneuver.
        """
        if not self.config.enable_station_keeping:
            return
        if self._sat.size == 0:
            return

        radius = float(self.config.station_keeping_radius_km)

        for idx, object_id in enumerate(self._sat.ids):
            r_curr = self._sat.r[idx].astype(np.float64, copy=False)

            nominal = self._nominal_slots_r.get(object_id)
            if nominal is None:
                nominal = r_curr.copy()
                self._nominal_slots_r[object_id] = nominal
                self._sk_uptime_s.setdefault(object_id, 0.0)
                self._sk_outage_s.setdefault(object_id, 0.0)

            deviation = float(np.linalg.norm(r_curr - nominal))
            self._sk_last_deviation_km[object_id] = deviation

            status = "NOMINAL" if deviation <= radius else "OUT_OF_BOUNDS"
            self._sk_status[object_id] = status

            if status == "NOMINAL":
                self._sk_uptime_s[object_id] = self._sk_uptime_s.get(object_id, 0.0) + dt
                self._sk_outage_s.setdefault(object_id, 0.0)
                # Clear any pending recovery once back inside the box.
                self._sk_recovery_pending.discard(object_id)
            else:
                self._sk_outage_s[object_id] = self._sk_outage_s.get(object_id, 0.0) + dt
                self._sk_uptime_s.setdefault(object_id, 0.0)

                # Schedule a recovery maneuver if none is pending yet.
                if object_id not in self._sk_recovery_pending:
                    v_curr = self._sat.v[idx].astype(np.float64, copy=False)
                    scheduled = self._schedule_station_keeping_recovery(
                        object_id=object_id,
                        r_curr=r_curr,
                        v_curr=v_curr,
                        nominal_r=nominal,
                        deviation_km=deviation,
                    )
                    if scheduled:
                        self._sk_recovery_pending.add(object_id)

    def _schedule_station_keeping_recovery(
        self,
        object_id: str,
        r_curr: np.ndarray,
        v_curr: np.ndarray,
        nominal_r: np.ndarray,
        deviation_km: float,
    ) -> bool:
        """Plan and enqueue a single efficient recovery burn in RTN.

        Heuristic: generate an in-plane (R/T) delta-v pointing roughly back
        toward the nominal slot, with magnitude sized by the deviation and a
        configurable correction timescale, and capped to a fraction of
        max_dv_km_s.
        """
        slot = self.id_to_index.get(object_id)
        if slot is None or slot[0] != "SATELLITE":
            return False

        timescale = max(float(self.config.station_keeping_recovery_timescale_s), 1.0)
        max_dv = float(self._maneuver_cfg.max_dv_km_s)
        frac = float(self.config.station_keeping_max_dv_fraction)
        dv_cap = max(0.0, min(max_dv, max_dv * frac))
        if dv_cap <= 0.0:
            return False

        # Direction from nominal slot to current position, projected into RTN.
        dr = r_curr - nominal_r
        R, T, _N = rtn_basis_many(r_curr[None, :], v_curr[None, :])
        r_axis = R[0]
        t_axis = T[0]

        dr_r = float(np.dot(dr, r_axis))
        dr_t = float(np.dot(dr, t_axis))
        in_plane = np.array([dr_r, dr_t, 0.0], dtype=np.float64)
        norm_in_plane = float(np.linalg.norm(in_plane))
        if norm_in_plane <= 0.0:
            return False

        # Size the burn so that, over the correction timescale, the induced
        # displacement is on the order of the deviation, but never exceeding
        # dv_cap to preserve fuel and leave room for other maneuvers.
        target_mag = deviation_km / timescale
        dv_mag = min(dv_cap, max(0.0, target_mag))
        if dv_mag <= 0.0:
            return False

        unit_rtn = in_plane / norm_in_plane
        dv_rtn = -dv_mag * unit_rtn

        burn_time = self.current_time_s + float(self.config.scheduler_latency_s)
        self._scheduler.schedule(
            ScheduledManeuver(
                object_id=object_id,
                epoch_s=burn_time,
                delta_v_rtn_km_s=dv_rtn,
                requires_los=False,
            )
        )
        self.logger.debug(
            "station_keeping_recovery_scheduled object_id=%s deviation_km=%.3f dv_rtn=[%.6f,%.6f,%.6f] burn_time_s=%.3f",
            object_id,
            deviation_km,
            float(dv_rtn[0]),
            float(dv_rtn[1]),
            float(dv_rtn[2]),
            burn_time,
        )
        return True

    def _build_station_keeping_report(self) -> list[dict[str, object]]:
        """Build a per-satellite station-keeping summary for the step output."""
        if self._sat.size == 0:
            return []

        radius = float(self.config.station_keeping_radius_km)
        report: list[dict[str, object]] = []
        for object_id in self._sat.ids:
            deviation = float(self._sk_last_deviation_km.get(object_id, 0.0))
            status = self._sk_status.get(
                object_id,
                "NOMINAL" if deviation <= radius else "OUT_OF_BOUNDS",
            )
            uptime = float(self._sk_uptime_s.get(object_id, 0.0))
            outage = float(self._sk_outage_s.get(object_id, 0.0))
            report.append(
                {
                    "id": object_id,
                    "deviation_km": deviation,
                    "status": status,
                    "uptime_s": uptime,
                    "outage_s": outage,
                }
            )
        return report

    def _update_trajectory_history(self) -> None:
        """Maintain a decimated history of satellite positions for 90 minutes.

        Samples at a fixed period (_traj_history_dt_s) and keeps only entries
        within the configured horizon to bound memory.
        """
        if self._sat.size == 0:
            return

        if (self.current_time_s - self._traj_history_last_sample_s) < self._traj_history_dt_s:
            return

        self._traj_history_last_sample_s = self.current_time_s
        horizon_start = self.current_time_s - self._traj_history_horizon_s

        for idx, sid in enumerate(self._sat.ids):
            r = self._sat.r[idx].astype(np.float64, copy=False).copy()
            hist = self._traj_history.setdefault(sid, [])
            hist.append((self.current_time_s, r))
            # Drop samples older than horizon.
            while hist and hist[0][0] < horizon_start:
                hist.pop(0)

    def _build_trajectory_snapshot(self) -> dict[str, dict[str, list[list[float]]]]:
        """Construct past and predicted trajectories for all satellites.

        Past: sampled positions over the last 90 minutes.
        Future: coarse prediction over the next 90 minutes using a copy of the
        integrator state, at the same sample period.
        """
        result: dict[str, dict[str, list[list[float]]]] = {}

        if self._sat.size == 0:
            return result

        # Past trajectories.
        for sid in self._sat.ids:
            hist = self._traj_history.get(sid, [])
            if not hist:
                continue
            times, positions = zip(*hist)
            pos_arr = np.stack(positions, axis=0)
            lat, lon = compute_lat_lon_deg(pos_arr)
            R_EARTH_KM = 6378.137
            alt = np.linalg.norm(pos_arr, axis=1) - R_EARTH_KM
            past_rows = [[float(lat[i]), float(lon[i]), float(alt[i])] for i in range(pos_arr.shape[0])]
            result.setdefault(sid, {})["past"] = past_rows

        # Future trajectories: simple propagation ignoring future maneuvers.
        horizon_s = self._traj_history_horizon_s
        dt = self._traj_history_dt_s
        steps = int(horizon_s // dt)
        if steps <= 0:
            return result

        sat_n = self._sat.size
        r_pred = self._sat.r_active.astype(np.float64, copy=True)
        v_pred = self._sat.v_active.astype(np.float64, copy=True)

        for _ in range(steps):
            r_pred, v_pred = rk4_step_many(r_pred, v_pred, dt, workspace=self._rk4_ws_sat)
            lat, lon = compute_lat_lon_deg(r_pred)
            R_EARTH_KM = 6378.137
            alt = np.linalg.norm(r_pred, axis=1) - R_EARTH_KM
            for i, sid in enumerate(self._sat.ids):
                row = [float(lat[i]), float(lon[i]), float(alt[i])]
                bucket = result.setdefault(sid, {})
                bucket.setdefault("future", []).append(row)

        return result

    def _derive_satellite_status(self, satellite_id: str, fuel_kg: float) -> str:
        """Compute a simple high-level status for snapshot consumption."""
        # Station-keeping OUT_OF_BOUNDS takes precedence.
        if self._sk_status.get(satellite_id) == "OUT_OF_BOUNDS":
            return "OUT_OF_BOUNDS"

        # Low-fuel or EOL-planned satellites raise an alert.
        state = self._eol_state.get(satellite_id, "ACTIVE")
        if state != "ACTIVE" or fuel_kg <= 0.0:
            return "ALERT"

        return "NOMINAL"

    def _update_eol_after_burn(self, sat_indices: np.ndarray) -> None:
        """Check for fuel-based end-of-life and plan graveyard maneuvers.

        A satellite enters EOL when its remaining fuel drops below 5% of the
        tracked initial fuel. At that point, a final graveyard burn is
        scheduled, sized not to exceed available fuel or maneuver dv caps.
        """
        if self._sat.fuel is None:
            return
        if not len(sat_indices):
            return

        threshold = 0.05
        idx_arr = np.asarray(sat_indices, dtype=np.int64)
        for sat_idx in idx_arr:
            if sat_idx < 0 or sat_idx >= self._sat.size:
                continue
            object_id = self._sat.ids[sat_idx]
            init_fuel = self._initial_fuel_kg.get(object_id)
            if init_fuel is None or init_fuel <= 0.0:
                continue

            current_fuel = float(self._sat.fuel[sat_idx])
            frac = current_fuel / init_fuel if init_fuel > 0.0 else 0.0
            state = self._eol_state.get(object_id, "ACTIVE")
            if frac < threshold and state == "ACTIVE":
                if self._schedule_eol_graveyard(object_id, sat_idx):
                    self._eol_state[object_id] = "EOL_PLANNED"

    def _schedule_eol_graveyard(self, object_id: str, sat_idx: int) -> bool:
        """Schedule a one-time graveyard orbit maneuver for an EOL satellite.

        The burn is purely radial (R direction in RTN) to raise the orbit,
        with magnitude limited by both available fuel (via rocket equation)
        and the configured max_dv_km_s.
        """
        if self._sat.fuel is None:
            return False
        if sat_idx < 0 or sat_idx >= self._sat.size:
            return False

        fuel = float(self._sat.fuel[sat_idx])
        mass = float(self._sat.mass[sat_idx])
        if fuel <= 0.0 or mass <= fuel:
            return False

        cfg = self._maneuver_cfg
        ve = float(cfg.isp_s) * float(cfg.g0_m_s2)
        dv_limit_m_s = ve * np.log(mass / (mass - fuel))
        if not np.isfinite(dv_limit_m_s) or dv_limit_m_s <= 0.0:
            return False

        dv_limit_km_s = dv_limit_m_s / 1000.0
        dv_cap = float(cfg.max_dv_km_s)
        dv_mag = min(dv_limit_km_s, dv_cap)
        if dv_mag <= 0.0:
            return False

        dv_rtn = np.array([dv_mag, 0.0, 0.0], dtype=np.float64)
        burn_time = self.current_time_s + float(self.config.scheduler_latency_s)

        self._scheduler.schedule(
            ScheduledManeuver(
                object_id=object_id,
                epoch_s=burn_time,
                delta_v_rtn_km_s=dv_rtn,
                requires_los=False,
            )
        )
        self._eol_graveyard_epoch_s[object_id] = burn_time
        self.logger.info(
            "eol_graveyard_maneuver_scheduled object_id=%s dv_mag_km_s=%.6f fuel_kg=%.3f mass_kg=%.3f burn_time_s=%.3f",
            object_id,
            dv_mag,
            fuel,
            mass,
            burn_time,
        )
        return True

    def _finalize_eol_removals(self) -> None:
        """Demote EOL satellites to debris after graveyard burns are due."""
        if not self._eol_graveyard_epoch_s:
            return

        now = self.current_time_s
        to_remove: list[str] = []
        for object_id, epoch in list(self._eol_graveyard_epoch_s.items()):
            if now >= epoch and self._eol_state.get(object_id) == "EOL_PLANNED":
                to_remove.append(object_id)

        for object_id in to_remove:
            slot = self.id_to_index.get(object_id)
            if slot is None or slot[0] != "SATELLITE":
                # Already removed or repurposed; just clear metadata.
                self._clear_satellite_metadata(object_id)
                continue

            _, idx = slot
            r = self._sat.r[idx].copy()
            v = self._sat.v[idx].copy()
            mass = float(self._sat.mass[idx])

            # Remove from satellite population and rebuild index after swap-remove.
            self._sat.remove(object_id)
            self._rebuild_global_index()

            # Reinsert as debris to keep it in the simulation but out of the active constellation.
            rec = _ObjectRecord(
                object_id=object_id,
                object_type="DEBRIS",
                r=r.astype(self._state_dtype, copy=False),
                v=v.astype(self._state_dtype, copy=False),
                mass=self._state_dtype.type(mass),
                fuel=None,
            )
            deb_idx = self._deb.upsert(rec)
            self.id_to_index[object_id] = ("DEBRIS", deb_idx)
            self._eol_state[object_id] = "EOL_REMOVED"
            self.logger.info(
                "eol_satellite_demoted_to_debris object_id=%s mass_kg=%.3f time_s=%.3f",
                object_id,
                mass,
                now,
            )

            # Clear satellite-specific metadata now that it is debris.
            self._clear_satellite_metadata(object_id)

    def get_snapshot(self) -> dict[str, object]:
        """Return compact frontend-friendly state payload."""
        sat_rows: list[list[object]] = []
        sat_n = self._sat.size
        if sat_n:
            lat, lon = compute_lat_lon_deg(self._sat.r_active)
            fuel = self._sat.fuel_active
            # Snapshot generation is naturally row-oriented for frontend payloads.
            for i, sid in enumerate(self._sat.ids):
                f = float(fuel[i])
                status = self._derive_satellite_status(sid, f)
                sat_rows.append([sid, float(lat[i]), float(lon[i]), f, status])

        # Debris: compact row format [id, lat, lon, altitude_km].
        deb_rows: list[list[object]] = []
        deb_n = self._deb.size
        if deb_n:
            deb_pos = self._deb.r_active.astype(np.float64, copy=False)
            dlat, dlon = compute_lat_lon_deg(deb_pos)
            r_norm = np.linalg.norm(deb_pos, axis=1)
            R_EARTH_KM = 6378.137
            alt = r_norm - R_EARTH_KM
            for i, did in enumerate(self._deb.ids):
                deb_rows.append([did, float(dlat[i]), float(dlon[i]), float(alt[i])])

        trajectories = self._build_trajectory_snapshot()

        return {
            "timestamp_s": self.current_time_s,
            "satellites": sat_rows,
            "debris": deb_rows,
            "trajectories": trajectories,
        }

    def assess_conjunctions(self, horizon_s: float = 86_400.0) -> list[dict[str, object]]:
        """Run predictive conjunction assessment on current state."""
        ids, pos, vel = self._combined_state()
        return self._collision.assess_conjunctions(
            ids=ids,
            positions_km=pos,
            velocities_km_s=vel,
            horizon_s=float(horizon_s),
        )

    @property
    def object_count(self) -> int:
        return self._sat.size + self._deb.size

    def _propagate(self, dt: float) -> tuple[np.ndarray, np.ndarray]:
        total = self.object_count
        if total == 0:
            empty = np.empty((0, 3), dtype=self._state_dtype)
            return empty, empty

        self._ensure_combined_capacity(total)
        r_all = self._combined_r[:total]
        v_all = self._combined_v[:total]

        sat_n = self._sat.size
        deb_n = self._deb.size

        if sat_n:
            r_all[:sat_n] = self._sat.r_active
            v_all[:sat_n] = self._sat.v_active
        if deb_n:
            r_all[sat_n : sat_n + deb_n] = self._deb.r_active
            v_all[sat_n : sat_n + deb_n] = self._deb.v_active

        r_next, v_next = rk4_step_many(r_all, v_all, dt, workspace=self._rk4_ws_sat)

        if sat_n:
            self._sat.r[:sat_n] = r_next[:sat_n]
            self._sat.v[:sat_n] = v_next[:sat_n]
        if deb_n:
            self._deb.r[:deb_n] = r_next[sat_n : sat_n + deb_n]
            self._deb.v[:deb_n] = v_next[sat_n : sat_n + deb_n]

        return r_next, v_next

    def _has_los_for_sat_index(self, sat_idx: int) -> bool:
        """Return True if satellite at index has LOS to any ground station."""
        if not self._ground_stations:
            return True
        if sat_idx < 0 or sat_idx >= self._sat.size:
            return False

        r = self._sat.r[sat_idx].astype(np.float64, copy=False)
        return self._has_los_for_position(r)

    def _has_los_for_position(self, r_km: np.ndarray) -> bool:
        """Check LOS from any ground station using elevation-angle criterion.

        Approximate Earth as spherical and treat ECI as Earth-fixed for this
        purpose, which is sufficient for communication-window logic in this
        engine.
        """
        r = np.asarray(r_km, dtype=np.float64)
        if r.shape != (3,):
            raise ValueError("r_km must be length-3 vector")

        # Earth radius in km (spherical approximation).
        R_EARTH_KM = 6378.137
        r_norm = np.linalg.norm(r)
        if not np.isfinite(r_norm) or r_norm <= 0.0:
            return False

        for gs in self._ground_stations:
            cos_lat = np.cos(gs.lat_rad)
            sin_lat = np.sin(gs.lat_rad)
            cos_lon = np.cos(gs.lon_rad)
            sin_lon = np.sin(gs.lon_rad)
            # Station position on Earth's surface.
            s = np.array(
                [
                    cos_lat * cos_lon,
                    cos_lat * sin_lon,
                    sin_lat,
                ],
                dtype=np.float64,
            )
            r_station = R_EARTH_KM * s
            d = r - r_station
            d_norm = np.linalg.norm(d)
            if not np.isfinite(d_norm) or d_norm <= 0.0:
                continue

            # Elevation angle is the angle between LOS and local zenith.
            # sin(el) = (d · s) / |d|
            sin_el = float(np.dot(d, s) / d_norm)
            sin_el = float(np.clip(sin_el, -1.0, 1.0))
            el = float(np.arcsin(sin_el))
            if el >= gs.min_elev_rad:
                return True

        return False

    def _execute_maneuvers(self, due: list[ScheduledManeuver]) -> int:
        if not due or self._sat.size == 0:
            return 0

        # Keep the latest burn per object in this tick to avoid duplicate index writes.
        latest_by_id: dict[str, ScheduledManeuver] = {}
        for m in due:
            latest_by_id[m.object_id] = m

        sat_indices: list[int] = []
        dv_rows: list[np.ndarray] = []
        requires_los_flags: list[bool] = []
        for object_id, m in latest_by_id.items():
            slot = self.id_to_index.get(object_id)
            if slot is None or slot[0] != "SATELLITE":
                continue

            sat_idx = slot[1]

            # Enforce LOS constraints at execution time for maneuvers that
            # require ground contact.
            if m.requires_los and self.config.enable_comm_constraints and self._ground_stations:
                if not self._has_los_for_sat_index(sat_idx):
                    continue

            sat_indices.append(sat_idx)
            dv_rows.append(m.delta_v_rtn_km_s)
            requires_los_flags.append(m.requires_los)

        if not sat_indices:
            return 0

        idx = np.asarray(sat_indices, dtype=np.int64)
        dv_rtn = np.stack(dv_rows, axis=0).astype(np.float64, copy=False)

        # Pre-validate fuel sufficiency using the rocket equation so we can
        # cleanly skip infeasible burns instead of relying on the batch call
        # to silently reject them.
        current_mass = self._sat.mass[idx].astype(np.float64, copy=False)
        current_fuel = self._sat.fuel[idx].astype(np.float64, copy=False)
        cfg = self._maneuver_cfg
        ve = float(cfg.isp_s) * float(cfg.g0_m_s2)

        # Maneuvers are planned in RTN and converted to ECI at execution time.
        r_now = self._sat.r[idx].astype(np.float64, copy=False)
        v_now = self._sat.v[idx].astype(np.float64, copy=False)
        dv_eci_full = rtn_to_eci_many(dv_rtn, r_now, v_now)

        dv_mag_km_s = np.linalg.norm(dv_eci_full, axis=1)
        dv_mag_m_s = dv_mag_km_s * 1000.0
        with np.errstate(over="ignore", invalid="ignore"):
            dm = current_mass * (1.0 - np.exp(-dv_mag_m_s / ve))

        feasible = (
            np.isfinite(dm)
            & (dm >= 0.0)
            & (dm <= current_fuel + 1e-12)
        )

        if not np.any(feasible):
            return 0

        ok_idx = idx[feasible]
        ok_dv_eci = dv_eci_full[feasible]

        applied = apply_burn_batch(
            v_km_s=self._sat.v,
            mass_kg=self._sat.mass,
            fuel_kg=self._sat.fuel,
            sat_indices=ok_idx,
            delta_v_km_s=ok_dv_eci,
            cfg=self._maneuver_cfg,
        )
        if applied > 0:
            self._update_eol_after_burn(ok_idx)
            now = self.current_time_s
            for sat_idx in ok_idx:
                object_id = self._sat.ids[int(sat_idx)]
                self._last_burn_epoch_s[object_id] = now
        return applied

    def _plan_autonomous_avoidance(self, conjunctions: list[dict[str, object]]) -> list[dict[str, object]]:
        """Plan and schedule evasion + recovery burns from conjunction warnings.

        Strategy:
        - Prefer transverse (T) burn to phase-shift along-track timing.
        - Use radial (R) assist only if T-only burn cannot reach the target miss.
        - Avoid normal (N) unless unavoidable; currently left at 0 unless no other option.
        """
        if not conjunctions:
            return []

        safe_miss = float(self.config.auto_avoidance_safe_miss_km)
        max_dv = float(self.config.auto_avoidance_max_dv_km_s)
        cooldown = float(self.config.auto_avoidance_cooldown_s)
        min_tca = float(self.config.auto_avoidance_min_tca_s)
        margin = float(self.config.auto_avoidance_margin_factor)

        planned: list[dict[str, object]] = []
        planned_for_object: set[str] = set()

        for conj in conjunctions:
            miss = float(conj.get("miss_distance_km", 0.0))
            if miss >= safe_miss:
                continue

            id_a = str(conj.get("object_a", ""))
            id_b = str(conj.get("object_b", ""))
            if not id_a or not id_b:
                continue

            target_id = self._choose_maneuver_target(id_a, id_b)
            if target_id is None or target_id in planned_for_object:
                continue

            now = self.current_time_s
            if now < self._cooldown_until_s.get(target_id, 0.0):
                continue

            tca_s = max(float(conj.get("tca_s", 0.0)), 0.0)
            t_eff = max(tca_s, min_tca)

            target_state = self._state_by_id(target_id)
            other_id = id_b if target_id == id_a else id_a
            other_state = self._state_by_id(other_id)
            if target_state is None or other_state is None:
                continue

            r_tgt, v_tgt, _ = target_state
            r_oth, _, _ = other_state

            R, T, N = rtn_basis_many(r_tgt[None, :], v_tgt[None, :])
            r_rel = (r_oth - r_tgt).astype(np.float64, copy=False)
            s_rel_t = float(np.dot(r_rel, T[0]))
            s_rel_r = float(np.dot(r_rel, R[0]))

            needed = max(0.0, safe_miss - miss) * margin
            dv_t_mag = min(max_dv, needed / t_eff)
            if dv_t_mag <= 0.0:
                continue

            sign_t = -1.0 if s_rel_t >= 0.0 else 1.0
            dv_r = 0.0
            dv_t = sign_t * dv_t_mag
            dv_n = 0.0

            # If T-only cannot reach target miss, spend remaining dv budget on radial.
            achieved = abs(dv_t_mag) * t_eff
            if achieved < needed:
                rem_budget = max(0.0, max_dv * max_dv - dv_t * dv_t)
                if rem_budget > 0.0:
                    dv_r_mag = min(np.sqrt(rem_budget), (needed - achieved) / t_eff)
                    sign_r = -1.0 if s_rel_r >= 0.0 else 1.0
                    dv_r = sign_r * float(dv_r_mag)

            dv_vec = np.array([dv_r, dv_t, dv_n], dtype=np.float64)
            dv_mag = float(np.linalg.norm(dv_vec))
            if dv_mag <= 0.0 or dv_mag > max_dv + 1e-12:
                continue

            evasion_epoch = now + float(self.config.scheduler_latency_s)
            recovery_epoch = max(evasion_epoch + cooldown, now + tca_s + cooldown)
            recovery_dv = -dv_vec

            self._scheduler.schedule(
                ScheduledManeuver(
                    object_id=target_id,
                    epoch_s=evasion_epoch,
                    delta_v_rtn_km_s=dv_vec,
                    requires_los=False,
                )
            )
            self._scheduler.schedule(
                ScheduledManeuver(
                    object_id=target_id,
                    epoch_s=recovery_epoch,
                    delta_v_rtn_km_s=recovery_dv,
                    requires_los=False,
                )
            )

            self._cooldown_until_s[target_id] = recovery_epoch + cooldown
            planned_for_object.add(target_id)
            planned.append(
                {
                    "object_id": target_id,
                    "for_conjunction_with": other_id,
                    "target_safe_miss_km": safe_miss,
                    "estimated_pre_miss_km": miss,
                    "evasion_burn": {
                        "epoch_s": evasion_epoch,
                        "delta_v_rtn_km_s": [float(dv_vec[0]), float(dv_vec[1]), float(dv_vec[2])],
                    },
                    "recovery_burn": {
                        "epoch_s": recovery_epoch,
                        "delta_v_rtn_km_s": [float(recovery_dv[0]), float(recovery_dv[1]), float(recovery_dv[2])],
                    },
                }
            )

        return planned

    def _choose_maneuver_target(self, id_a: str, id_b: str) -> str | None:
        slot_a = self.id_to_index.get(id_a)
        slot_b = self.id_to_index.get(id_b)
        if slot_a is None or slot_b is None:
            return None

        is_sat_a = slot_a[0] == "SATELLITE"
        is_sat_b = slot_b[0] == "SATELLITE"
        if is_sat_a and not is_sat_b:
            return id_a
        if is_sat_b and not is_sat_a:
            return id_b
        if not is_sat_a and not is_sat_b:
            return None

        # If both are satellites, pick higher-fuel spacecraft to minimize mission risk.
        fuel_a = float(self._sat.fuel[slot_a[1]])
        fuel_b = float(self._sat.fuel[slot_b[1]])
        return id_a if fuel_a >= fuel_b else id_b

    def _state_by_id(self, object_id: str) -> tuple[np.ndarray, np.ndarray, ObjectType] | None:
        slot = self.id_to_index.get(object_id)
        if slot is None:
            return None

        pop, idx = slot
        if pop == "SATELLITE":
            return self._sat.r[idx], self._sat.v[idx], pop
        return self._deb.r[idx], self._deb.v[idx], pop

    def _combined_state(self) -> tuple[list[str], np.ndarray, np.ndarray]:
        total = self.object_count
        if total == 0:
            empty = np.empty((0, 3), dtype=self._state_dtype)
            return [], empty, empty

        ids = self._sat.ids + self._deb.ids
        self._ensure_combined_capacity(total)
        pos = self._combined_r[:total]
        vel = self._combined_v[:total]

        sat_n = self._sat.size
        deb_n = self._deb.size
        if sat_n:
            pos[:sat_n] = self._sat.r_active
            vel[:sat_n] = self._sat.v_active
        if deb_n:
            pos[sat_n : sat_n + deb_n] = self._deb.r_active
            vel[sat_n : sat_n + deb_n] = self._deb.v_active

        return ids, pos, vel

    def _parse_record(self, raw: object) -> _ObjectRecord:
        if not isinstance(raw, dict):
            raise ValueError("object record must be a dictionary")

        object_id = str(raw.get("id", "")).strip()
        if not object_id:
            raise ValueError("object id is required")

        raw_type = str(raw.get("type", "SATELLITE")).upper().strip()
        if raw_type not in ("SATELLITE", "DEBRIS"):
            raise ValueError("type must be SATELLITE or DEBRIS")
        object_type: ObjectType = raw_type  # type: ignore[assignment]

        r = as_vec3_array(raw.get("r_km"), "r_km").astype(self._state_dtype, copy=False)
        v = as_vec3_array(raw.get("v_km_s"), "v_km_s").astype(self._state_dtype, copy=False)

        mass = self._state_dtype.type(raw.get("mass_kg", 550.0))
        if mass <= 0.0:
            raise ValueError("mass_kg must be > 0")

        fuel: float | None
        if object_type == "SATELLITE":
            fv = raw.get("fuel_kg", 50.0)
            fuel = float(self._state_dtype.type(50.0 if fv is None else fv))
            if fuel < 0.0:
                raise ValueError("fuel_kg must be >= 0 for satellites")
        else:
            fuel = None

        return _ObjectRecord(
            object_id=object_id,
            object_type=object_type,
            r=r,
            v=v,
            mass=mass,
            fuel=fuel,
        )

    def _clear_satellite_metadata(self, object_id: str) -> None:
        """Remove all per-satellite auxiliary state for a given id."""
        self._nominal_slots_r.pop(object_id, None)
        self._sk_uptime_s.pop(object_id, None)
        self._sk_outage_s.pop(object_id, None)
        self._sk_status.pop(object_id, None)
        self._sk_last_deviation_km.pop(object_id, None)
        self._sk_recovery_pending.discard(object_id)
        self._initial_fuel_kg.pop(object_id, None)
        self._eol_state.pop(object_id, None)
        self._eol_graveyard_epoch_s.pop(object_id, None)

    def _store_for(self, object_type: ObjectType) -> _PopulationStore:
        return self._sat if object_type == "SATELLITE" else self._deb

    def _rebuild_global_index(self) -> None:
        self.id_to_index.clear()
        for i, object_id in enumerate(self._sat.ids):
            self.id_to_index[object_id] = ("SATELLITE", i)
        for i, object_id in enumerate(self._deb.ids):
            self.id_to_index[object_id] = ("DEBRIS", i)

    def _ensure_combined_capacity(self, target_size: int) -> None:
        if target_size <= self._combined_capacity:
            return

        new_capacity = max(1, self._combined_capacity)
        while new_capacity < target_size:
            new_capacity *= 2

        self._combined_r = np.empty((new_capacity, 3), dtype=self._state_dtype)
        self._combined_v = np.empty((new_capacity, 3), dtype=self._state_dtype)
        self._combined_capacity = new_capacity

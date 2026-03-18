from __future__ import annotations

import base64
import os
import zlib
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import numpy as np

from .collision import CollisionConfig, detect_collisions
from .config import configure_logging, load_simulation_config
from .integrator import rk4_many
from .maneuver import Maneuver
from .models import HealthResponse, SpaceObject, SpaceObjectType
from .scheduler import execute as execute_maneuvers
from .store import (
    OBJECTS,
    add_or_update,
    export_state_vectors,
    get_object_by_id,
    import_state_vectors,
    schedule_maneuver,
 )


class TelemetryObjectIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["SATELLITE", "DEBRIS"] = "SATELLITE"
    r_km: list[float] = Field(min_length=3, max_length=3)
    v_km_s: list[float] = Field(min_length=3, max_length=3)
    mass_kg: float = Field(default=550.0, gt=0.0)
    fuel_kg: float | None = Field(default=None, ge=0.0)


class TelemetryIn(BaseModel):
    objects: list[TelemetryObjectIn] = Field(min_length=1)


class ManeuverScheduleIn(BaseModel):
    object_id: str = Field(min_length=1, max_length=128)
    delta_v_km_s: list[float] = Field(min_length=3, max_length=3)


class SimulateStepIn(BaseModel):
    step_seconds: float = Field(gt=0.0)


class SimulateStepOut(BaseModel):
    collisions_detected: list[tuple[str, str]]
    maneuvers_executed: int


class VisualizationSnapshotOut(BaseModel):
    timestamp_s: float
    # satellites as compact rows: [id, lat_deg, lon_deg, fuel_kg, status]
    satellites: list[list[object]]
    debris: dict[str, object]


def create_app() -> FastAPI:
    logger = configure_logging()
    sim_cfg = load_simulation_config()

    app = FastAPI(
        title="Autonomous Constellation Manager (ACM)",
        version="0.1.0",
        description="Backend for orbital simulation, collision avoidance, and maneuver planning.",
    )

    # Simple in-process simulation clock (seconds).
    sim_time_s: float = 0.0

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/api/telemetry")
    def post_telemetry(body: TelemetryIn) -> dict[str, int]:
        """Ingest telemetry (r, v) and upsert objects into the global store."""
        t0 = perf_counter()
        upserted = 0
        for o in body.objects:
            obj_type = SpaceObjectType(o.type)
            fuel = None
            if obj_type == SpaceObjectType.SATELLITE:
                fuel = 50.0 if o.fuel_kg is None else float(o.fuel_kg)
            domain = SpaceObject(
                id=o.id,
                type=obj_type,
                r=np.asarray(o.r_km, dtype=np.float64),
                v=np.asarray(o.v_km_s, dtype=np.float64),
                mass=float(o.mass_kg),
                fuel=fuel,
            )
            add_or_update(domain)
            upserted += 1
        logger.info(
            "telemetry_upsert completed upserted=%d total=%d elapsed_ms=%.2f",
            upserted,
            len(OBJECTS),
            (perf_counter() - t0) * 1000.0,
        )
        return {"objects_upserted": upserted, "objects_total": len(OBJECTS)}

    @app.post("/api/maneuver/schedule")
    def schedule(body: ManeuverScheduleIn) -> dict[str, float]:
        """Schedule a maneuver with a fixed 10-second latency."""
        nonlocal sim_time_s
        obj = get_object_by_id(body.object_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="object not found")

        dv = np.asarray(body.delta_v_km_s, dtype=np.float64)
        if dv.shape != (3,):
            raise HTTPException(status_code=400, detail="delta_v_km_s must be length 3")

        burn_time = sim_time_s + sim_cfg.integration_tick_s
        schedule_maneuver(
            Maneuver(object_id=body.object_id, epoch_s=burn_time, delta_v_km_s=dv)
        )
        logger.debug(
            "maneuver_scheduled object_id=%s burn_time_s=%.3f dv=%.6f,%.6f,%.6f",
            body.object_id,
            burn_time,
            float(dv[0]),
            float(dv[1]),
            float(dv[2]),
        )
        return {"scheduled_for_time_s": burn_time}

    @app.post("/api/simulate/step", response_model=SimulateStepOut)
    def simulate_step(body: SimulateStepIn) -> SimulateStepOut:
        """Advance the simulation, detect collisions, and execute maneuvers."""
        nonlocal sim_time_s

        start = perf_counter()
        step_seconds = float(body.step_seconds)
        dt = float(sim_cfg.integration_tick_s)
        if step_seconds <= 0.0:
            raise HTTPException(status_code=400, detail="step_seconds must be > 0")

        collisions: set[tuple[str, str]] = set()
        executed_total = 0

        collision_cfg = CollisionConfig(
            collision_distance_km=sim_cfg.collision_distance_km,
            block_size=sim_cfg.collision_block_size,
            max_pairs=sim_cfg.collision_max_pairs,
            prefer_kdtree=sim_cfg.prefer_kdtree,
        )

        # Integrate in 10s ticks (last partial tick is ignored by requirement).
        ticks = int(step_seconds // dt)
        if ticks > sim_cfg.max_step_ticks:
            raise HTTPException(
                status_code=400,
                detail=f"requested ticks ({ticks}) exceeds ACM_MAX_STEP_TICKS ({sim_cfg.max_step_ticks})",
            )

        for _ in range(ticks):
            # Vectorized propagation keeps Python-level loops out of the hot path.
            objs, r, v = export_state_vectors()
            if objs:
                r_next, v_next = rk4_many(r, v, dt)
                import_state_vectors(objs, r_next, v_next)

            sim_time_s += dt

            # Collisions.
            for a, b in detect_collisions(objs, collision_cfg):
                # normalize ordering for stable uniqueness
                collisions.add((a, b) if a < b else (b, a))

            # Maneuvers.
            executed_total += int(execute_maneuvers(sim_time_s))

        logger.info(
            "simulate_step completed step_seconds=%.3f ticks=%d objects=%d collisions=%d maneuvers=%d elapsed_ms=%.2f",
            step_seconds,
            ticks,
            len(OBJECTS),
            len(collisions),
            executed_total,
            (perf_counter() - start) * 1000.0,
        )

        return SimulateStepOut(
            collisions_detected=sorted(collisions),
            maneuvers_executed=executed_total,
        )

    @app.get("/api/visualization/snapshot", response_model=VisualizationSnapshotOut)
    def visualization_snapshot() -> VisualizationSnapshotOut:
        """Return a compact snapshot for visualization clients."""
        nonlocal sim_time_s

        objs = list(OBJECTS.values())
        if not objs:
            return VisualizationSnapshotOut(
                timestamp_s=sim_time_s,
                satellites=[],
                debris={
                    "count": 0,
                    "encoding": "zlib+base64",
                    "dtype": "float32",
                    "shape": [0, 3],
                    "data": "",
                },
            )

        # Split satellites/debris.
        sat = [o for o in objs if o.type == SpaceObjectType.SATELLITE]
        deb = [o for o in objs if o.type == SpaceObjectType.DEBRIS]

        # Satellites: vectorized lat/lon from Earth-fixed position.
        satellites_out: list[list[object]] = []
        if sat:
            r = np.stack([o.r for o in sat], axis=0).astype(np.float64, copy=False)  # (Ns,3)
            x = r[:, 0]
            y = r[:, 1]
            z = r[:, 2]
            rho = np.sqrt(x * x + y * y + z * z)
            # Spherical lat/lon (deg). (ECI treated as Earth-fixed here.)
            lat = np.degrees(np.arcsin(np.clip(z / rho, -1.0, 1.0)))
            lon = np.degrees(np.arctan2(y, x))

            for i, o in enumerate(sat):
                fuel = float(o.fuel) if o.fuel is not None else 0.0
                status = "OK" if fuel > 0.0 else "NO_FUEL"
                satellites_out.append(
                    [o.id, float(lat[i]), float(lon[i]), fuel, status]
                )

        # Debris cloud: compressed float32 positions.
        if deb:
            pos = np.stack([o.r for o in deb], axis=0).astype(np.float32, copy=False)  # (Nd,3)
            raw = pos.tobytes(order="C")
            comp = zlib.compress(raw, level=6)
            data_b64 = base64.b64encode(comp).decode("ascii")
            debris_out = {
                "count": int(pos.shape[0]),
                "encoding": "zlib+base64",
                "dtype": "float32",
                "shape": [int(pos.shape[0]), 3],
                "data": data_b64,
            }
        else:
            debris_out = {
                "count": 0,
                "encoding": "zlib+base64",
                "dtype": "float32",
                "shape": [0, 3],
                "data": "",
            }

        return VisualizationSnapshotOut(
            timestamp_s=sim_time_s,
            satellites=satellites_out,
            debris=debris_out,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("ACM_HOST", "0.0.0.0")
    port = int(os.getenv("ACM_PORT", "8000"))
    configure_logging().info("starting acm host=%s port=%d", host, port)
    uvicorn.run("acm.main:app", host=host, port=port, reload=False)


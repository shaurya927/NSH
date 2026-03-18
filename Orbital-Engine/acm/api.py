from __future__ import annotations

import asyncio
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
from engine import ACMEngine


# Global engine instance reused by all requests.
ENGINE = ACMEngine()
_ENGINE_LOCK = RLock()


class TelemetryIn(BaseModel):
    objects: list[dict[str, Any]] = Field(min_length=1)


class GroundStationIn(BaseModel):
    stations: list[dict[str, Any]] = Field(min_length=1)


class ManeuverScheduleIn(BaseModel):
    object_id: str = Field(min_length=1, max_length=128)
    delta_v_rtn_km_s: list[float] | None = Field(default=None, min_length=3, max_length=3)
    # Backward compatibility: interpreted as RTN if provided.
    delta_v_km_s: list[float] | None = Field(default=None, min_length=3, max_length=3)
    epoch_s: float | None = None

    @model_validator(mode="after")
    def _validate_dv_present(self) -> "ManeuverScheduleIn":
        if self.delta_v_rtn_km_s is None and self.delta_v_km_s is None:
            raise ValueError("delta_v_rtn_km_s is required")
        return self


class SimulateStepIn(BaseModel):
    step_seconds: float = Field(gt=0.0)


async def _run_engine(callable_obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Run engine calls in a worker thread for async-compatible endpoints."""

    def _wrapped() -> Any:
        # The engine mutates shared state, so serialize access.
        with _ENGINE_LOCK:
            return callable_obj(*args, **kwargs)

    return await asyncio.to_thread(_wrapped)


app = FastAPI(
    title="ACM Engine Integration API",
    version="1.0.0",
    description="Thin API layer over ACMEngine.",
)


@app.post("/api/telemetry")
async def post_telemetry(body: TelemetryIn) -> dict[str, Any]:
    try:
        payload = body.model_dump()
        return await _run_engine(ENGINE.ingest_telemetry, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ground-stations")
async def post_ground_stations(body: GroundStationIn) -> dict[str, Any]:
    """Load or replace the ground station dataset used for LOS checks."""
    try:
        payload = body.model_dump()
        return await _run_engine(ENGINE.load_ground_stations, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/maneuver/schedule")
async def schedule_maneuver(body: ManeuverScheduleIn) -> dict[str, Any]:
    try:
        payload = body.model_dump()
        return await _run_engine(ENGINE.schedule_maneuver, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/simulate/step")
async def simulate_step(body: SimulateStepIn) -> dict[str, Any]:
    try:
        return await _run_engine(ENGINE.step_simulation, body.step_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/visualization/snapshot")
async def visualization_snapshot() -> dict[str, Any]:
    try:
        return await _run_engine(ENGINE.get_snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

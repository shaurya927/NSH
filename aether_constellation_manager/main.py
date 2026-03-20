# AETHER Constellation Manager API

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone


# Import the orbital engine (SimulationEngine, State, Vec3)
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../Orbital-Engine')))
from Physics.vector import Vec3
from Physics.state import State
from Simulation.engine import SimulationEngine

import uvicorn


# ==========================================
# 1. INITIALIZE API & SECURITY (CORS)
# ==========================================
app = FastAPI(title="AETHER Constellation Manager API")

# This allows your frontend teammate's web app to fetch data without errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. INTERNAL MEMORY (Global State)
# ==========================================

# Global state and simulation engine
global_state: Dict[str, Any] = {
    "satellites": {},
    "debris": {},
    "last_update": None
}

# Initialize the simulation engine
sim_engine = SimulationEngine()

# Helper to sync global_state to sim_engine
def sync_state_to_engine():
    sim_engine.objects.clear()
    for sat_id, sat in global_state["satellites"].items():
        r = Vec3(sat["r"].x, sat["r"].y, sat["r"].z)
        v = Vec3(sat["v"].x, sat["v"].y, sat["v"].z)
        sim_engine.add_object(type("SatObj", (), {"name": sat_id, "state": State(r, v)})())
    for deb_id, deb in global_state["debris"].items():
        r = Vec3(deb["r"].x, deb["r"].y, deb["r"].z)
        v = Vec3(deb["v"].x, deb["v"].y, deb["v"].z)
        sim_engine.add_object(type("DebObj", (), {"name": deb_id, "state": State(r, v)})())

# Helper to update global_state from sim_engine
def sync_engine_to_state():
    for obj in sim_engine.objects:
        obj_id = getattr(obj, "name", None)
        if obj_id is None:
            continue
        state = obj.state
        entry = {"r": state.r, "v": state.v}
        if obj_id in global_state["satellites"]:
            global_state["satellites"][obj_id] = entry
        elif obj_id in global_state["debris"]:
            global_state["debris"][obj_id] = entry

# ==========================================
# 3. DATA MODELS (Strict Hackathon Formats)
# ==========================================
class Vector3D(BaseModel):
    x: float
    y: float
    z: float

class SpaceObject(BaseModel):
    id: str
    type: str  # "SATELLITE" or "DEBRIS"
    r: Vector3D 
    v: Vector3D 

class TelemetryPayload(BaseModel):
    timestamp: datetime
    objects: List[SpaceObject]

class ManeuverBurn(BaseModel):
    burn_id: str
    burnTime: datetime
    deltaV_vector: Vector3D

class ManeuverSchedulePayload(BaseModel):
    satelliteId: str
    maneuver_sequence: List[ManeuverBurn]

class SimulateStepPayload(BaseModel):
    step_seconds: int

# ==========================================
# 4. THE 4 REQUIRED API ENDPOINTS
# ==========================================

# --- API #1: Telemetry Ingestion ---
@app.post("/api/telemetry")
async def ingest_telemetry(payload: TelemetryPayload):
    processed = 0
    global_state["last_update"] = payload.timestamp
    
    for obj in payload.objects:
        if obj.type == "SATELLITE":
            global_state["satellites"][obj.id] = {"r": obj.r, "v": obj.v}
        elif obj.type == "DEBRIS":
            global_state["debris"][obj.id] = {"r": obj.r, "v": obj.v}
        processed += 1
        
    return {
        "status": "ACK",
        "processed_count": processed,
        "active_cdm_warnings": 0
    }

# --- API #2: Maneuver Scheduling ---
@app.post("/api/maneuver/schedule", status_code=status.HTTP_202_ACCEPTED)
async def schedule_maneuver(payload: ManeuverSchedulePayload):
    return {
        "status": "SCHEDULED",
        "validation": {
            "ground_station_los": True,
            "sufficient_fuel": True,
            "projected_mass_remaining_kg": 548.12
        }
    }

# --- API #3: Simulation Fast-Forward (Tick) ---

@app.post("/api/simulate/step")
async def simulate_step(payload: SimulateStepPayload):
    current_time = global_state.get("last_update")
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    new_time = current_time + timedelta(seconds=payload.step_seconds)
    global_state["last_update"] = new_time

    # Sync state to engine, step, then sync back
    sync_state_to_engine()
    
    total_seconds = payload.step_seconds
    if total_seconds != 0:
        step_size = 60 if total_seconds > 0 else -60
        steps = abs(total_seconds) // abs(step_size)
        remainder = total_seconds % step_size
        
        for _ in range(steps):
            sim_engine.step(step_size)
        if remainder != 0:
            sim_engine.step(remainder)

    sync_engine_to_state()

    return {
        "status": "STEP_COMPLETE",
        "new_timestamp": new_time.isoformat() + "Z",
        "collisions_detected": 0,  # Placeholder: add collision logic if available
        "maneuvers_executed": 0    # Placeholder: add maneuver logic if available
    }

# --- API #4: Clear Engine State ---
@app.post("/api/clear")
async def clear_state():
    global_state["satellites"].clear()
    global_state["debris"].clear()
    sim_engine.objects.clear()
    return {"status": "CLEARED"}

# --- API #5: Visualization Snapshot ---

@app.get("/api/visualization/snapshot")
async def visualization_snapshot():
    current_time = global_state.get("last_update")
    timestamp_str = current_time.isoformat() + "Z" if current_time else "2026-03-12T08:00:00.000Z"

    # Sync state to engine to ensure latest positions
    sync_state_to_engine()
    satellites = []
    debris_cloud = []
    for obj in sim_engine.objects:
        obj_id = getattr(obj, "name", None)
        state = obj.state
        # Convert ECI to lat/lon/alt (simple spherical, not accounting for Earth rotation)
        r = state.r
        x, y, z = r.x, r.y, r.z
        import math
        rho = math.sqrt(x*x + y*y + z*z)
        lat = math.degrees(math.asin(z / rho))
        lon = math.degrees(math.atan2(y, x))
        alt = rho - 6378.137  # Earth radius in km
        if obj_id in global_state["satellites"]:
            satellites.append({
                "id": obj_id,
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "fuel_kg": 50.0,  # Placeholder, update if you track fuel
                "status": "NOMINAL"  # Placeholder, update if you track status
            })
        elif obj_id in global_state["debris"]:
            debris_cloud.append([obj_id, lat, lon, alt])

    return {
        "timestamp": timestamp_str,
        "satellites": satellites,
        "debris_cloud": debris_cloud
    }

# --- Bonus: Root Check ---
@app.get("/")
def read_root():
    return {"message": "AETHER Constellation Manager API is fully online!"}

# ==========================================
# 5. EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
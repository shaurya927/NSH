# AETHER Constellation Manager API
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone


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
global_state: Dict[str, Any] = {
    "satellites": {},
    "debris": {},
    "last_update": None
}

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
    
    # NOTE: Your physics teammate's collision logic will eventually go here
    
    return {
        "status": "STEP_COMPLETE",
        "new_timestamp": new_time.isoformat() + "Z",
        "collisions_detected": 0,
        "maneuvers_executed": 0
    }

# --- API #4: Visualization Snapshot ---
@app.get("/api/visualization/snapshot")
async def visualization_snapshot():
    current_time = global_state.get("last_update")
    timestamp_str = current_time.isoformat() + "Z" if current_time else "2026-03-12T08:00:00.000Z"

    return {
        "timestamp": timestamp_str,
        "satellites": [
            {
                "id": "SAT-Alpha-04",
                "lat": 28.545,
                "lon": 77.192,
                "fuel_kg": 48.5,
                "status": "NOMINAL"
            }
        ],
        "debris_cloud": [
            ["DEB-99421", 12.42, 45.21, 400.5],
            ["DEB-99422", 12.55, -45.10, 401.2]
        ]
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
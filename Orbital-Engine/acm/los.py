from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .models import SpaceObject
from .physics import RE_KM


@dataclass(frozen=True, slots=True)
class GroundStation:
    """Simple ground station model (spherical Earth).

    lat_deg: geodetic latitude in degrees (treated as geocentric for spherical Earth)
    lon_deg: longitude in degrees, east-positive
    """

    station_id: str
    lat_deg: float
    lon_deg: float

    def ecef_position_km(self, earth_radius_km: float = RE_KM) -> np.ndarray:
        """Return station position in ECEF (km) assuming spherical Earth."""
        lat = np.deg2rad(float(self.lat_deg))
        lon = np.deg2rad(float(self.lon_deg))
        clat = float(np.cos(lat))
        slat = float(np.sin(lat))
        clon = float(np.cos(lon))
        slon = float(np.sin(lon))
        r = float(earth_radius_km)
        return np.array([r * clat * clon, r * clat * slon, r * slat], dtype=np.float64)


def load_ground_stations_json(path: str | Path) -> list[GroundStation]:
    """Load ground stations from a JSON file.

    Expected formats:
    - A list of objects: [{"station_id":"GS1","lat_deg":..,"lon_deg":..}, ...]
    - Or wrapped: {"stations":[ ... ]}
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    items: Any
    if isinstance(data, dict) and "stations" in data:
        items = data["stations"]
    else:
        items = data
    if not isinstance(items, list):
        raise ValueError("Invalid ground stations JSON: expected a list or {'stations': [...]} ")

    out: list[GroundStation] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid station at index {i}: expected object")
        station_id = str(raw.get("station_id") or raw.get("id") or f"GS-{i}")
        lat = raw.get("lat_deg", raw.get("lat"))
        lon = raw.get("lon_deg", raw.get("lon"))
        if lat is None or lon is None:
            raise ValueError(f"Station {station_id!r} missing lat/lon")
        out.append(GroundStation(station_id=station_id, lat_deg=float(lat), lon_deg=float(lon)))
    return out


def eci_to_earth_fixed(r_eci_km: np.ndarray) -> np.ndarray:
    """Convert ECI position to Earth-fixed position.

    For now, this assumes the ECI frame is aligned with Earth-fixed (no rotation).
    A future upgrade can add Earth rotation using a sidereal time parameter.
    """
    r = np.asarray(r_eci_km, dtype=np.float64)
    if r.shape != (3,):
        raise ValueError("r_eci_km must be shape (3,)")
    return r


def elevation_angle_rad(r_sat_eci_km: np.ndarray, station: GroundStation) -> float:
    """Compute elevation angle (radians) from station to satellite.

    Uses spherical Earth geometry:
    - station zenith direction is along station position vector
    - elevation = asin( (rho · z_hat) / ||rho|| ), where rho = sat - station
    """
    r_sat = eci_to_earth_fixed(r_sat_eci_km)
    r_gs = station.ecef_position_km()
    rho = r_sat - r_gs
    rho_norm = float(np.linalg.norm(rho))
    if not np.isfinite(rho_norm) or rho_norm <= 0.0:
        return float("-inf")
    z_hat = r_gs / float(np.linalg.norm(r_gs))
    sin_el = float(np.dot(rho, z_hat)) / rho_norm
    # Numerical clamp
    sin_el = max(-1.0, min(1.0, sin_el))
    return float(np.arcsin(sin_el))


def has_line_of_sight(
    satellite: SpaceObject,
    ground_station: GroundStation,
    min_elevation_deg: float = 0.0,
) -> bool:
    """Return True if satellite is above the station's horizon.

    Args:
        satellite: space object with ECI position in km.
        ground_station: station lat/lon.
        min_elevation_deg: optional mask angle; default 0° (geometric LOS).
    """
    el = elevation_angle_rad(satellite.r, ground_station)
    return el >= np.deg2rad(float(min_elevation_deg))


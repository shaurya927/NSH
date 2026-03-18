// ============================================
// AETHER – Engine Proxy Service
// Forwards requests to Python ACMEngine API
// ============================================

import { SATELLITE_REGISTRY, DEBRIS_REGISTRY } from './engineSeeder';

const ENGINE_URL = process.env.ENGINE_URL || 'http://localhost:8000';

export interface EngineProxyResponse<T = any> {
  ok: boolean;
  status: number;
  data: T | null;
  error?: string;
}

async function engineFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<EngineProxyResponse<T>> {
  try {
    const url = `${ENGINE_URL}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      return { ok: false, status: res.status, data: null, error: text || `HTTP ${res.status}` };
    }

    const data = (await res.json()) as T;
    return { ok: true, status: res.status, data };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: err?.message || 'Engine unreachable',
    };
  }
}

// --- Telemetry Ingestion ---
export async function proxyTelemetry(objects: any[]): Promise<EngineProxyResponse> {
  return engineFetch('/api/telemetry', {
    method: 'POST',
    body: JSON.stringify({ objects }),
  });
}

// --- Maneuver Scheduling ---
export async function proxyManeuver(payload: {
  object_id: string;
  delta_v_rtn_km_s?: number[];
  delta_v_km_s?: number[];
  epoch_s?: number;
}): Promise<EngineProxyResponse> {
  return engineFetch('/api/maneuver/schedule', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- Simulation Step ---
export async function proxySimulateStep(stepSeconds: number): Promise<EngineProxyResponse> {
  return engineFetch('/api/simulate/step', {
    method: 'POST',
    body: JSON.stringify({ step_seconds: stepSeconds }),
  });
}

// --- Visualization Snapshot ---
export async function proxySnapshot(): Promise<EngineProxyResponse> {
  return engineFetch('/api/visualization/snapshot');
}

// --- Health Check ---
export async function proxyHealthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${ENGINE_URL}/docs`, { method: 'HEAD' });
    return res.ok || res.status === 200;
  } catch {
    return false;
  }
}

// --- Transform engine snapshot to frontend format ---
export function transformSnapshot(engineData: any) {
  const R_EARTH_KM = 6378.137;

  const satellites = (engineData.satellites || []).map((row: any) => {
    // Engine format: [id, lat, lon, fuel_kg, status]
    const [id, lat, lon, fuel, status] = Array.isArray(row)
      ? row
      : [row.id, row.lat, row.lon, row.fuel_kg, row.status];

    const meta = SATELLITE_REGISTRY[id];
    const fuelKg = typeof fuel === 'number' ? fuel : 0;
    const initialFuel = meta?.initialFuelKg ?? 50;
    const fuelPercent = Math.min(100, Math.round((fuelKg / initialFuel) * 100));

    // Map engine status to frontend status
    let mappedStatus: string;
    if (status === 'NOMINAL' || status === 'OK') {
      mappedStatus = fuelPercent < 20 ? 'warning' : 'nominal';
    } else if (status === 'OUT_OF_BOUNDS') {
      mappedStatus = 'warning';
    } else if (status === 'ALERT' || status === 'NO_FUEL') {
      mappedStatus = 'critical';
    } else {
      mappedStatus = 'nominal';
    }

    // Delta-specific override: Delta starts critical
    if (id === 'AETHER-Delta' && fuelPercent < 30) {
      mappedStatus = 'critical';
    }

    // Compute health from fuel and status
    let health: number;
    if (meta) {
      // Health degrades proportionally with fuel usage
      const fuelFraction = fuelKg / initialFuel;
      health = Math.max(10, Math.round(meta.baseHealth * (0.5 + 0.5 * fuelFraction)));
    } else {
      health = mappedStatus === 'critical' ? 45 : mappedStatus === 'warning' ? 78 : 95;
    }

    // Compute altitude from engine position data if available
    // For now estimate from lat/lon (engine gives lat/lon from ECI)
    const altitude = 400 + (lat ? Math.abs(lat) * 0.3 : 0);
    const vCirc = 7.67 - altitude * 0.001; // approximate circular velocity

    return {
      id,
      name: meta?.name ?? id,
      noradId: meta?.noradId ?? id,
      constellation: meta?.constellation ?? 'AETHER-Prime',
      status: mappedStatus,
      orbitType: meta?.orbitType ?? 'LEO',
      telemetry: {
        timestamp: new Date().toISOString(),
        position: { x: 0, y: 0, z: 0 },
        velocity: { vx: 0, vy: vCirc, vz: 0 },
        latitude: lat,
        longitude: lon,
        altitude,
        inclination: 51.6,
        eccentricity: 0.0001,
        period: 92.5,
      },
      fuelLevel: fuelPercent,
      health,
      lastContact: new Date().toISOString(),
    };
  });

  // Engine debris format: array of [id, lat, lon, alt_km] or compressed blob
  const debrisRaw = engineData.debris || [];
  let debris: any[];
  if (Array.isArray(debrisRaw) && debrisRaw.length > 0 && Array.isArray(debrisRaw[0])) {
    debris = debrisRaw.map((row: any) => {
      const [id, lat, lon, alt] = row;
      const meta = DEBRIS_REGISTRY[id];
      return {
        id,
        name: meta?.name ?? id,
        noradId: meta?.noradId ?? id,
        type: meta?.type ?? 'fragment',
        size: meta?.size ?? 'small',
        latitude: lat || 0,
        longitude: lon || 0,
        altitude: alt || 400,
        position: { x: 0, y: 0, z: 0 },
        velocity: { vx: -0.5 + Math.random(), vy: 7.3 + Math.random() * 0.2, vz: Math.random() * 0.2 - 0.1 },
        riskLevel: meta?.riskLevel ?? 'medium',
      };
    });
  } else if (typeof debrisRaw === 'object' && debrisRaw.count !== undefined) {
    // Compressed format – create placeholders using registry
    const regKeys = Object.keys(DEBRIS_REGISTRY);
    debris = Array.from({ length: Math.min(debrisRaw.count, 20) }, (_, i) => {
      const regId = regKeys[i % regKeys.length];
      const meta = DEBRIS_REGISTRY[regId];
      return {
        id: meta?.noradId ?? `DEB-${String(i + 1).padStart(5, '0')}`,
        name: meta?.name ?? `Debris Fragment ${i + 1}`,
        noradId: meta?.noradId ?? `DEB-${String(i + 1).padStart(5, '0')}`,
        type: meta?.type ?? 'fragment',
        size: meta?.size ?? 'small',
        position: { x: 6800 + Math.random() * 300, y: Math.random() * 200 - 100, z: Math.random() * 200 - 100 },
        velocity: { vx: 0, vy: 7.3, vz: 0 },
        riskLevel: meta?.riskLevel ?? 'medium',
      };
    });
  } else {
    debris = [];
  }

  return {
    satellites,
    debris,
    conjunctions: [] as any[],
    timestamp: new Date().toISOString(),
    simulationTime: engineData.timestamp_s || 0,
  };
}

// --- Transform engine conjunctions to frontend format ---
export function transformConjunctions(conjunctions: any[]) {
  if (!Array.isArray(conjunctions)) return [];

  return conjunctions.map((c: any, i: number) => {
    const riskMap: Record<string, string> = {
      CRITICAL: 'critical',
      MEDIUM: 'medium',
      LOW: 'low',
    };

    // Look up friendly names from registries
    const nameA = SATELLITE_REGISTRY[c.object_a]?.name
      ?? DEBRIS_REGISTRY[c.object_a]?.name
      ?? c.object_a;
    const nameB = SATELLITE_REGISTRY[c.object_b]?.name
      ?? DEBRIS_REGISTRY[c.object_b]?.name
      ?? c.object_b;

    // Estimate collision probability from miss distance
    const miss = c.miss_distance_km || 0;
    let probability: number;
    if (miss < 0.1) probability = 0.05;
    else if (miss < 0.5) probability = 0.01;
    else if (miss < 1.0) probability = 0.003;
    else if (miss < 3.0) probability = 0.0008;
    else probability = 0.0001;

    return {
      id: `conj-${String(i + 1).padStart(3, '0')}`,
      primaryObject: c.object_a,
      secondaryObject: c.object_b,
      primaryName: nameA,
      secondaryName: nameB,
      timeOfClosestApproach: new Date(Date.now() + (c.tca_s || 0) * 1000).toISOString(),
      missDistance: miss,
      probability,
      riskLevel: riskMap[c.risk_level] || 'low',
    };
  });
}

export { ENGINE_URL };

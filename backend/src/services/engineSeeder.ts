// ============================================
// AETHER – Engine Seeder
// Seeds initial constellation data into ACMEngine on startup
// ============================================

import { proxyTelemetry, proxyHealthCheck, ENGINE_URL } from './engineProxy';

/**
 * Satellite metadata registry — maps engine object IDs to rich display data
 * matching the original mock data properties.
 */
export const SATELLITE_REGISTRY: Record<string, {
  name: string;
  noradId: string;
  constellation: string;
  orbitType: string;
  baseHealth: number;
  initialFuelKg: number;
}> = {
  'AETHER-Alpha': {
    name: 'AETHER-Alpha',
    noradId: '55001',
    constellation: 'AETHER-Prime',
    orbitType: 'LEO',
    baseHealth: 95,
    initialFuelKg: 43.5,
  },
  'AETHER-Beta': {
    name: 'AETHER-Beta',
    noradId: '55002',
    constellation: 'AETHER-Prime',
    orbitType: 'LEO',
    baseHealth: 78,
    initialFuelKg: 21.0,
  },
  'AETHER-Gamma': {
    name: 'AETHER-Gamma',
    noradId: '55003',
    constellation: 'AETHER-Prime',
    orbitType: 'LEO',
    baseHealth: 99,
    initialFuelKg: 46.5,
  },
  'AETHER-Delta': {
    name: 'AETHER-Delta',
    noradId: '55004',
    constellation: 'AETHER-Prime',
    orbitType: 'LEO',
    baseHealth: 45,
    initialFuelKg: 6.0,
  },
  'AETHER-Epsilon': {
    name: 'AETHER-Epsilon',
    noradId: '55005',
    constellation: 'AETHER-Prime',
    orbitType: 'LEO',
    baseHealth: 91,
    initialFuelKg: 38.0,
  },
};

export const DEBRIS_REGISTRY: Record<string, {
  name: string;
  noradId: string;
  type: string;
  size: string;
  riskLevel: string;
}> = {
  'DEB-COSMOS-2251': {
    name: 'COSMOS-2251 Fragment',
    noradId: '34001',
    type: 'fragment',
    size: 'small',
    riskLevel: 'high',
  },
  'DEB-SL16-Body': {
    name: 'SL-16 Rocket Body',
    noradId: '22285',
    type: 'rocket_body',
    size: 'large',
    riskLevel: 'medium',
  },
  'DEB-Unknown-001': {
    name: 'Unknown Object',
    noradId: '99001',
    type: 'unknown',
    size: 'medium',
    riskLevel: 'low',
  },
  'DEB-Fengyun-1C': {
    name: 'Fengyun-1C Fragment',
    noradId: '31001',
    type: 'fragment',
    size: 'small',
    riskLevel: 'critical',
  },
};

const R_EARTH = 6378.137;
const MU = 398600.4418;

function latLonAltToECI(latDeg: number, lonDeg: number, altKm: number) {
  const r = R_EARTH + altKm;
  const latRad = (latDeg * Math.PI) / 180;
  const lonRad = (lonDeg * Math.PI) / 180;
  const x = r * Math.cos(latRad) * Math.cos(lonRad);
  const y = r * Math.cos(latRad) * Math.sin(lonRad);
  const z = r * Math.sin(latRad);
  return [x, y, z];
}

function circularVelocity(r_km: number[]) {
  const rMag = Math.sqrt(r_km[0] ** 2 + r_km[1] ** 2 + r_km[2] ** 2);
  const v = Math.sqrt(MU / rMag);
  const norm = rMag || 1;
  // Velocity perpendicular to position in orbital plane
  return [(-r_km[1] / norm) * v, (r_km[0] / norm) * v, 0];
}

/**
 * Build the full seed telemetry including satellites and debris.
 * Debris is placed NEAR satellites so the engine detects conjunctions.
 */
function buildSeedTelemetry() {
  const satellites = [
    { id: 'AETHER-Alpha', lat: 28.5, lon: -80.6, alt: 408 },
    { id: 'AETHER-Beta', lat: 35.2, lon: 120.4, alt: 415 },
    { id: 'AETHER-Gamma', lat: -12.8, lon: 45.3, alt: 402 },
    { id: 'AETHER-Delta', lat: 52.1, lon: -3.7, alt: 395 },
    { id: 'AETHER-Epsilon', lat: -33.9, lon: 151.2, alt: 420 },
  ];

  // Place debris NEAR satellites with slight offsets so conjunctions are detected
  // DEB-Fengyun-1C near AETHER-Alpha (critical risk)
  // DEB-COSMOS-2251 near AETHER-Beta (high risk)
  // DEB-SL16-Body near AETHER-Gamma (medium risk)
  // DEB-Unknown-001 near AETHER-Delta (low risk)
  const debris = [
    { id: 'DEB-Fengyun-1C', lat: 28.52, lon: -80.58, alt: 408.2 },  // ~3km from Alpha
    { id: 'DEB-COSMOS-2251', lat: 35.22, lon: 120.42, alt: 415.1 },  // ~3km from Beta
    { id: 'DEB-SL16-Body', lat: -12.78, lon: 45.32, alt: 402.3 },    // ~3km from Gamma
    { id: 'DEB-Unknown-001', lat: 52.12, lon: -3.68, alt: 395.5 },    // ~3km from Delta
  ];

  const objects: any[] = [];

  for (const sat of satellites) {
    const meta = SATELLITE_REGISTRY[sat.id];
    const r = latLonAltToECI(sat.lat, sat.lon, sat.alt);
    const v = circularVelocity(r);
    objects.push({
      id: sat.id,
      type: 'SATELLITE',
      r: { x: r[0], y: r[1], z: r[2] },
      v: { x: v[0], y: v[1], z: v[2] },
      mass_kg: 550.0,
      fuel_kg: meta?.initialFuelKg ?? 50.0,
    });
  }

  for (const deb of debris) {
    const r = latLonAltToECI(deb.lat, deb.lon, deb.alt);
    const v = circularVelocity(r);
    // Add slight velocity offset to create approach dynamics
    v[0] += 0.002 * (Math.random() - 0.5);
    v[1] += 0.002 * (Math.random() - 0.5);
    objects.push({
      id: deb.id,
      type: 'DEBRIS',
      r: { x: r[0], y: r[1], z: r[2] },
      v: { x: v[0], y: v[1], z: v[2] },
      mass_kg: 1.0,
    });
  }

  return objects;
}

/**
 * Seed the ACMEngine with initial constellation data.
 * Retries up to 5 times with a 2-second delay between attempts.
 */
export async function seedEngine(): Promise<boolean> {
  const maxRetries = 5;
  const retryDelay = 2000;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    console.log(`🛰️  Seeding ACMEngine (attempt ${attempt}/${maxRetries})...`);

    const healthy = await proxyHealthCheck();
    if (!healthy) {
      console.log(`   ⚠️  ACMEngine not reachable at ${ENGINE_URL}`);
      if (attempt < maxRetries) {
        console.log(`   Retrying in ${retryDelay / 1000}s...`);
        await new Promise((r) => setTimeout(r, retryDelay));
        continue;
      }
      console.log('   ❌ ACMEngine unavailable — running in OFFLINE mode with mock data');
      return false;
    }

    const objects = buildSeedTelemetry();
    const result = await proxyTelemetry(objects);

    if (result.ok) {
      console.log(`   ✅ Seeded ${objects.length} objects into ACMEngine`);
      console.log(`   Engine response:`, JSON.stringify(result.data));
      return true;
    } else {
      console.log(`   ❌ Seed failed: ${result.error}`);
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, retryDelay));
      }
    }
  }

  console.log('   ❌ All seed attempts failed — running in OFFLINE mode');
  return false;
}

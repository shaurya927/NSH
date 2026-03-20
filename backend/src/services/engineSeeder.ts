// ============================================
// AETHER – Engine Seeder
// Seeds initial constellation data into ACMEngine on startup
// ============================================

import { proxyTelemetry, proxyHealthCheck, ENGINE_URL } from './engineProxy';
import * as satellite from 'satellite.js';

/**
 * Satellite metadata registry — dynamically populated from TLEs at seed time.
 * Maps engine object IDs to rich display data + real orbital parameters.
 */
export const SATELLITE_REGISTRY: Record<string, {
  name: string;
  noradId: string;
  constellation: string;
  orbitType: string;
  baseHealth: number;
  initialFuelKg: number;
  inclination: number;
  eccentricity: number;
  period: number;
  altitude: number;
  velocityMag: number;
  satrec?: any;
}> = {};

function classifyOrbitType(altKm: number, incDeg: number): string {
  if (altKm > 34000) return 'GEO';
  if (altKm > 2000) return 'MEO';
  if (incDeg > 85) return 'SSO';
  return 'LEO';
}

function classifyConstellation(name: string): string {
  if (name.startsWith('IRNSS')) return 'NavIC';
  if (name.startsWith('GSAT')) return 'GSAT';
  if (name.startsWith('INSAT')) return 'INSAT';
  if (name.startsWith('CARTOSAT')) return 'Cartosat';
  if (name.startsWith('RISAT')) return 'RISAT';
  if (name.startsWith('EOS')) return 'EOS';
  if (name.startsWith('RESOURCESAT')) return 'Resourcesat';
  return 'ISRO';
}

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

// Hardcoded Indian satellite TLEs as fallback when Celestrak is unreachable
const INDIAN_SATELLITE_TLES = [
  ['INSAT-3D', '1 39216U 13043A   26078.50000000  .00000045  00000-0  00000+0 0  9991', '2 39216  0.0452  75.4000 0003253 142.3000 217.7000  1.00272542 46001'],
  ['INSAT-3DR', '1 41752U 16054A   26078.50000000  .00000042  00000-0  00000+0 0  9992', '2 41752  0.0415  82.1000 0001234 130.5000 229.5000  1.00271234 34001'],
  ['GSAT-6', '1 40880U 15047A   26078.50000000  .00000038  00000-0  00000+0 0  9993', '2 40880  0.0612  83.0000 0003567 145.2000 214.8000  1.00270987 38001'],
  ['GSAT-6A', '1 43241U 18032A   26078.50000000  .00000041  00000-0  00000+0 0  9994', '2 43241  0.0534  79.5000 0002345 138.7000 221.3000  1.00271567 28001'],
  ['GSAT-7A', '1 43872U 18104A   26078.50000000  .00000039  00000-0  00000+0 0  9995', '2 43872  0.0298  93.2000 0001456 125.6000 234.4000  1.00272345 26001'],
  ['GSAT-9', '1 42380U 17029A   26078.50000000  .00000043  00000-0  00000+0 0  9996', '2 42380  0.0156  48.5000 0004567 150.3000 209.7000  1.00270456 32001'],
  ['GSAT-11', '1 43862U 18100A   26078.50000000  .00000036  00000-0  00000+0 0  9997', '2 43862  0.0523  74.8000 0001234 160.2000 199.8000  1.00271890 26001'],
  ['GSAT-14', '1 39498U 14003A   26078.50000000  .00000044  00000-0  00000+0 0  9998', '2 39498  0.0245  93.5000 0002678 135.4000 224.6000  1.00270234 44001'],
  ['GSAT-15', '1 41028U 15065A   26078.50000000  .00000040  00000-0  00000+0 0  9999', '2 41028  0.0312  93.5000 0002456 140.1000 219.9000  1.00272100 38001'],
  ['GSAT-16', '1 40332U 14089A   26078.50000000  .00000037  00000-0  00000+0 0  9990', '2 40332  0.0278  55.2000 0003345 155.6000 204.4000  1.00271456 42001'],
  ['GSAT-17', '1 42713U 17038B   26078.50000000  .00000035  00000-0  00000+0 0  9991', '2 42713  0.0423  93.5000 0001890 148.3000 211.7000  1.00270567 32001'],
  ['GSAT-18', '1 41797U 16063A   26078.50000000  .00000046  00000-0  00000+0 0  9992', '2 41797  0.0367  74.0000 0002567 132.8000 227.2000  1.00271890 34001'],
  ['GSAT-19', '1 42747U 17039A   26078.50000000  .00000038  00000-0  00000+0 0  9993', '2 42747  0.0489  93.5000 0003123 158.1000 201.9000  1.00272567 32001'],
  ['GSAT-24', '1 52902U 22067A   26078.50000000  .00000034  00000-0  00000+0 0  9994', '2 52902  0.0234  83.5000 0001567 145.5000 214.5000  1.00271234 14001'],
  ['GSAT-30', '1 44998U 20007A   26078.50000000  .00000041  00000-0  00000+0 0  9995', '2 44998  0.0189  83.5000 0002890 152.4000 207.6000  1.00270890 22001'],
  ['GSAT-31', '1 44040U 19010A   26078.50000000  .00000039  00000-0  00000+0 0  9996', '2 44040  0.0345  93.5000 0001678 163.7000 196.3000  1.00271567 26001'],
  ['CARTOSAT-2D', '1 42720U 17008G   26078.50000000  .00000680  00000-0  29800-4 0  9997', '2 42720 97.4300 140.5000 0011234 234.5000 125.4000 15.19432000 49001'],
  ['CARTOSAT-2E', '1 42767U 17036A   26078.50000000  .00000560  00000-0  25400-4 0  9998', '2 42767 97.4400 165.3000 0010567 225.8000 134.1000 15.19234000 46001'],
  ['CARTOSAT-2F', '1 43111U 18004A   26078.50000000  .00000520  00000-0  23600-4 0  9999', '2 43111 97.4500 189.7000 0009890 218.3000 141.6000 15.19345000 42001'],
  ['CARTOSAT-3', '1 44789U 19089A   26078.50000000  .00000480  00000-0  21800-4 0  9990', '2 44789 97.5000 245.2000 0012345 204.7000 155.2000 15.19456000 22001'],
  ['RISAT-2', '1 34807U 09019A   26078.50000000  .00000890  00000-0  38200-4 0  9991', '2 34807 41.2100 285.4000 0009567 178.3000 181.7000 14.82345000 86001'],
  ['RISAT-2B', '1 44233U 19028A   26078.50000000  .00000750  00000-0  33400-4 0  9992', '2 44233 37.0000 312.6000 0008890 165.4000 194.5000 14.82567000 38001'],
  ['RISAT-2BR1', '1 44853U 19091B   26078.50000000  .00000820  00000-0  35600-4 0  9993', '2 44853 37.0100 345.8000 0007234 152.6000 207.3000 14.82890000 22001'],
  ['IRNSS-1A', '1 39199U 13034A   26078.50000000  .00000032  00000-0  00000+0 0  9994', '2 39199 28.7000  15.3000 0025678 200.4000 159.5000  1.00272890 46001'],
  ['IRNSS-1B', '1 39635U 14017A   26078.50000000  .00000035  00000-0  00000+0 0  9995', '2 39635 28.6000  55.2000 0023456 195.3000 164.6000  1.00271234 44001'],
  ['IRNSS-1C', '1 40269U 14061A   26078.50000000  .00000033  00000-0  00000+0 0  9996', '2 40269 28.8000  83.5000 0027890 188.2000 171.7000  1.00272345 42001'],
  ['IRNSS-1D', '1 40547U 15018A   26078.50000000  .00000034  00000-0  00000+0 0  9997', '2 40547 28.7000 111.8000 0022345 210.6000 149.3000  1.00270567 40001'],
  ['IRNSS-1E', '1 41241U 16003A   26078.50000000  .00000036  00000-0  00000+0 0  9998', '2 41241 28.6000 142.1000 0024567 205.8000 154.1000  1.00271890 38001'],
  ['IRNSS-1F', '1 41384U 16015A   26078.50000000  .00000031  00000-0  00000+0 0  9999', '2 41384 28.7000 175.3000 0026789 198.3000 161.6000  1.00272234 38001'],
  ['IRNSS-1G', '1 41469U 16027A   26078.50000000  .00000037  00000-0  00000+0 0  9990', '2 41469 28.8000 200.6000 0021234 215.4000 144.5000  1.00270890 36001'],
  ['IRNSS-1I', '1 43286U 18035A   26078.50000000  .00000033  00000-0  00000+0 0  9991', '2 43286 28.7000 232.8000 0023567 208.7000 151.2000  1.00271567 28001'],
  ['EOS-01', '1 47177U 20084A   26078.50000000  .00000720  00000-0  31800-4 0  9992', '2 47177 37.0200  56.4000 0010234 172.3000 187.6000 14.82456000 18001'],
  ['EOS-02', '1 53380U 22098A   26078.50000000  .00000450  00000-0  20400-4 0  9993', '2 53380 37.0000  89.7000 0009567 185.6000 174.3000 14.82678000 12001'],
  ['EOS-04', '1 51741U 22017A   26078.50000000  .00000580  00000-0  26200-4 0  9994', '2 51741 97.4600 312.5000 0011890 245.3000 114.6000 15.19567000 14001'],
  ['EOS-06', '1 54372U 22162A   26078.50000000  .00000510  00000-0  23200-4 0  9995', '2 54372 98.7200  45.6000 0013234 256.7000 103.2000 14.19890000 10001'],
  ['RESOURCESAT-2', '1 37387U 11015A   26078.50000000  .00000610  00000-0  27400-4 0  9996', '2 37387 98.7300  78.9000 0008456 234.2000 125.7000 14.21234000 76001'],
  ['RESOURCESAT-2A', '1 43125U 18009A   26078.50000000  .00000550  00000-0  24800-4 0  9997', '2 43125 98.7400 112.3000 0009890 228.5000 131.4000 14.21567000 42001'],
  ['MICROSAT-R DEB', '1 44382U 19006B   26078.50000000  .00001200  00000-0  52000-4 0  9998', '2 44382 96.6200 145.6000 0045678 178.9000 181.0000 15.01234000 30001'],
];

function parseTlesFromText(tleText: string) {
  const indianPrefixes = ['INSAT', 'GSAT', 'CARTOSAT', 'RISAT', 'IRNSS', 'EOS', 'MICROSAT', 'PSLV', 'RESOURCESAT'];
  const lines = tleText.split('\n');
  const objects: any[] = [];

  for (let i = 0; i < lines.length - 2; i += 3) {
    const name = lines[i].trim();
    const tle1 = lines[i+1].trim();
    const tle2 = lines[i+2].trim();
    if (!name || !tle1 || !tle2) continue;

    const isIndian = indianPrefixes.some(prefix => name.startsWith(prefix) || name.includes(` ${prefix}`));
    if (!isIndian) continue;

    const obj = propagateTle(name, tle1, tle2);
    if (obj) objects.push(obj);
    if (objects.length >= 60) break;
  }
  return objects;
}

function propagateTle(name: string, tle1: string, tle2: string) {
  try {
    const satrec = satellite.twoline2satrec(tle1, tle2);
    const now = new Date();
    const pv = satellite.propagate(satrec, now);
    if (!pv || !pv.position || !pv.velocity) return null;
    const pos = pv.position;
    const vel = pv.velocity;
    if (typeof pos === 'boolean') return null;

    // Extract real orbital elements from TLE
    const inclinationDeg = satrec.inclo * (180 / Math.PI);  // radians -> degrees
    const eccentricity = satrec.ecco;
    const meanMotionRevPerDay = satrec.no * (1440 / (2 * Math.PI)); // rad/min -> rev/day
    const periodMin = 1440 / meanMotionRevPerDay; // minutes

    // Compute real altitude from position vector
    const rMag = Math.sqrt(pos.x ** 2 + pos.y ** 2 + pos.z ** 2);
    const altitudeKm = rMag - R_EARTH;

    // Compute real velocity magnitude
    const vMag = Math.sqrt((vel as any).x ** 2 + (vel as any).y ** 2 + (vel as any).z ** 2);

    // Extract NORAD catalog number from TLE line 1
    const noradId = tle1.substring(2, 7).trim();

    const type = name.includes('DEB') ? 'DEBRIS' : 'SATELLITE';
    const orbitType = classifyOrbitType(altitudeKm, inclinationDeg);
    const constellation = classifyConstellation(name);

    // Register satellite with real orbital parameters
    if (type === 'SATELLITE') {
      SATELLITE_REGISTRY[name] = {
        name,
        noradId,
        constellation,
        orbitType,
        baseHealth: 85 + Math.floor(Math.random() * 15), // 85-99
        initialFuelKg: 50.0,
        inclination: Math.round(inclinationDeg * 100) / 100,
        eccentricity: Math.round(eccentricity * 1000000) / 1000000,
        period: Math.round(periodMin * 100) / 100,
        altitude: Math.round(altitudeKm * 100) / 100,
        velocityMag: Math.round(vMag * 1000) / 1000,
        satrec,
      };
    }

    return {
      id: name,
      type,
      r: { x: pos.x, y: pos.y, z: pos.z },
      v: { x: vel.x, y: (vel as any).y, z: (vel as any).z },
      mass_kg: type === 'SATELLITE' ? 500.0 : 1.0,
      fuel_kg: type === 'SATELLITE' ? 50.0 : 0,
    };
  } catch {
    return null;
  }
}

export async function fetchLiveIndianTelemetry() {
  // Try live fetch with a 8-second timeout
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle';
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!response.ok) throw new Error('HTTP ' + response.status);
    const text = await response.text();
    const objects = parseTlesFromText(text);
    if (objects.length > 0) {
      console.log(`   📡 Fetched ${objects.length} live Indian satellites from Celestrak`);
      return objects;
    }
    throw new Error('No Indian satellites found in response');
  } catch (err: any) {
    clearTimeout(timeout);
    console.log(`   ⚠️  Celestrak fetch failed (${err.message}), using hardcoded Indian TLEs`);
  }

  // Fallback: use hardcoded TLEs
  const objects: any[] = [];
  for (const [name, tle1, tle2] of INDIAN_SATELLITE_TLES) {
    const obj = propagateTle(name, tle1, tle2);
    if (obj) objects.push(obj);
    if (objects.length >= 60) break;
  }
  console.log(`   🛰️  Loaded ${objects.length} Indian satellites from hardcoded TLEs`);
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

    let objects: any[];
    try {
      objects = await fetchLiveIndianTelemetry();
    } catch (err: any) {
      console.log('   ❌ Failed to fetch live telemetry:', err.message);
      return false;
    }

    if (objects.length === 0) {
      console.log('   ❌ No satellite objects to seed');
      return false;
    }

    const result = await proxyTelemetry(objects);

    if (result.ok) {
      console.log(`   ✅ Seeded ${objects.length} Indian satellites into ACMEngine`);
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

// ============================================
// AETHER – Mock Data Service
// Provides sample data for development/testing
// Replace with real data sources later
// ============================================

import {
  Satellite,
  Debris,
  TelemetryStateVector,
  ConjunctionEvent,
  VisualizationSnapshot,
} from '../models/types';

/** Generate a mock telemetry state vector */
function mockTelemetry(lat: number, lon: number, alt: number): TelemetryStateVector {
  return {
    timestamp: new Date().toISOString(),
    position: { x: 6778 + alt, y: 0, z: 0 },
    velocity: { vx: 0, vy: 7.5, vz: 0 },
    latitude: lat,
    longitude: lon,
    altitude: alt,
    inclination: 51.6,
    eccentricity: 0.0001,
    period: 92.5,
  };
}

/** Sample satellites for mock data */
export const mockSatellites: Satellite[] = [
  {
    id: 'sat-001',
    name: 'AETHER-Alpha',
    noradId: '55001',
    constellation: 'AETHER-Prime',
    status: 'nominal',
    orbitType: 'LEO',
    telemetry: mockTelemetry(28.5, -80.6, 408),
    fuelLevel: 87,
    health: 95,
    lastContact: new Date().toISOString(),
  },
  {
    id: 'sat-002',
    name: 'AETHER-Beta',
    noradId: '55002',
    constellation: 'AETHER-Prime',
    status: 'warning',
    orbitType: 'LEO',
    telemetry: mockTelemetry(35.2, 120.4, 415),
    fuelLevel: 42,
    health: 78,
    lastContact: new Date().toISOString(),
  },
  {
    id: 'sat-003',
    name: 'AETHER-Gamma',
    noradId: '55003',
    constellation: 'AETHER-Prime',
    status: 'nominal',
    orbitType: 'LEO',
    telemetry: mockTelemetry(-12.8, 45.3, 402),
    fuelLevel: 93,
    health: 99,
    lastContact: new Date().toISOString(),
  },
  {
    id: 'sat-004',
    name: 'AETHER-Delta',
    noradId: '55004',
    constellation: 'AETHER-Prime',
    status: 'critical',
    orbitType: 'LEO',
    telemetry: mockTelemetry(52.1, -3.7, 395),
    fuelLevel: 12,
    health: 45,
    lastContact: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'sat-005',
    name: 'AETHER-Epsilon',
    noradId: '55005',
    constellation: 'AETHER-Prime',
    status: 'nominal',
    orbitType: 'LEO',
    telemetry: mockTelemetry(-33.9, 151.2, 420),
    fuelLevel: 76,
    health: 91,
    lastContact: new Date().toISOString(),
  },
];

/** Sample debris objects */
export const mockDebris: Debris[] = [
  {
    id: 'deb-001',
    name: 'COSMOS-2251 Fragment',
    noradId: '34001',
    type: 'fragment',
    size: 'small',
    position: { x: 6900, y: 120, z: -50 },
    velocity: { vx: -1.2, vy: 7.3, vz: 0.5 },
    riskLevel: 'high',
  },
  {
    id: 'deb-002',
    name: 'SL-16 Rocket Body',
    noradId: '22285',
    type: 'rocket_body',
    size: 'large',
    position: { x: 7100, y: -200, z: 80 },
    velocity: { vx: 0.8, vy: 7.1, vz: -0.3 },
    riskLevel: 'medium',
  },
  {
    id: 'deb-003',
    name: 'Unknown Object',
    noradId: '99001',
    type: 'unknown',
    size: 'medium',
    position: { x: 6800, y: 50, z: 300 },
    velocity: { vx: -0.5, vy: 7.4, vz: 0.1 },
    riskLevel: 'low',
  },
  {
    id: 'deb-004',
    name: 'Fengyun-1C Fragment',
    noradId: '31001',
    type: 'fragment',
    size: 'small',
    position: { x: 6850, y: -80, z: -120 },
    velocity: { vx: 1.0, vy: 7.2, vz: -0.2 },
    riskLevel: 'critical',
  },
];

/** Sample conjunction events */
export const mockConjunctions: ConjunctionEvent[] = [
  {
    id: 'conj-001',
    primaryObject: 'sat-001',
    secondaryObject: 'deb-004',
    timeOfClosestApproach: new Date(Date.now() + 7200000).toISOString(),
    missDistance: 0.45,
    probability: 0.0032,
    riskLevel: 'high',
  },
  {
    id: 'conj-002',
    primaryObject: 'sat-002',
    secondaryObject: 'deb-001',
    timeOfClosestApproach: new Date(Date.now() + 14400000).toISOString(),
    missDistance: 1.2,
    probability: 0.0008,
    riskLevel: 'medium',
  },
];

/** Get a full visualization snapshot */
export function getVisualizationSnapshot(): VisualizationSnapshot {
  return {
    satellites: mockSatellites,
    debris: mockDebris,
    conjunctions: mockConjunctions,
    timestamp: new Date().toISOString(),
  };
}

// ============================================
// AETHER – Autonomous Constellation Manager
// Shared Data Models / TypeScript Interfaces
// ============================================

/** Represents a satellite in the constellation */
export interface Satellite {
  id: string;
  name: string;
  noradId: string;
  constellation: string;
  status: 'nominal' | 'warning' | 'critical' | 'offline';
  orbitType: 'LEO' | 'MEO' | 'GEO' | 'HEO';
  telemetry: TelemetryStateVector;
  fuelLevel: number; // percentage 0-100
  health: number; // percentage 0-100
  lastContact: string; // ISO timestamp
}

/** Represents a piece of space debris */
export interface Debris {
  id: string;
  name: string;
  noradId: string;
  type: 'rocket_body' | 'fragment' | 'payload' | 'unknown';
  size: 'small' | 'medium' | 'large';
  position: {
    x: number;
    y: number;
    z: number;
  };
  velocity: {
    vx: number;
    vy: number;
    vz: number;
  };
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

/** Telemetry state vector for a satellite */
export interface TelemetryStateVector {
  timestamp: string; // ISO timestamp
  position: {
    x: number; // km (ECI frame)
    y: number;
    z: number;
  };
  velocity: {
    vx: number; // km/s
    vy: number;
    vz: number;
  };
  latitude: number;
  longitude: number;
  altitude: number; // km
  inclination: number; // degrees
  eccentricity: number;
  period: number; // minutes
}

/** Maneuver command for collision avoidance */
export interface ManeuverCommand {
  id: string;
  satelliteId: string;
  type: 'prograde' | 'retrograde' | 'normal' | 'radial';
  deltaV: number; // m/s
  scheduledTime: string; // ISO timestamp
  duration: number; // seconds
  status: 'pending' | 'scheduled' | 'executing' | 'completed' | 'failed';
  reason: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

/** Simulation state for one time step */
export interface SimulationState {
  stepNumber: number;
  timestamp: string; // ISO timestamp
  satellites: Satellite[];
  debris: Debris[];
  conjunctions: ConjunctionEvent[];
  maneuversExecuted: string[]; // maneuver IDs
}

/** Conjunction (close-approach) event between two objects */
export interface ConjunctionEvent {
  id: string;
  primaryObject: string; // satellite ID
  secondaryObject: string; // debris or satellite ID
  timeOfClosestApproach: string; // ISO timestamp
  missDistance: number; // km
  probability: number; // collision probability (0-1)
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

/** API response wrapper */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  timestamp: string;
  message?: string;
}

/** Visualization snapshot returned by the API */
export interface VisualizationSnapshot {
  satellites: Satellite[];
  debris: Debris[];
  conjunctions: ConjunctionEvent[];
  timestamp: string;
}

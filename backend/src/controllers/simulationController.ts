// ============================================
// AETHER – Simulation Controller
// Handles orbital simulation stepping
// ============================================

import { Request, Response } from 'express';
import { ApiResponse, SimulationState } from '../models/types';
import { mockSatellites, mockDebris, mockConjunctions } from '../services/mockData';

/**
 * POST /api/simulate/step
 * Advances the simulation by one time step.
 * TODO: Implement SGP4/SDP4 propagation
 * TODO: Run conjunction screening
 * TODO: Apply scheduled maneuvers
 */
export function simulateStep(req: Request, res: Response): void {
  const { stepNumber = 1, deltaTime = 60 } = req.body;

  // Mutate mock data to simulate propagation
  mockSatellites.forEach((sat) => {
    sat.fuelLevel = Math.max(0, sat.fuelLevel - (Math.random() * 0.2));
    sat.telemetry.altitude = Math.max(0, sat.telemetry.altitude - (Math.random() * 0.5));
    sat.telemetry.velocity.vy += (Math.random() * 0.02 - 0.01);
    
    // Randomize health slightly for critical ones
    if (sat.status === 'warning' || sat.status === 'critical') {
      sat.health = Math.max(0, sat.health - Math.random() * 2);
    }
  });

  mockConjunctions.forEach((conj) => {
    conj.missDistance = Math.max(0, conj.missDistance - (Math.random() * 0.1));
    conj.probability = Math.min(1, conj.probability + (Math.random() * 0.005));
    if (conj.missDistance < 0.5) {
      conj.riskLevel = 'critical';
    }
  });

  const simulationState: SimulationState = {
    stepNumber,
    timestamp: new Date(Date.now() + stepNumber * deltaTime * 1000).toISOString(),
    satellites: mockSatellites,
    debris: mockDebris,
    conjunctions: mockConjunctions,
    maneuversExecuted: [],
  };

  const response: ApiResponse<SimulationState> = {
    success: true,
    data: simulationState,
    timestamp: new Date().toISOString(),
    message: `Simulation step ${stepNumber} completed`,
  };

  res.json(response);
}

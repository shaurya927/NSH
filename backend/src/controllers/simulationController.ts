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

  // TODO: Propagate satellite orbits using SGP4
  // TODO: Propagate debris objects
  // TODO: Screen for conjunctions
  // TODO: Execute pending maneuvers

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

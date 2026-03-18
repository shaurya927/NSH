// ============================================
// AETHER – Simulation Controller
// Handles orbital simulation stepping
// ============================================

import { Request, Response } from 'express';
import {
  proxySimulateStep,
  proxySnapshot,
  transformSnapshot,
  transformConjunctions,
} from '../services/engineProxy';
import { mockSatellites, mockDebris, mockConjunctions } from '../services/mockData';

/**
 * POST /api/simulate/step
 * Advances the simulation by one time step.
 * Proxies to ACMEngine when available, falls back to mock data.
 */
export async function simulateStep(req: Request, res: Response): Promise<void> {
  const { stepNumber = 1, deltaTime = 60, step_seconds } = req.body;
  const seconds = step_seconds || deltaTime || 60;

  try {
    // Step the engine
    const stepResult = await proxySimulateStep(seconds);

    if (stepResult.ok && stepResult.data) {
      // Fetch fresh snapshot after stepping
      const snapshotResult = await proxySnapshot();
      const snapshot = snapshotResult.ok && snapshotResult.data
        ? transformSnapshot(snapshotResult.data)
        : null;

      // Transform conjunctions from step result
      const conjunctions: any[] = transformConjunctions(
        stepResult.data.predicted_conjunctions || []
      );

      // Merge conjunctions into snapshot
      if (snapshot) {
        (snapshot as any).conjunctions = conjunctions;
      }

      res.json({
        success: true,
        data: snapshot || {
          satellites: [],
          debris: [],
          conjunctions,
          timestamp: new Date().toISOString(),
        },
        engineResult: {
          ticks: stepResult.data.ticks,
          collisionsDetected: stepResult.data.collisions_detected || [],
          maneuversExecuted: stepResult.data.maneuvers_executed || 0,
          simulationTime: stepResult.data.simulation_time_s || 0,
          stationKeeping: stepResult.data.station_keeping || [],
          autonomousManeuvers: stepResult.data.autonomous_maneuvers || [],
        },
        timestamp: new Date().toISOString(),
        message: `Simulation advanced ${seconds}s via ACMEngine`,
        engineOnline: true,
      });
      return;
    }
  } catch (err) {
    console.error('Engine simulation proxy error:', err);
  }

  // Fallback: mutate mock data
  mockSatellites.forEach((sat) => {
    sat.fuelLevel = Math.max(0, sat.fuelLevel - Math.random() * 0.2);
    sat.telemetry.altitude = Math.max(0, sat.telemetry.altitude - Math.random() * 0.5);
    sat.telemetry.velocity.vy += Math.random() * 0.02 - 0.01;
    if (sat.status === 'warning' || sat.status === 'critical') {
      sat.health = Math.max(0, sat.health - Math.random() * 2);
    }
  });

  mockConjunctions.forEach((conj) => {
    conj.missDistance = Math.max(0, conj.missDistance - Math.random() * 0.1);
    conj.probability = Math.min(1, conj.probability + Math.random() * 0.005);
    if (conj.missDistance < 0.5) conj.riskLevel = 'critical';
  });

  res.json({
    success: true,
    data: {
      stepNumber,
      timestamp: new Date(Date.now() + stepNumber * seconds * 1000).toISOString(),
      satellites: mockSatellites,
      debris: mockDebris,
      conjunctions: mockConjunctions,
      maneuversExecuted: [],
    },
    timestamp: new Date().toISOString(),
    message: `Simulation step ${stepNumber} completed (offline)`,
    engineOnline: false,
  });
}

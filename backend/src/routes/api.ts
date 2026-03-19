// ============================================
// AETHER – API Routes
// Defines all REST API endpoints
// ============================================

import { Router } from 'express';
import { ingestTelemetry } from '../controllers/telemetryController';
import { scheduleManeuver } from '../controllers/maneuverController';
import { simulateStep } from '../controllers/simulationController';
import { getSnapshot } from '../controllers/visualizationController';

const router = Router();

// --- Telemetry Routes ---
router.post('/telemetry', ingestTelemetry);

// --- Maneuver Routes ---
router.post('/maneuver/schedule', scheduleManeuver);

// --- Simulation Routes ---
router.post('/simulate/step', simulateStep);

// --- Visualization Routes ---
router.get('/visualization/snapshot', getSnapshot);

// --- Engine Routes ---
import { seedEngine } from '../services/engineSeeder';
router.get('/seed', async (_req, res) => {
  const result = await seedEngine();
  res.json({ success: result, message: result ? 'Engine seeded successfully' : 'Failed to seed engine' });
});

// --- Health Check ---
router.get('/health', (_req, res) => {
  res.json({
    status: 'online',
    service: 'AETHER Mission Control API',
    version: '2.0.0',
    timestamp: new Date().toISOString(),
    engineUrl: process.env.ENGINE_URL || 'http://localhost:8000',
  });
});

export default router;

// ============================================
// AETHER – Visualization Controller
// Returns snapshot data for frontend rendering
// ============================================

import { Request, Response } from 'express';
import { proxySnapshot, transformSnapshot, transformConjunctions } from '../services/engineProxy';
import { getVisualizationSnapshot } from '../services/mockData';

/**
 * GET /api/visualization/snapshot
 * Returns current satellite positions, debris, and conjunction data.
 * Proxies to ACMEngine when available, falls back to mock data.
 */
export async function getSnapshot(req: Request, res: Response): Promise<void> {
  try {
    const engineResult = await proxySnapshot();

    if (engineResult.ok && engineResult.data) {
      const transformed = transformSnapshot(engineResult.data);

      res.json({
        success: true,
        data: transformed,
        timestamp: new Date().toISOString(),
        message: 'Live snapshot from ACMEngine',
        engineOnline: true,
      });
      return;
    }
  } catch (err) {
    console.error('Engine proxy error:', err);
  }

  // Fallback to mock data
  const snapshot = getVisualizationSnapshot();
  res.json({
    success: true,
    data: snapshot,
    timestamp: new Date().toISOString(),
    message: 'Offline snapshot (mock data)',
    engineOnline: false,
  });
}

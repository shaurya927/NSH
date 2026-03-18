// ============================================
// AETHER – Telemetry Controller
// Handles satellite telemetry data ingestion
// ============================================

import { Request, Response } from 'express';
import { proxyTelemetry } from '../services/engineProxy';

/**
 * POST /api/telemetry
 * Accepts telemetry data from satellites.
 * Proxies to ACMEngine when available.
 */
export async function ingestTelemetry(req: Request, res: Response): Promise<void> {
  const telemetryData = req.body;

  // Normalize input: accept { objects: [...] } or direct array
  const objects = Array.isArray(telemetryData)
    ? telemetryData
    : telemetryData.objects || [telemetryData];

  try {
    const engineResult = await proxyTelemetry(objects);

    if (engineResult.ok && engineResult.data) {
      res.json({
        success: true,
        data: engineResult.data,
        timestamp: new Date().toISOString(),
        message: 'Telemetry ingested by ACMEngine',
        engineOnline: true,
      });
      return;
    }
  } catch (err) {
    console.error('Engine telemetry proxy error:', err);
  }

  // Fallback
  res.json({
    success: true,
    data: {
      received: true,
      objectCount: objects.length,
    },
    timestamp: new Date().toISOString(),
    message: 'Telemetry received (offline mode)',
    engineOnline: false,
  });
}

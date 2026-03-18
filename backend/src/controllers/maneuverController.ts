// ============================================
// AETHER – Maneuver Controller
// Handles collision avoidance maneuver scheduling
// ============================================

import { Request, Response } from 'express';
import { proxyManeuver } from '../services/engineProxy';
import { v4Fallback } from '../utils/id';

/**
 * POST /api/maneuver/schedule
 * Accepts a maneuver command and schedules it via ACMEngine.
 * Falls back to mock response when engine is offline.
 */
export async function scheduleManeuver(req: Request, res: Response): Promise<void> {
  const { satelliteId, object_id, type, deltaV, delta_v_rtn_km_s, scheduledTime, duration, reason, priority } = req.body;

  const targetId = object_id || satelliteId || 'SAT-001';

  // Build delta-v vector: prefer RTN format, fallback to simple scalar
  let dvVector: number[];
  if (delta_v_rtn_km_s && Array.isArray(delta_v_rtn_km_s)) {
    dvVector = delta_v_rtn_km_s;
  } else if (typeof deltaV === 'number') {
    // Convert simple deltaV (m/s) to RTN (km/s): apply as along-track (T direction)
    const dvKmS = deltaV / 1000;
    dvVector = [0, dvKmS, 0]; // transverse burn
  } else {
    dvVector = [0, 0.001, 0]; // small default burn
  }

  try {
    const engineResult = await proxyManeuver({
      object_id: targetId,
      delta_v_rtn_km_s: dvVector,
    });

    if (engineResult.ok && engineResult.data) {
      res.json({
        success: true,
        data: {
          id: `mnv-${v4Fallback()}`,
          satelliteId: targetId,
          type: type || 'prograde',
          deltaV: Math.sqrt(dvVector.reduce((s, v) => s + v * v, 0)) * 1000, // back to m/s
          scheduledTime: new Date(Date.now() + (engineResult.data.scheduled_for_time_s || 10) * 1000).toISOString(),
          duration: duration || 30,
          status: 'scheduled',
          reason: reason || 'Collision avoidance maneuver',
          priority: priority || 'high',
          engineScheduledFor: engineResult.data.scheduled_for_time_s,
        },
        timestamp: new Date().toISOString(),
        message: 'Maneuver scheduled via ACMEngine',
        engineOnline: true,
      });
      return;
    }
  } catch (err) {
    console.error('Engine maneuver proxy error:', err);
  }

  // Fallback
  res.json({
    success: true,
    data: {
      id: `mnv-${v4Fallback()}`,
      satelliteId: targetId,
      type: type || 'prograde',
      deltaV: deltaV || 1.5,
      scheduledTime: scheduledTime || new Date(Date.now() + 3600000).toISOString(),
      duration: duration || 30,
      status: 'scheduled',
      reason: reason || 'Collision avoidance maneuver',
      priority: priority || 'high',
    },
    timestamp: new Date().toISOString(),
    message: 'Maneuver scheduled (offline mode)',
    engineOnline: false,
  });
}

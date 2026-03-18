// ============================================
// AETHER – Express Server Entry Point
// ============================================

import express from 'express';
import cors from 'cors';
import apiRoutes from './routes/api';

const app = express();
const PORT = process.env.PORT || 5000;

// --- Middleware ---
app.use(cors());
app.use(express.json());

// --- Request Logger (dev) ---
app.use((req, _res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// --- API Routes ---
app.use('/api', apiRoutes);

// --- Root ---
app.get('/', (_req, res) => {
  res.json({
    name: 'AETHER – Autonomous Constellation Manager API',
    version: '1.0.0',
    endpoints: [
      'POST /api/telemetry',
      'POST /api/maneuver/schedule',
      'POST /api/simulate/step',
      'GET  /api/visualization/snapshot',
      'GET  /api/health',
    ],
  });
});

// --- Start Server ---
app.listen(PORT, () => {
  console.log(`\n🛰️  AETHER Mission Control API`);
  console.log(`   Running on http://localhost:${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/api/health\n`);
});

export default app;

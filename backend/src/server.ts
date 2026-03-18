// ============================================
// AETHER – Express Server Entry Point
// ============================================

import express from 'express';
import cors from 'cors';
import apiRoutes from './routes/api';
import { seedEngine } from './services/engineSeeder';

const app = express();
const PORT = process.env.PORT || 5000;

// --- Middleware ---
app.use(cors());
app.use(express.json({ limit: '10mb' }));

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
    version: '2.0.0',
    endpoints: [
      'POST /api/telemetry',
      'POST /api/maneuver/schedule',
      'POST /api/simulate/step',
      'GET  /api/visualization/snapshot',
      'GET  /api/health',
    ],
    engine: process.env.ENGINE_URL || 'http://localhost:8000',
  });
});

// --- Start Server ---
app.listen(PORT, async () => {
  console.log(`\n🛰️  AETHER Mission Control API`);
  console.log(`   Running on http://localhost:${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/api/health`);
  console.log(`   Engine: ${process.env.ENGINE_URL || 'http://localhost:8000'}\n`);

  // Seed ACMEngine with initial constellation data
  const engineReady = await seedEngine();
  if (engineReady) {
    console.log('   🟢 ACMEngine connected and seeded — LIVE mode');
  } else {
    console.log('   🟡 ACMEngine unavailable — OFFLINE mode (mock data)');
  }
  console.log('');
});

export default app;

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { AlertTriangle, Clock, ShieldCheck, Crosshair, Satellite, Zap } from 'lucide-react';
import FleetPanel from '../components/FleetPanel';
import ConjunctionsPanel from '../components/ConjunctionsPanel';
import OrbitVisualizer from '../components/OrbitVisualizer';
import MapVisualizer from '../components/MapVisualizer';
import RadarVisualizer from '../components/RadarVisualizer';
import TrackerTable from '../components/TrackerTable';
import Navbar from '../components/Navbar';
import './Dashboard.css';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:5000/api';

const mockTelemetry = (alt: number, vy: number) => ({
  altitude: alt,
  velocity: { vy }
});

const OFFLINE_DATA = {
  satellites: [
    { id: 'sat-1', name: 'AETHER-Alpha', status: 'nominal', noradId: '55001', health: 95, fuelLevel: 87, telemetry: mockTelemetry(550, 7.5) },
    { id: 'sat-2', name: 'AETHER-Beta', status: 'warning', noradId: '55002', health: 78, fuelLevel: 42, telemetry: mockTelemetry(610, 7.3) },
    { id: 'sat-3', name: 'AETHER-Gamma', status: 'nominal', noradId: '55003', health: 99, fuelLevel: 93, telemetry: mockTelemetry(520, 7.6) },
    { id: 'sat-4', name: 'AETHER-Delta', status: 'critical', noradId: '55004', health: 45, fuelLevel: 12, telemetry: mockTelemetry(590, 7.4) },
    { id: 'sat-5', name: 'AETHER-Epsilon', status: 'nominal', noradId: '55005', health: 91, fuelLevel: 76, telemetry: mockTelemetry(640, 7.2) },
  ],
  debris: [{ name: 'DEB-001' }, { name: 'DEB-002' }, { name: 'DEB-003' }],
  conjunctions: [],
  timestamp: new Date().toISOString(),
};

const Dashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);
  const [isSimulating, setIsSimulating] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'info' | '3d' | '2d'>('info');
  const is3D = activeTab === '3d';
  const [offlineMode, setOfflineMode] = useState(false);
  const [engineOnline, setEngineOnline] = useState(false);
  const [simTime, setSimTime] = useState(0);

  const requestToken = useRef(0);

  const advanceSimulation = async (seconds: number) => {
    requestToken.current++; // Invalidate pending fetches
    try {
      setIsSimulating(true);
      const res = await axios.post(`${API_URL}/simulate/step`, { step_seconds: seconds });
      const responseData = res.data.data || res.data;
      setData(responseData);
      setStep(prev => prev + (seconds > 0 ? 1 : -1));

      if (res.data.engineResult) {
        setSimTime(res.data.engineResult.simulationTime || 0);

        const collCount = res.data.engineResult.collisionsDetected?.length || 0;
        const maneuvers = res.data.engineResult.maneuversExecuted || 0;
        if (collCount > 0 || maneuvers > 0) {
          showToast(`Step: ${collCount} collisions, ${maneuvers} maneuvers`);
        }
      }

      setEngineOnline(res.data.engineOnline ?? false);
    } catch (err) {
      console.error("Simulation failed", err);
      showToast('Backend offline — simulation unavailable');
    } finally {
      setIsSimulating(false);
      requestToken.current++; // Invalidate fetches that might have started during simulation
    }
  };


  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const fetchSnapshot = useCallback(async () => {
    if (isSimulating) return;
    
    const token = ++requestToken.current;
    try {
      const res = await axios.get(`${API_URL}/visualization/snapshot`);
      if (requestToken.current !== token) return; // Stale request, discard
      
      const responseData = res.data.data || res.data;
      setData(responseData);
      setEngineOnline(res.data.engineOnline ?? false);
      setOfflineMode(!res.data.engineOnline && !responseData.satellites?.length);
      if (responseData.simulationTime) {
        setSimTime(responseData.simulationTime);
      }
      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch AETHER data", err);
      setOfflineMode(true);
      setEngineOnline(false);
      setLoading(false);
      setData((prev: any) => prev ?? OFFLINE_DATA);
    }
  }, []);



  useEffect(() => {
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 10000);
    return () => clearInterval(interval);
  }, [fetchSnapshot]);

  useEffect(() => {
    if (!is3D) return;

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setActiveTab('info');
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [is3D]);

  if (loading || !data) {
    return (
      <div className="loading-screen">
        <div className="loader"></div>
        <p className="mono-text">ESTABLISHING UPLINK...</p>
      </div>
    );
  }

  const criticalSatellites = data.satellites?.filter((s: any) => s.status === 'critical' || s.status === 'warning') || [];
  const highRiskConjunctions = data.conjunctions?.filter((c: any) => c.riskLevel === 'high' || c.riskLevel === 'critical') || [];

  const formatSimTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `T+${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  if (is3D) {
    return (
      <div className="fullscreen-3d" style={{ position: 'relative' }}>
        <button 
          onClick={() => setActiveTab('info')}
          className="glass-panel"
          style={{
            position: 'absolute',
            top: '24px',
            right: '24px',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            color: 'white',
            cursor: 'pointer',
            borderRadius: '8px',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(30, 41, 59, 0.9)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'rgba(15, 23, 42, 0.8)'}
        >
          <span className="mono-text" style={{ fontSize: '12px' }}>ESC TO CLOSE</span>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
        
        <div className="simulation-controls glass-panel" style={{ position: 'absolute', top: '24px', left: '24px', zIndex: 1000, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="sim-status" style={{ marginBottom: '4px' }}>
            <span className="mono-text label">SIM STEP:</span>
            <span className="mono-text value">{step}</span>
          </div>
          <button className={`btn-advance ${isSimulating ? 'simulating' : ''}`} onClick={() => advanceSimulation(-5400)} disabled={isSimulating}>
            <Clock size={16} />
            <span>{isSimulating ? 'SIMULATING...' : '-90 MIN'}</span>
          </button>
          <button className={`btn-advance ${isSimulating ? 'simulating' : ''}`} onClick={() => advanceSimulation(5400)} disabled={isSimulating}>
            <Clock size={16} />
            <span>{isSimulating ? 'SIMULATING...' : '+90 MIN'}</span>
          </button>
        </div>

        <OrbitVisualizer
          satellites={data.satellites}
          debris={data.debris}
          conjunctions={data.conjunctions}
          minimal
          fullscreen
        />
      </div>
    );
  }

  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="main-content">
        <div className="dashboard" style={{ marginTop: '24px' }}>
          {offlineMode && (
            <div className="glass-panel" style={{ padding: '12px 16px', borderColor: 'rgba(245, 158, 11, 0.4)', background: 'rgba(245, 158, 11, 0.08)' }}>
              <span className="mono-text" style={{ fontSize: '12px', color: 'var(--text-main)' }}>
                OFFLINE MODE — set `VITE_API_URL` or start backend at `http://localhost:5000`
              </span>
            </div>
          )}
          <>
            <div className="dashboard-header">
              <div className="header-title">
                <h2>Network Overview</h2>
                <p className="subtitle">
                  {engineOnline ? (
                    <>
                      <Zap size={14} style={{ color: 'var(--status-nominal)', marginRight: '6px', verticalAlign: 'middle' }} />
                      <span>ACMEngine Live — {formatSimTime(simTime)}</span>
                    </>
                  ) : (
                    'Real-time telemetry and orbital propagation'
                  )}
                </p>
              </div>
              
              <div className="simulation-controls glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-start' }}>
                <div className="sim-status" style={{ marginBottom: '4px' }}>
                  <span className="mono-text label">SIM STEP:</span>
                  <span className="mono-text value">{step}</span>
                </div>
                <button className={`btn-advance ${isSimulating ? 'simulating' : ''}`} onClick={() => advanceSimulation(-5400)} disabled={isSimulating} style={{ width: '100%' }}>
                  <Clock size={16} />
                  <span>{isSimulating ? 'SIMULATING...' : '-90 MIN'}</span>
                </button>
                <button className={`btn-advance ${isSimulating ? 'simulating' : ''}`} onClick={() => advanceSimulation(5400)} disabled={isSimulating} style={{ width: '100%' }}>
                  <Clock size={16} />
                  <span>{isSimulating ? 'SIMULATING...' : '+90 MIN'}</span>
                </button>
              </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="kpi-card glass-panel">
                <div className="kpi-icon bg-blue"><Satellite size={20} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Active Satellites</span>
                  <span className="kpi-value">{data.satellites?.length || 0}</span>
                </div>
              </motion.div>
              
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="kpi-card glass-panel alert">
                <div className="kpi-icon bg-orange"><AlertTriangle size={20} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Anomalies Detected</span>
                  <span className="kpi-value">{criticalSatellites.length}</span>
                </div>
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="kpi-card glass-panel">
                <div className="kpi-icon bg-cyan"><Crosshair size={20} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Tracked Debris</span>
                  <span className="kpi-value">{Array.isArray(data.debris) ? data.debris.length : (data.debris?.count || 0)}</span>
                </div>
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="kpi-card glass-panel alert">
                <div className="kpi-icon bg-red"><ShieldCheck size={20} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Critical Conjunctions</span>
                  <span className="kpi-value glow-text" style={{ color: 'var(--status-critical)' }}>{highRiskConjunctions.length}</span>
                </div>
              </motion.div>
            </div>
          </>

      {/* Dynamic Tab Content */}
      <div className="tab-content" style={{ marginTop: '24px' }}>
        {activeTab === 'info' && (
          <div className="info-grid">
            <div className="left-column" id="fleet-panel">
              <FleetPanel satellites={data.satellites} />
            </div>
            <div className="right-column" id="conjunctions-panel">
              <ConjunctionsPanel conjunctions={data.conjunctions} onScheduleManeuver={showToast} />
            </div>
          </div>
        )}

        {activeTab === '2d' && (
          <div className="tracker-2d-layout">
            <div className="map-section">
              <MapVisualizer satellites={data.satellites} debris={data.debris} conjunctions={data.conjunctions} timestamp={data.timestamp} />
            </div>
            <div className="radar-section">
              <RadarVisualizer satellites={data.satellites} />
            </div>
            <div className="table-section">
              <TrackerTable satellites={data.satellites} />
            </div>
          </div>
        )}
      </div>
      
        {toastMessage && (
          <motion.div 
            className="toast-notification glass-panel"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
          >
            <ShieldCheck size={18} className="text-nominal" style={{ color: 'var(--status-nominal)' }} />
            <span>{toastMessage}</span>
          </motion.div>
        )}
      </div>
      </main>
    </div>
  );
};

export default Dashboard;

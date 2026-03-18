import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { AlertTriangle, Clock, ShieldCheck, Crosshair, Satellite } from 'lucide-react';
import FleetPanel from '../components/FleetPanel';
import ConjunctionsPanel from '../components/ConjunctionsPanel';
import OrbitVisualizer from '../components/OrbitVisualizer';
import MapVisualizer from '../components/MapVisualizer';
import RadarVisualizer from '../components/RadarVisualizer';
import TrackerTable from '../components/TrackerTable';
import Navbar from '../components/Navbar';
import './Dashboard.css';

const API_URL = 'http://localhost:5000/api';

const Dashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);
  const [isSimulating, setIsSimulating] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'info' | '3d' | '2d'>('info');

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const fetchSnapshot = async () => {
    try {
      const res = await axios.get(`${API_URL}/visualization/snapshot`);
      setData(res.data.data);
      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch AETHER data", err);
    }
  };

  const advanceSimulation = async () => {
    try {
      setIsSimulating(true);
      const res = await axios.post(`${API_URL}/simulate/step`, { 
        stepNumber: step + 1,
        deltaTime: 60 
      });
      // Mock data returns the same snapshot structure roughly
      setData(res.data.data);
      setStep(prev => prev + 1);
    } catch (err) {
      console.error("Simulation failed", err);
    } finally {
      setIsSimulating(false);
    }
  };

  useEffect(() => {
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 10000); // Auto refresh every 10s
    return () => clearInterval(interval);
  }, []);

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

  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="main-content">
        <div className="dashboard" style={{ marginTop: '24px' }}>
          {activeTab !== '3d' && (
            <>
              <div className="dashboard-header">
                <div className="header-title">
                  <h2>Network Overview</h2>
                  <p className="subtitle">Real-time telemetry and orbital propagation</p>
                </div>
                
                <div className="simulation-controls glass-panel">
                  <div className="sim-status">
                    <span className="mono-text label">SIM STEP:</span>
                    <span className="mono-text value">{step}</span>
                  </div>
                  <button 
                    className={`btn-advance ${isSimulating ? 'simulating' : ''}`}
                    onClick={advanceSimulation}
                    disabled={isSimulating}
                  >
                    <Clock size={16} />
                    <span>{isSimulating ? 'PROPAGATING...' : 'ADVANCE +60s'}</span>
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
                    <span className="kpi-value">{data.debris?.length || 0}</span>
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
          )}

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

        {activeTab === '3d' && (
          <div className="center-column glass-panel visualizer-container" style={{ minHeight: '600px', height: 'calc(100vh - 120px)' }}>
            <div className="panel-header">
              <h3>Orbital Visualizer 3D</h3>
              <div className="panel-actions">
                <span className="badge-outline">SGP4/SDP4</span>
              </div>
            </div>
            <OrbitVisualizer satellites={data.satellites} debris={data.debris} conjunctions={data.conjunctions} />
          </div>
        )}

        {activeTab === '2d' && (
          <div className="tracker-2d-layout">
            <div className="map-section">
              <MapVisualizer satellites={data.satellites} debris={data.debris} conjunctions={data.conjunctions} />
            </div>
            <div className="radar-section">
              <RadarVisualizer satellites={data.satellites} />
            </div>
            <div className="table-section">
              <TrackerTable satellites={data.satellites} />
            </div>
            <div className="info-section glass-panel">
              <h3 className="section-title">Telemetry Stream</h3>
              <div className="chart-placeholder">
                <div className="chart-line"></div>
                <div className="chart-line secondary"></div>
              </div>
              <div className="sat-info">
                <h4>System Load</h4>
                <p className="text-muted">VHF band (144 MHz)</p>
                <div className="progress-bar"><div className="fill" style={{width: '64%'}}></div></div>
              </div>
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

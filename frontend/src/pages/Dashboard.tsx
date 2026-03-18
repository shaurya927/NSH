import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { AlertTriangle, Clock, ShieldCheck, Crosshair, Satellite } from 'lucide-react';
import FleetPanel from '../components/FleetPanel';
import ConjunctionsPanel from '../components/ConjunctionsPanel';
import OrbitVisualizer from '../components/OrbitVisualizer';
import './Dashboard.css';

const API_URL = 'http://localhost:5000/api';

const Dashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);
  const [isSimulating, setIsSimulating] = useState(false);

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
    <div className="dashboard">
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
            <span className="kpi-value glow-text status-critical">{highRiskConjunctions.length}</span>
          </div>
        </motion.div>
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">
        <div className="left-column">
          <FleetPanel satellites={data.satellites} />
        </div>
        
        <div className="center-column glass-panel visualizer-container">
          <div className="panel-header">
            <h3>Orbital Visualizer</h3>
            <div className="panel-actions">
              <span className="badge-outline">LIVE SPATIAL</span>
            </div>
          </div>
          <OrbitVisualizer satellites={data.satellites} debris={data.debris} conjunctions={data.conjunctions} />
        </div>
        
        <div className="right-column">
          <ConjunctionsPanel conjunctions={data.conjunctions} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

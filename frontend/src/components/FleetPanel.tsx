import { motion } from 'framer-motion';
import { Satellite, Activity, Battery, Hash } from 'lucide-react';
import './FleetPanel.css';

interface FleetPanelProps {
  satellites: any[];
}

const FleetPanel = ({ satellites = [] }: FleetPanelProps) => {
  return (
    <div className="fleet-panel glass-panel">
      <div className="panel-header">
        <h3>Active Constellation</h3>
        <span className="badge-outline">AETHER-PRIME</span>
      </div>
      
      <div className="fleet-list">
        {satellites.map((sat, index) => (
          <motion.div 
            initial={{ opacity: 0, x: -10 }} 
            animate={{ opacity: 1, x: 0 }} 
            transition={{ delay: index * 0.1 }}
            key={sat.id} 
            className={`sat-card status-${sat.status}`}
          >
            <div className="sat-header">
              <div className="sat-title">
                <Satellite size={16} className={`icon-${sat.status}`} />
                <h4>{sat.name}</h4>
              </div>
              <span className={`status-indicator status-${sat.status}`}></span>
            </div>
            
            <div className="sat-details">
              <div className="detail-item">
                <Hash size={12} className="text-muted" />
                <span className="mono-text">{sat.noradId ?? 'N/A'}</span>
              </div>
              <div className="detail-item">
                <Activity size={12} className="text-muted" />
                <span className="mono-text">{sat.health ?? '--'}%</span>
              </div>
              <div className="detail-item">
                <Battery size={12} className="text-muted" />
                <span className="mono-text">{sat.fuelLevel ?? '--'}%</span>
              </div>
            </div>
            
            <div className="sat-telemetry">
              <div className="telemetry-col">
                <span className="label">ALT</span>
                <span className="value mono-text">{sat.telemetry?.altitude?.toFixed(1) ?? 'N/A'} km</span>
              </div>
              <div className="telemetry-col">
                <span className="label">VEL</span>
                <span className="value mono-text">{sat.telemetry?.velocity?.vy?.toFixed(2) ?? 'N/A'} km/s</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default FleetPanel;

import { motion } from 'framer-motion';
import { AlertTriangle, Crosshair, Clock, Info, ShieldCheck } from 'lucide-react';
import './ConjunctionsPanel.css';

interface ConjunctionsPanelProps {
  conjunctions: any[];
}

const ConjunctionsPanel = ({ conjunctions = [] }: ConjunctionsPanelProps) => {
  if (!conjunctions || conjunctions.length === 0) {
    return (
      <div className="conjunctions-panel glass-panel">
        <div className="panel-header">
          <h3>Conjunction Events</h3>
          <span className="badge-outline">ALL CLEAR</span>
        </div>
        <div className="empty-state">
          <ShieldCheck size={32} className="text-muted" />
          <p>No high-risk conjunctions detected in the current screening volume.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="conjunctions-panel glass-panel alert-accent">
      <div className="panel-header alert-header">
        <h3 className="glow-text text-red">Conjunction Events</h3>
        <span className="badge-alert bg-red blink">{conjunctions.length} Warnings</span>
      </div>
      
      <div className="conjunction-list">
        {conjunctions.map((conj, index) => {
          const tca = new Date(conj.timeOfClosestApproach);
          const tcaStr = tca.toISOString().split('.')[0].replace('T', ' ') + 'Z';
          const isCritical = conj.riskLevel === 'critical' || conj.riskLevel === 'high';

          return (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }} 
              animate={{ opacity: 1, scale: 1 }} 
              transition={{ delay: index * 0.1 }}
              key={conj.id} 
              className={`conj-card risk-${conj.riskLevel}`}
            >
              <div className="conj-header">
                <div className="conj-objects">
                  <span className="obj-primary mono-text">{conj.primaryObject}</span>
                  <span className="obj-vs">VS</span>
                  <span className="obj-secondary mono-text">{conj.secondaryObject}</span>
                </div>
                {isCritical && <AlertTriangle size={16} className="text-red blink" />}
              </div>
              
              <div className="conj-metrics">
                <div className="metric">
                  <span className="label">MISS DISTANCE</span>
                  <span className={`value mono-text ${isCritical ? 'text-red glow-text' : ''}`}>
                    {conj.missDistance.toFixed(2)} km
                  </span>
                </div>
                <div className="metric">
                  <span className="label">PROBABILITY</span>
                  <span className="value mono-text">{(conj.probability * 100).toFixed(4)}%</span>
                </div>
              </div>
              
              <div className="conj-tca">
                <Clock size={14} className="text-muted" />
                <span className="label">TCA:</span>
                <span className="value mono-text">{tcaStr}</span>
              </div>
              
              <div className="conj-actions">
                <button className="btn-action">
                  <Info size={14} /> Details
                </button>
                <button className={`btn-maneuver ${isCritical ? 'primary-red' : 'primary-blue'}`}>
                  <Crosshair size={14} /> Schedule Maneuver
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
export default ConjunctionsPanel;

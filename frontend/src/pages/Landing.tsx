import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Rocket, Shield, Activity, Globe, ArrowRight } from 'lucide-react';
import './Landing.css';

const Landing = () => {
  const navigate = useNavigate();

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" as const } }
  };

  return (
    <div className="landing-page">
      {/* Background Effects */}
      <div className="landing-bg">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="grid-overlay"></div>
      </div>

      <nav className="landing-nav">
        <div className="navbar-logo">
          <Rocket className="logo-icon" size={28} color="var(--accent-blue)" />
          <div className="logo-text">
            <h1>AETHER</h1>
            <span className="logo-subtitle mono-text">SYS-CORE</span>
          </div>
        </div>
        <div className="nav-actions">
          <button className="btn-login mono-text">SYS LOGIN</button>
          <button className="btn-primary" onClick={() => navigate('/dashboard')}>
            MISSION CONTROL <ArrowRight size={16} />
          </button>
        </div>
      </nav>

      <main className="landing-content">
        <motion.section 
          className="hero-section"
          initial="hidden"
          animate="visible"
          variants={containerVariants}
        >
          <motion.div className="badge-pill mono-text" variants={itemVariants}>
            <span className="live-dot"></span> LIVE TELEMETRY V1.0 ECI
          </motion.div>
          
          <motion.h1 className="hero-title" variants={itemVariants}>
            Autonomous Space<br/>
            <span className="text-gradient">Constellation Management</span>
          </motion.h1>
          
          <motion.p className="hero-subtitle" variants={itemVariants}>
            Real-time orbital propagation, collision avoidance, and fleet telemetry for the next generation of satellite networks and deep space ops.
          </motion.p>
          
          <motion.div className="hero-actions" variants={itemVariants}>
            <button className="btn-primary large" onClick={() => navigate('/dashboard')}>
              INITIALIZE DASHBOARD
            </button>
            <button className="btn-secondary large">
              VIEW DOCS
            </button>
          </motion.div>
        </motion.section>

        <motion.section 
          className="features-grid"
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.8 }}
        >
          <div className="feature-card glass-panel">
            <div className="feature-icon bg-cyan">
              <Activity size={24} />
            </div>
            <h3>Real-Time Telemetry</h3>
            <p>Monitor your entire fleet's health, fuel reserves, and operational status in a centralized, ultra-low latency dashboard.</p>
          </div>
          
          <div className="feature-card glass-panel">
            <div className="feature-icon bg-red">
              <Shield size={24} />
            </div>
            <h3>Conjunction Screening</h3>
            <p>Advanced SGP4/SDP4 orbital propagation detects potential collisions with space debris or other assets days in advance.</p>
          </div>
          
          <div className="feature-card glass-panel">
            <div className="feature-icon bg-blue">
              <Globe size={24} />
            </div>
            <h3>Spatial Visualizer</h3>
            <p>Interactive, dynamic pseudo-3D canvas plotting orbits, satellite positions, and debris fields with millimeter precision.</p>
          </div>
        </motion.section>
      </main>
    </div>
  );
};

export default Landing;

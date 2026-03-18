import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Satellite, ShieldAlert, Rocket, Activity, Box, Map } from 'lucide-react';
import './Navbar.css';

interface NavbarProps {
  activeTab?: 'info' | '3d' | '2d';
  onTabChange?: (tab: 'info' | '3d' | '2d') => void;
}

const Navbar = ({ activeTab = 'info', onTabChange = () => {} }: NavbarProps) => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <nav className="navbar glass-panel">
      <Link to="/" className="navbar-logo" style={{ textDecoration: 'none', color: 'inherit' }}>
        <Rocket className="logo-icon" size={28} color="var(--accent-blue)" />
        <div className="logo-text">
          <h1>AETHER</h1>
          <span className="logo-subtitle mono-text">MISSION CONTROL</span>
        </div>
      </Link>

      <div className="navbar-links">
        <div className={`nav-item ${activeTab === 'info' ? 'active' : ''}`} onClick={() => onTabChange('info')} style={{ cursor: 'pointer' }}>
          <Activity size={18} />
          <span>Dashboard</span>
        </div>
        <div className={`nav-item ${activeTab === '3d' ? 'active' : ''}`} onClick={() => onTabChange('3d')} style={{ cursor: 'pointer' }}>
          <Box size={18} />
          <span>3D Model</span>
        </div>
        <div className={`nav-item ${activeTab === '2d' ? 'active' : ''}`} onClick={() => onTabChange('2d')} style={{ cursor: 'pointer' }}>
          <Map size={18} />
          <span>2D Map</span>
        </div>
      </div>

      <div className="navbar-status">
        <div className="status-item">
          <span className="status-label mono-text">SYS:</span>
          <span className="status-indicator status-nominal"></span>
          <span className="status-value status-nominal">ONLINE</span>
        </div>
        <div className="status-item timer-item mono-text">
          T: {time.toISOString().split('T')[1].split('.')[0]}Z
        </div>
      </div>
    </nav>
  );
};

export default Navbar;

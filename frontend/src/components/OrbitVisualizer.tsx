import { useEffect, useRef } from 'react';

import './OrbitVisualizer.css';

interface OrbitVisualizerProps {
  satellites: any[];
  debris: any[];
  conjunctions: any[];
}

const OrbitVisualizer = ({ satellites = [], debris = [], conjunctions = [] }: OrbitVisualizerProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    
    ctx.scale(dpr, dpr);
    
    // Center logic
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    
    // Animation loop
    let animationId: number;
    let time = 0;

    // Pre-calculate sizes
    const earthRadius = Math.min(rect.width, rect.height) * 0.15;

    // Pre-calculated orbital paths for visual layout (pseudo-3D)
    const orbits = [
      { rx: earthRadius * 1.5, ry: earthRadius * 0.4, angle: 0.2 },
      { rx: earthRadius * 1.8, ry: earthRadius * 0.6, angle: -0.4 },
      { rx: earthRadius * 2.2, ry: earthRadius * 0.7, angle: 0.8 },
      { rx: earthRadius * 1.6, ry: earthRadius * 1.4, angle: 1.2 },
      { rx: earthRadius * 2.5, ry: earthRadius * 0.5, angle: -0.8 },
      { rx: earthRadius * 2.0, ry: earthRadius * 1.8, angle: 0.1 },
    ];

    const draw = () => {
      ctx.clearRect(0, 0, rect.width, rect.height);
      time += 0.005;

      // Draw Earth (glow & globe)
      
      const glow = ctx.createRadialGradient(cx, cy, earthRadius * 0.8, cx, cy, earthRadius * 2);
      glow.addColorStop(0, 'rgba(6, 182, 212, 0.2)');
      glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius * 2, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      // Earth gradient
      const gradient = ctx.createLinearGradient(cx - earthRadius, cy - earthRadius, cx + earthRadius, cy + earthRadius);
      gradient.addColorStop(0, '#1e3a8a'); // dark blue
      gradient.addColorStop(1, '#0f172a'); // darker
      
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.6)';
      ctx.stroke();

      // Draw wireframe grid on Earth
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.15)';
      ctx.lineWidth = 1;
      for (let i = -3; i <= 3; i++) {
        ctx.beginPath();
        ctx.ellipse(cx, cy, earthRadius, earthRadius * (Math.abs(i) / 3), 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw Orbits
      orbits.forEach(orbit => {
        ctx.beginPath();
        ctx.ellipse(cx, cy, orbit.rx, orbit.ry, orbit.angle, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        ctx.stroke();
      });

      // Draw Satellites
      satellites.forEach((sat, i) => {
        const orbit = orbits[i % orbits.length];
        const t = time * (1.5 - (i * 0.1)) + (i * 1.5); // Spread them out
        
        const x = cx + orbit.rx * Math.cos(t) * Math.cos(orbit.angle) - orbit.ry * Math.sin(t) * Math.sin(orbit.angle);
        const y = cy + orbit.rx * Math.cos(t) * Math.sin(orbit.angle) + orbit.ry * Math.sin(t) * Math.cos(orbit.angle);
        
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        
        if (sat.status === 'critical') ctx.fillStyle = '#ef4444';
        else if (sat.status === 'warning') ctx.fillStyle = '#f59e0b';
        else ctx.fillStyle = '#10b981';
        
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.8)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label
        ctx.font = '10px JetBrains Mono';
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.fillText(sat.name.split('-')[1] || sat.name, x + 8, y + 4);
      });

      // Draw Debris
      debris.forEach((deb, i) => {
        const j = i + 3; 
        const orbit = orbits[j % orbits.length];
        const t = -time * (2 - (i * 0.2)) + (i * 2.5); // Retrograde mostly
        
        const x = cx + orbit.rx * Math.cos(t) * Math.cos(orbit.angle) - orbit.ry * Math.sin(t) * Math.sin(orbit.angle);
        const y = cy + orbit.rx * Math.cos(t) * Math.sin(orbit.angle) + orbit.ry * Math.sin(t) * Math.cos(orbit.angle);
        
        ctx.beginPath();
        ctx.rect(x - 2, y - 2, 4, 4);
        ctx.fillStyle = '#94a3b8';
        ctx.fill();
        
        if (deb.riskLevel === 'high' || deb.riskLevel === 'critical') {
           ctx.beginPath();
           ctx.arc(x, y, 8 + Math.sin(time*10)*2, 0, Math.PI * 2);
           ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)';
           ctx.stroke();
        }
      });

      animationId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [satellites, debris, conjunctions]);

  return (
    <div className="orbit-visualizer">
      <canvas ref={canvasRef} className="orbit-canvas" />
      
      <div className="telemetry-overlay">
        <div className="target-reticle">
          <div className="crosshair-x"></div>
          <div className="crosshair-y"></div>
        </div>
        
        <div className="data-box top-left glass-panel">
          <span className="mono-text label">ORBITAL PROPAGATOR</span>
          <span className="mono-text value">SGP4/SDP4</span>
        </div>
        
        <div className="data-box bottom-right glass-panel">
          <span className="mono-text label">FRAME</span>
          <span className="mono-text value">J2000 (ECI)</span>
        </div>
      </div>
    </div>
  );
};
export default OrbitVisualizer;

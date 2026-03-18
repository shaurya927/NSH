import { useEffect, useRef } from 'react';
import './RadarVisualizer.css';

interface RadarVisualizerProps {
  satellites: any[];
}

const RadarVisualizer = ({ satellites = [] }: RadarVisualizerProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const r = Math.min(cx, cy) * 0.8;

    const draw = () => {
      ctx.clearRect(0, 0, rect.width, rect.height);

      // Draw Radar Circles
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.lineWidth = 1;

      for (let i = 1; i <= 3; i++) {
        ctx.beginPath();
        ctx.arc(cx, cy, r * (i / 3), 0, Math.PI * 2);
        ctx.stroke();
      }

      // Crosshairs
      ctx.beginPath(); ctx.moveTo(cx - r, cy); ctx.lineTo(cx + r, cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy + r); ctx.stroke();

      // Labels (N, S, E, W)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.font = '10px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('N', cx, cy - r - 10);
      ctx.fillText('S', cx, cy + r + 10);
      ctx.fillText('W', cx - r - 10, cy);
      ctx.fillText('E', cx + r + 10, cy);

      // Plot actual satellite positions (Map entire global space directly to radar disk for demo)
      satellites.slice(0, 8).forEach((sat) => {
        const lat = sat.telemetry?.latitude || 0;
        let lon = sat.telemetry?.longitude || 0;
        
        // Wrap lon relative to map center 0
        if (lon > 180) lon -= 360;
        
        const distDeg = Math.sqrt(lat*lat + lon*lon);
        // Normalize against max range (e.g. 180deg full earth)
        const maxDeg = 180;
        
        if (distDeg < maxDeg) {
          const radarR = r * (distDeg / maxDeg);
          // Angle on radar based on lat/lon
          const angle = Math.atan2(lat, lon); // lat is y, lon is x
          
          const x = cx + Math.cos(angle) * radarR;
          const y = cy - Math.sin(angle) * radarR; // invert y

          // Dot
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = sat.status === 'critical' ? '#ef4444' : sat.status === 'warning' ? '#f59e0b' : '#10b981';
          ctx.fill();

          // Info Box near point
          ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
          ctx.fillRect(x + 10, y - 10, 80, 45);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.strokeRect(x + 10, y - 10, 80, 45);
          ctx.fillStyle = '#fff';
          ctx.textAlign = 'left';
          ctx.fillText(sat.name, x + 15, y + 2);
          ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
          ctx.fillText(`Lat: ${lat.toFixed(1)}°`, x + 15, y + 14);
          ctx.fillText(`Lon: ${lon.toFixed(1)}°`, x + 15, y + 26);
        }
      });
    };

    draw();
    return () => {};
  }, [satellites]);

  return (
    <div className="radar-visualizer glass-panel h-full w-full">
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  );
};

export default RadarVisualizer;

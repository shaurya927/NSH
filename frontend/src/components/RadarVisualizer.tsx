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

    let animationId: number;
    let time = 0;

    const draw = () => {
      ctx.clearRect(0, 0, rect.width, rect.height);
      time += 0.01;

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

      // Plot dummy satellite passes
      satellites.slice(0, 3).forEach((sat, i) => {
        // Parametric path for an overhead pass
        const phase = i * Math.PI / 2;
        const passDuration = 400; // frames
        const t = (time * 50 + phase * 100) % passDuration;
        
        if (t > 0 && t < passDuration) {
          // Calculate Az/El roughly mapped to polar coords
          const progress = t / passDuration;
          const az = phase + (progress * Math.PI / 2); // azimuth sweeps
          const el = Math.sin(progress * Math.PI) * (Math.PI / 2); // elevation goes 0 -> max -> 0
          
          // Map elevation to radius (90 deg = center, 0 deg = edge)
          const dist = r * (1 - (el / (Math.PI / 2)));
          
          const x = cx + Math.sin(az) * dist;
          const y = cy - Math.cos(az) * dist;

          // Trail
          ctx.beginPath();
          for (let pt = 0; pt < t; pt += 5) {
            const prog = pt / passDuration;
            const a = phase + (prog * Math.PI / 2);
            const e = Math.sin(prog * Math.PI) * (Math.PI / 2);
            const d = r * (1 - (e / (Math.PI / 2)));
            const px = cx + Math.sin(a) * d;
            const py = cy - Math.cos(a) * d;
            if (pt === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.strokeStyle = i === 0 ? 'rgba(217, 70, 239, 0.6)' : 'rgba(56, 189, 248, 0.6)';
          ctx.stroke();

          // Dot
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = i === 0 ? '#d946ef' : '#38bdf8';
          ctx.fill();

          // Info Box near point
          if (progress > 0.4 && progress < 0.6) {
             ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
             ctx.fillRect(x + 10, y - 10, 80, 45);
             ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
             ctx.strokeRect(x + 10, y - 10, 80, 45);
             ctx.fillStyle = '#fff';
             ctx.textAlign = 'left';
             ctx.fillText(sat.name, x + 15, y + 2);
             ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
             ctx.fillText(`Az: ${(az * 180 / Math.PI).toFixed(1)}°`, x + 15, y + 14);
             ctx.fillText(`El: ${(el * 180 / Math.PI).toFixed(1)}°`, x + 15, y + 26);
          }
        }
      });

      animationId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animationId);
  }, [satellites]);

  return (
    <div className="radar-visualizer glass-panel h-full w-full">
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  );
};

export default RadarVisualizer;

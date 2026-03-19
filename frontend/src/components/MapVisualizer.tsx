import { useMemo } from 'react';
import { MapContainer, TileLayer, Circle, Marker, Polyline, Tooltip, LayerGroup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MapVisualizer.css';
import Terminator from './Terminator';

// Fix typical leaflet generic icon issues
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

interface MapVisualizerProps {
  satellites: any[];
  debris: any[];
  conjunctions: any[];
  timestamp?: string;
}

const customIcon = (color: string) => new L.DivIcon({
  className: 'custom-div-icon',
  html: `<div style="background-color:${color}; width:8px; height:8px; border-radius:50%; border:2px solid white; box-shadow: 0 0 8px ${color}"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6]
});

const MapVisualizer = ({ satellites = [], debris: _debris = [], timestamp }: MapVisualizerProps) => {
  // Use real data from the Backend/Engine instead of a mocked timer
  const liveSatellites = useMemo(() => {
    return satellites.map((sat) => {
      const lat = sat.telemetry?.latitude || 0;
      const lng = sat.telemetry?.longitude || 0;
      
      const color = sat.status === 'critical' ? '#ef4444' : sat.status === 'warning' ? '#f59e0b' : '#10b981';
      const altitude = sat.telemetry?.altitude || 400;
      const footprintRadius = 800000 + (altitude * 200); 
      
      const trail: [number, number][] = [];

      return {
        ...sat,
        lat,
        lng,
        color,
        footprintRadius,
        trail
      };
    });
  }, [satellites]);

  return (
    <div className="map-visualizer">
      <MapContainer 
        center={[20, 0]} 
        zoom={2.5} 
        minZoom={2}
        zoomSnap={0}
        maxBounds={[[-90, -Infinity], [90, Infinity]]}
        worldCopyJump={true}
        style={{ height: '100%', width: '100%', background: '#0a0a0c' }}
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        
        <Terminator timestamp={timestamp} />
        
        {liveSatellites.map((sat, i) => (
          <LayerGroup key={`satGroup-${i}`}>
            <Circle 
              center={[sat.lat, sat.lng]} 
              radius={sat.footprintRadius}
              pathOptions={{
                color: sat.color, 
                fillColor: sat.color, 
                fillOpacity: 0.1, 
                weight: 1, 
                opacity: 0.5 
              }}
            />
            {sat.trail.length > 0 && (
              <Polyline 
                positions={sat.trail} 
                pathOptions={{ color: 'white', weight: 1, opacity: 0.3 }} 
              />
            )}
            <Marker position={[sat.lat, sat.lng]} icon={customIcon(sat.color)}>
              <Tooltip direction="right" offset={[10, 0]} opacity={0.8} permanent>
                <div style={{fontFamily: 'monospace', fontSize: '10px'}}>{sat.name}</div>
              </Tooltip>
            </Marker>
          </LayerGroup>
        ))}
      </MapContainer>
      
      <div className="telemetry-overlay" style={{ pointerEvents: 'none' }}>
        <div className="data-box top-left glass-panel" style={{ pointerEvents: 'auto' }}>
          <span className="mono-text label">PROJECTION</span>
          <span className="mono-text value">INTERACTIVE MERCATOR</span>
        </div>
      </div>
    </div>
  );
};
export default MapVisualizer;

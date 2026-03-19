import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
// @ts-ignore - leaflet-terminator may lack type definitions
import terminator from 'leaflet-terminator';

const Terminator = ({ timestamp }: { timestamp?: string }) => {
  const map = useMap();
  const tRef = useRef<any>(null);

  useEffect(() => {
    const t = terminator();
    t.setStyle({
      fillOpacity: 0.45,
      fillColor: '#000000',
      color: 'transparent',
      interactive: false,
    });
    
    t.addTo(map);
    tRef.current = t;

    return () => {
      map.removeLayer(t);
    };
  }, [map]);

  useEffect(() => {
    if (tRef.current) {
      let d = new Date();
      if (timestamp) {
        const parsed = new Date(timestamp);
        if (!isNaN(parsed.getTime())) {
          d = parsed;
        }
      }
      tRef.current.setDate(d);
    }
  }, [timestamp]);

  return null;
};

export default Terminator;

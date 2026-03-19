import { useRef, useMemo, Suspense, useState, useEffect } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import './OrbitVisualizer.css';

interface OrbitVisualizerProps {
  satellites: any[];
  debris: any[];
  conjunctions: any[];
  minimal?: boolean;
  fullscreen?: boolean;
}

const EarthGlobe = () => {
  const groupRef = useRef<THREE.Group>(null);
  const [colorMap] = useLoader(THREE.TextureLoader, [
    'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg'
  ]);

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.rotation.y += 0.002; // Sidereal rotation
    }
  });

  return (
    <group ref={groupRef} rotation={[0.4, 0, 0]}>
      {/* Outer Atmosphere Glow */}
      <mesh>
        <sphereGeometry args={[2.05, 32, 32]} />
        <meshBasicMaterial color="#0ea5e9" transparent opacity={0.15} side={THREE.BackSide} />
      </mesh>
      
      {/* Core Photorealistic Globe */}
      <mesh>
        <sphereGeometry args={[2, 64, 64]} />
        <meshStandardMaterial map={colorMap} roughness={0.6} metalness={0.1} />
      </mesh>
    </group>
  );
};

const StarfieldEnvironment = () => {
  const [starMap] = useLoader(THREE.TextureLoader, [
    'https://unpkg.com/three-globe/example/img/night-sky.png'
  ]);
  
  return (
    <mesh>
      <sphereGeometry args={[100, 64, 64]} />
      <meshBasicMaterial map={starMap} side={THREE.BackSide} depthWrite={false} color="#aaaaaa" />
    </mesh>
  );
};

const Sun = () => {
  const coreRef = useRef<THREE.Mesh>(null);
  const coronaRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  const [sunMap] = useLoader(THREE.TextureLoader, ['/sun.jpg']);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (coreRef.current) {
      coreRef.current.rotation.y = t * 0.05; // slowly rotate the texture
    }
    if (coronaRef.current) {
      const scale1 = 1 + Math.sin(t * 2) * 0.015;
      coronaRef.current.scale.set(scale1, scale1, scale1);
    }
    if (glowRef.current) {
      const scale2 = 1 + Math.sin(t * 1.5) * 0.025;
      glowRef.current.scale.set(scale2, scale2, scale2);
    }
  });

  return (
    <group position={[40, 5, 25]}>
      {/* Sun Core with NASA Texture */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[3, 64, 64]} />
        <meshBasicMaterial 
          map={sunMap} 
          toneMapped={false}
          color={[1.5, 1.5, 1.5]}
        />
      </mesh>
      
      {/* Inner Corona (Bright Yellow pulse) */}
      <mesh ref={coronaRef}>
        <sphereGeometry args={[3.3, 32, 32]} />
        <meshBasicMaterial 
          color={[2.0, 0.8, 0.2]} 
          toneMapped={false}
          transparent 
          opacity={0.3} 
          blending={THREE.AdditiveBlending} 
          depthWrite={false} 
        />
      </mesh>

      {/* Outer Glow (Deep Red/Orange) */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[4.5, 32, 32]} />
        <meshBasicMaterial 
          color={[1.5, 0.4, 0.0]} 
          toneMapped={false}
          transparent 
          opacity={0.15} 
          blending={THREE.AdditiveBlending} 
          depthWrite={false} 
        />
      </mesh>
      
      {/* Super massive faint solar atmosphere */}
      <mesh>
        <sphereGeometry args={[8, 32, 32]} />
        <meshBasicMaterial 
          color="#fb923c" 
          transparent 
          opacity={0.05} 
          blending={THREE.AdditiveBlending} 
          depthWrite={false} 
        />
      </mesh>
      
      {/* Primary directional illumination */}
      <pointLight intensity={800} color="#fffbeb" distance={400} decay={1.5} />
    </group>
  );
};

const Moon = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const [moonMap] = useLoader(THREE.TextureLoader, [
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/moon_1024.jpg'
  ]);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const t = clock.getElapsedTime() * 0.05; // Very slow orbit
    const distance = 14; 
    
    meshRef.current.position.set(Math.cos(t) * distance, Math.sin(t * 0.2) * 2, Math.sin(t) * distance);
    meshRef.current.rotation.y += 0.005; // Slightly faster moon rotation so user can notice it
  });

  return (
    <group>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.55, 32, 32]} />
        <meshStandardMaterial map={moonMap} roughness={0.9} metalness={0.1} />
      </mesh>
    </group>
  );
};

const SatelliteNode = ({ satellite, orbit, onSelect }: { satellite: any, orbit: any, onSelect: (s: any) => void }) => {
  const groupRef = useRef<THREE.Group>(null);
  const color = satellite.status === 'critical' ? '#ef4444' : satellite.status === 'warning' ? '#f59e0b' : '#10b981';

  useFrame(() => {
    if (!groupRef.current) return;
    
    // Map engine lat/lon to 3D sphere coordinate
    const latRad = (satellite.telemetry?.latitude || 0) * (Math.PI / 180);
    const lonRad = (satellite.telemetry?.longitude || 0) * (Math.PI / 180);
    const radius = orbit.radius || 3.3; 
    
    // Spherical to Cartesian (Y-up standard)
    const targetX = radius * Math.cos(latRad) * Math.cos(lonRad);
    const targetY = radius * Math.sin(latRad);
    const targetZ = radius * -Math.cos(latRad) * Math.sin(lonRad); 

    // Smoothly fly to target when sim ticks
    groupRef.current.position.lerp(new THREE.Vector3(targetX, targetY, targetZ), 0.1);
    
    // Orient the satellite so it faces the Earth (0, 0, 0)
    // Three.js lookAt points the local -Z axis towards the target
    groupRef.current.lookAt(0, 0, 0);
  });

  return (
    <group 
      ref={groupRef}
      onClick={(e) => { e.stopPropagation(); onSelect(satellite); }}
      onPointerOver={() => document.body.style.cursor = 'pointer'}
      onPointerOut={() => document.body.style.cursor = 'default'}
    >
      {/* Invisible Interactive Hitbox to make clicking easy */}
      <mesh>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} color="white" />
      </mesh>

      {/* Central Body */}
      <mesh>
        <boxGeometry args={[0.04, 0.04, 0.04]} />
        <meshStandardMaterial color={color} metalness={0.7} roughness={0.2} />
      </mesh>
      
      {/* Solar Panel Left */}
      <mesh position={[-0.06, 0, 0]}>
        <boxGeometry args={[0.06, 0.002, 0.03]} />
        <meshStandardMaterial color="#1d4ed8" metalness={0.9} roughness={0.1} />
      </mesh>
      
      {/* Solar Panel Right */}
      <mesh position={[0.06, 0, 0]}>
        <boxGeometry args={[0.06, 0.002, 0.03]} />
        <meshStandardMaterial color="#1d4ed8" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Antenna / Payload pointing to Earth (local -Z) */}
      <mesh position={[0, 0, -0.03]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.005, 0.01, 0.02]} />
        <meshStandardMaterial color="#cbd5e1" metalness={0.6} roughness={0.4} />
      </mesh>

      <Html center zIndexRange={[100, 0]}>
        <div 
          onClick={(e) => { e.stopPropagation(); onSelect(satellite); }}
          style={{ 
            color: 'white', fontFamily: 'var(--font-mono)', fontSize: '10px', 
            background: 'rgba(10,10,12,0.8)', padding: '2px 6px', 
            borderRadius: '4px', border: `1px solid ${color}`,
            pointerEvents: 'auto', cursor: 'pointer', whiteSpace: 'nowrap',
            marginTop: '25px'
          }}>
           {satellite.name}
        </div>
      </Html>
    </group>
  );
};

const DebrisNode = ({ debris: deb, orbit }: { debris: any, orbit: any }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame(() => {
    if (!meshRef.current) return;
    
    const latRad = (deb.latitude || 0) * (Math.PI / 180);
    const lonRad = (deb.longitude || 0) * (Math.PI / 180);
    const radius = orbit.radius || 4.2;
    
    // Spherical to Cartesian (Y-up standard)
    const targetX = radius * Math.cos(latRad) * Math.cos(lonRad);
    const targetY = radius * Math.sin(latRad);
    const targetZ = radius * -Math.cos(latRad) * Math.sin(lonRad);

    // Smoothly fly to target when sim ticks
    meshRef.current.position.lerp(new THREE.Vector3(targetX, targetY, targetZ), 0.1);
  });

  return (
    <group>
      <mesh ref={meshRef}>
        <boxGeometry args={[0.05, 0.05, 0.05]} />
        <meshBasicMaterial color="#64748b" />
      </mesh>
    </group>
  );
};

const OrbitVisualizer = ({ satellites = [], debris = [], minimal = false, fullscreen = false }: OrbitVisualizerProps) => {
  const [selectedSat, setSelectedSat] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  // Keep selected panel updated across sim ticks
  useEffect(() => {
    if (selectedSat) {
      const updated = satellites.find(s => s.id === selectedSat.id);
      if (updated) setSelectedSat(updated);
    }
  }, [satellites, selectedSat]);

  // Precompute orbits safely
  const satelliteOrbits = useMemo(() => [
    { radius: 3.2, tiltX: 0.2, tiltZ: 0.5 },
    { radius: 3.5, tiltX: -0.4, tiltZ: 0.1 },
    { radius: 3.9, tiltX: 0.8, tiltZ: -0.3 },
    { radius: 3.4, tiltX: 1.2, tiltZ: 0.7 },
    { radius: 4.2, tiltX: -0.8, tiltZ: -0.5 },
    { radius: 3.7, tiltX: 0.1, tiltZ: 0.9 },
  ], []);

  const debrisOrbits = useMemo(() => [
    { radius: 3.3, tiltX: -0.5, tiltZ: 0.8 },
    { radius: 4.0, tiltX: 0.9, tiltZ: -0.1 },
    { radius: 3.6, tiltX: 0.3, tiltZ: -0.7 },
    { radius: 4.5, tiltX: -0.2, tiltZ: 0.4 },
  ], []);

  return (
    <div className={`orbit-visualizer ${fullscreen ? 'fullscreen' : ''}`} style={{ width: '100%', height: '100%', minHeight: fullscreen ? 0 : '600px', position: 'relative' }}>
      
      {/* Search Bar Overlay */}
      {!minimal && (
        <div style={{ position: 'absolute', top: '24px', left: '50%', transform: 'translateX(-50%)', zIndex: 20, width: '300px', pointerEvents: 'auto' }}>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="Search satellites..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              style={{
                width: '100%', padding: '10px 16px', borderRadius: '8px',
                background: 'rgba(10,12,16,0.85)', border: '1px solid rgba(255,255,255,0.2)',
                color: 'white', fontFamily: 'var(--font-mono)', fontSize: '14px', outline: 'none',
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)', boxSizing: 'border-box'
              }}
            />
            {showDropdown && searchQuery && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, width: '100%', marginTop: '8px',
                background: 'rgba(10,12,16,0.95)', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px', maxHeight: '200px', overflowY: 'auto',
                boxShadow: '0 10px 25px rgba(0,0,0,0.7)', padding: '4px', boxSizing: 'border-box'
              }}>
                {satellites.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase())).length > 0 ? (
                  satellites.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase())).map((sat, i) => (
                    <div
                      key={sat.id || i}
                      onClick={() => {
                        setSelectedSat(sat);
                        setSearchQuery('');
                        setShowDropdown(false);
                      }}
                      style={{
                        padding: '10px 12px', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: '13px',
                        color: sat.status === 'nominal' ? '#10b981' : sat.status === 'warning' ? '#f59e0b' : '#ef4444',
                        borderBottom: '1px solid rgba(255,255,255,0.05)'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      {sat.name}
                    </div>
                  ))
                ) : (
                  <div style={{ padding: '10px', color: '#64748b', fontSize: '12px', textAlign: 'center' }}>No matches found</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <Canvas className="orbit-canvas" camera={{ position: [0, 2, 8], fov: 45 }}>
        <color attach="background" args={['#0a0a0c']} />
        <ambientLight intensity={0.05} />
        
        <EffectComposer enableNormalPass={false}>
          <Bloom luminanceThreshold={1} mipmapBlur intensity={1.5} />
        </EffectComposer>

        <OrbitControls enablePan={true} enableZoom={true} minDistance={3} maxDistance={40} />
        
        <Suspense fallback={null}>
          <StarfieldEnvironment />
          <Sun />
          <EarthGlobe />
          <Moon />
        </Suspense>
        
        {satellites.map((sat, i) => (
          <SatelliteNode key={`sat-${i}`} satellite={sat} orbit={satelliteOrbits[i % satelliteOrbits.length]} onSelect={setSelectedSat} />
        ))}
        {debris.map((deb, i) => (
          <DebrisNode key={`deb-${i}`} debris={deb} orbit={debrisOrbits[i % debrisOrbits.length]} />
        ))}
      </Canvas>
      
      {!minimal && (
        <div className="telemetry-overlay" style={{ pointerEvents: 'none' }}>
          <div className="data-box top-left glass-panel" style={{ pointerEvents: 'auto' }}>
            <span className="mono-text label">ORBITAL PROPAGATOR</span>
            <span className="mono-text value">THREE.JS WEBGL</span>
          </div>
          
          <div className="data-box bottom-right glass-panel" style={{ pointerEvents: 'auto' }}>
            <span className="mono-text label">INTERACTION</span>
            <span className="mono-text value">ALT-DRAG ROTATE</span>
          </div>
        </div>
      )}

      {selectedSat && (
        <div className="satellite-info-panel glass-panel" style={{
          position: 'absolute', top: '50%', left: '24px', transform: 'translateY(-50%)',
          width: '360px', pointerEvents: 'auto', zIndex: 10,
          background: 'rgba(10,12,16,0.95)', border: `1px solid ${selectedSat.status === 'nominal' ? '#10b981' : selectedSat.status === 'warning' ? '#f59e0b' : '#ef4444'}`,
          borderRadius: '8px', padding: '20px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
            <h3 style={{ margin: 0, color: '#0ea5e9', fontFamily: 'var(--font-mono)', fontSize: '16px', textTransform: 'uppercase', letterSpacing: '1px', paddingRight: '12px', wordBreak: 'break-word' }}>
              {selectedSat.name}
            </h3>
            <button onClick={() => setSelectedSat(null)} style={{ background: 'transparent', border: 'none', color: '#e2e8f0', cursor: 'pointer', fontSize: '24px', padding: '0 4px', lineHeight: '1',  marginTop: '-4px' }}>
              &times;
            </button>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(100px, max-content) 1fr', gap: '14px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
            <span style={{ color: '#94a3b8' }}>OBJ ID:</span>
            <span style={{ color: '#e2e8f0', textAlign: 'right' }}>#{selectedSat.noradId || 'UNKNOWN'}</span>
            
            <span style={{ color: '#94a3b8' }}>STATUS:</span>
            <span style={{ color: selectedSat.status === 'nominal' ? '#10b981' : selectedSat.status === 'warning' ? '#f59e0b' : '#ef4444', textAlign: 'right', fontWeight: 'bold' }}>
              {String(selectedSat.status).toUpperCase()}
            </span>

            <span style={{ color: '#94a3b8' }}>ALTITUDE:</span>
            <span style={{ color: '#e2e8f0', textAlign: 'right' }}>{selectedSat.telemetry?.altitude?.toFixed(2) || '---'} km</span>
            
            <span style={{ color: '#94a3b8' }}>VELOCITY:</span>
            <span style={{ color: '#e2e8f0', textAlign: 'right' }}>{selectedSat.telemetry?.velocity?.vy?.toFixed(3) || '---'} km/s</span>
            
            <span style={{ color: '#94a3b8' }}>INCLINATION:</span>
            <span style={{ color: '#e2e8f0', textAlign: 'right' }}>{selectedSat.telemetry?.inclination?.toFixed(2) || '---'}°</span>
            
            <span style={{ color: '#94a3b8' }}>ECCENTRICITY:</span>
            <span style={{ color: '#e2e8f0', textAlign: 'right' }}>{selectedSat.telemetry?.eccentricity?.toFixed(6) || '---'}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrbitVisualizer;

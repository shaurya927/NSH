import { useRef, useMemo, Suspense } from 'react';
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
        <Html distanceFactor={25} center>
          <div style={{ color: '#94a3b8', fontFamily: 'var(--font-mono)', fontSize: '8px', pointerEvents: 'none' }}>
            LUNA
          </div>
        </Html>
      </mesh>
      
      {/* Faint lunar orbit ring */}
      <mesh rotation={[Math.PI / 2, -0.15, 0]}>
         <ringGeometry args={[13.98, 14.02, 128]} />
         <meshBasicMaterial color="white" transparent opacity={0.03} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
};

const SatelliteNode = ({ satellite, orbit, index }: { satellite: any, orbit: any, index: number }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = satellite.status === 'critical' ? '#ef4444' : satellite.status === 'warning' ? '#f59e0b' : '#10b981';

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const time = clock.getElapsedTime() * 0.5;
    const t = time * (1.5 - (index * 0.1)) + (index * 1.5);
    
    // Orbital propagation along X-Z plane
    const x = Math.cos(t) * orbit.radius;
    const z = Math.sin(t) * orbit.radius;
    meshRef.current.position.set(x, 0, z);
  });

  return (
    <group rotation={[orbit.tiltX, 0, orbit.tiltZ]}>
      {/* The moving satellite */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color={color} />
        {/* HTML UI overlaid on the 3D position */}
        <Html center zIndexRange={[100, 0]}>
          <div style={{ 
            color: 'white', fontFamily: 'var(--font-mono)', fontSize: '10px', 
            background: 'rgba(10,10,12,0.8)', padding: '2px 6px', 
            borderRadius: '4px', border: `1px solid ${color}`,
            pointerEvents: 'none', whiteSpace: 'nowrap'
          }}>
             {satellite.name}
          </div>
        </Html>
      </mesh>
      
      {/* The static orbital ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
         <ringGeometry args={[orbit.radius, orbit.radius + 0.015, 64]} />
         <meshBasicMaterial color="white" transparent opacity={0.05} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
};

const DebrisNode = ({ debris: _debris, orbit, index }: { debris: any, orbit: any, index: number }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const time = clock.getElapsedTime() * 0.3;
    const t = -time * (2 - (index * 0.2)) + (index * 2.5); // retrograde
    
    const x = Math.cos(t) * orbit.radius;
    const z = Math.sin(t) * orbit.radius;
    meshRef.current.position.set(x, 0, z);
  });

  return (
    <group rotation={[orbit.tiltX, 0, orbit.tiltZ]}>
      <mesh ref={meshRef}>
        <boxGeometry args={[0.05, 0.05, 0.05]} />
        <meshBasicMaterial color="#64748b" />
      </mesh>
    </group>
  );
};

const OrbitVisualizer = ({ satellites = [], debris = [], minimal = false, fullscreen = false }: OrbitVisualizerProps) => {
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
      <Canvas className="orbit-canvas" camera={{ position: [0, 2, 8], fov: 45 }}>
        <color attach="background" args={['#0a0a0c']} />
        <ambientLight intensity={0.05} />
        
        <EffectComposer disableNormalPass>
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
          <SatelliteNode key={`sat-${i}`} satellite={sat} orbit={satelliteOrbits[i % satelliteOrbits.length]} index={i} />
        ))}
        {debris.map((deb, i) => (
          <DebrisNode key={`deb-${i}`} debris={deb} orbit={debrisOrbits[i % debrisOrbits.length]} index={i} />
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
    </div>
  );
};

export default OrbitVisualizer;

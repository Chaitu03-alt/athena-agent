import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export type OrbState = 'idle' | 'thinking' | 'calling_tool' | 'speaking' | 'listening';

interface ParticleOrbProps {
  state?: OrbState | string;
  className?: string;
  size?: number;
  interactive?: boolean;
}

// Generate circular soft glow particle texture in memory
function createGlowPointTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1.0)');
    gradient.addColorStop(0.2, 'rgba(0, 240, 255, 0.85)');
    gradient.addColorStop(0.5, 'rgba(0, 255, 102, 0.4)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0.0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export const ParticleOrb: React.FC<ParticleOrbProps> = ({
  state = 'idle',
  className = '',
  size = 320,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef(state);

  // Keep stateRef up to date for the requestAnimationFrame loop
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || size;
    const height = container.clientHeight || size;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.z = 240;

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const pointTexture = createGlowPointTexture();

    // 2. Main Particle Ribbon Vortex Geometry
    const PARTICLE_COUNT = 2400;
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const originalPositions = new Float32Array(PARTICLE_COUNT * 3);
    const colors = new Float32Array(PARTICLE_COUNT * 3);
    const speeds = new Float32Array(PARTICLE_COUNT);

    const baseColorCyan = new THREE.Color(0x00f0ff);
    const baseColorTeal = new THREE.Color(0x00ffc2);
    const baseColorPhosphor = new THREE.Color(0x00ff66);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      // Parametric Torus-Ribbon Knot coordinates
      const u = (i / PARTICLE_COUNT) * Math.PI * 8; // Multiple ribbon revolutions
      const v = (i / PARTICLE_COUNT) * Math.PI * 2;
      
      const majorRadius = 55 + Math.sin(u * 2) * 8;
      const minorRadius = 22 + Math.cos(v * 3) * 6;
      
      // Dispersion jitter
      const jitterX = (Math.random() - 0.5) * 6;
      const jitterY = (Math.random() - 0.5) * 6;
      const jitterZ = (Math.random() - 0.5) * 8;

      const x = (majorRadius + minorRadius * Math.cos(v)) * Math.cos(u) + jitterX;
      const y = (majorRadius + minorRadius * Math.cos(v)) * Math.sin(u) + jitterY;
      const z = minorRadius * Math.sin(v) * 1.8 + jitterZ;

      positions[i3] = x;
      positions[i3 + 1] = y;
      positions[i3 + 2] = z;

      originalPositions[i3] = x;
      originalPositions[i3 + 1] = y;
      originalPositions[i3 + 2] = z;

      // Color gradient blending along ribbon
      const t = (i / PARTICLE_COUNT + Math.random() * 0.1) % 1.0;
      const pColor = new THREE.Color();
      if (t < 0.5) {
        pColor.lerpColors(baseColorCyan, baseColorTeal, t * 2);
      } else {
        pColor.lerpColors(baseColorTeal, baseColorPhosphor, (t - 0.5) * 2);
      }

      colors[i3] = pColor.r;
      colors[i3 + 1] = pColor.g;
      colors[i3 + 2] = pColor.b;

      speeds[i] = 0.5 + Math.random() * 1.5;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 3.5,
      map: pointTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // 3. Dense Inner Core Nexus (600 particles)
    const CORE_COUNT = 600;
    const corePositions = new Float32Array(CORE_COUNT * 3);
    const coreColors = new Float32Array(CORE_COUNT * 3);

    for (let i = 0; i < CORE_COUNT; i++) {
      const i3 = i * 3;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      const r = 12 + Math.random() * 14;

      corePositions[i3] = r * Math.sin(phi) * Math.cos(theta);
      corePositions[i3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      corePositions[i3 + 2] = r * Math.cos(phi);

      coreColors[i3] = 0.8 + Math.random() * 0.2;
      coreColors[i3 + 1] = 1.0;
      coreColors[i3 + 2] = 0.95;
    }

    const coreGeometry = new THREE.BufferGeometry();
    coreGeometry.setAttribute('position', new THREE.BufferAttribute(corePositions, 3));
    coreGeometry.setAttribute('color', new THREE.BufferAttribute(coreColors, 3));

    const coreMaterial = new THREE.PointsMaterial({
      size: 2.2,
      map: pointTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const coreParticles = new THREE.Points(coreGeometry, coreMaterial);
    scene.add(coreParticles);

    // 4. Subtle Concentric Hologram Rings
    const ringGeo = new THREE.RingGeometry(72, 73.5, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = Math.PI / 3;
    scene.add(ringMesh);

    // 5. Animation Loop
    let animationFrameId: number;
    let clock = new THREE.Clock();
    let currentScale = 1.0;
    let targetScale = 1.0;
    let pulseAngle = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const delta = Math.min(clock.getDelta(), 0.1);
      const elapsed = clock.getElapsedTime();
      const currentState = (stateRef.current || 'idle').toLowerCase();

      // State-specific physics and velocities
      let rotSpeedY = 0.005;
      let rotSpeedX = 0.002;
      let coreRotSpeed = -0.015;
      let displacementAmp = 1.0;

      if (currentState === 'thinking' || currentState === 'calling_tool') {
        // High speed turbulence
        rotSpeedY = 0.045;
        rotSpeedX = 0.02;
        coreRotSpeed = -0.06;
        displacementAmp = 4.0;
        targetScale = 1.15 + Math.sin(elapsed * 10) * 0.06;
        material.size = 4.2;
      } else if (currentState === 'speaking') {
        // Rhythmic radial acoustic wave expansion
        rotSpeedY = 0.016;
        rotSpeedX = 0.006;
        pulseAngle += delta * 14;
        targetScale = 1.0 + Math.abs(Math.sin(pulseAngle)) * 0.28;
        displacementAmp = 2.2;
        material.size = 3.8;
      } else if (currentState === 'listening') {
        // High-frequency magnetic suction wave
        rotSpeedY = 0.022;
        rotSpeedX = -0.008;
        pulseAngle += delta * 8;
        targetScale = 0.92 + Math.sin(pulseAngle) * 0.12;
        displacementAmp = 2.5;
        material.size = 3.9;
      } else {
        // Idle gentle breathing
        rotSpeedY = 0.007;
        rotSpeedX = 0.003;
        coreRotSpeed = -0.012;
        targetScale = 1.0 + Math.sin(elapsed * 1.5) * 0.04;
        displacementAmp = 1.0;
        material.size = 3.4;
      }

      // Smooth scale interpolation
      currentScale += (targetScale - currentScale) * 0.1;
      particles.scale.set(currentScale, currentScale, currentScale);
      coreParticles.scale.set(currentScale * 0.95, currentScale * 0.95, currentScale * 0.95);
      ringMesh.scale.set(currentScale * 1.02, currentScale * 1.02, currentScale * 1.02);

      // Rotation updates
      particles.rotation.y += rotSpeedY;
      particles.rotation.x += rotSpeedX;
      particles.rotation.z += 0.001;

      coreParticles.rotation.y += coreRotSpeed;
      coreParticles.rotation.x -= rotSpeedX * 1.5;

      ringMesh.rotation.z += 0.004;

      // Dynamic vertex wave displacement
      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3;
        const ox = originalPositions[i3];
        const oy = originalPositions[i3 + 1];
        const oz = originalPositions[i3 + 2];

        const wave = Math.sin(elapsed * speeds[i] * 3 + ox * 0.05 + oy * 0.05) * displacementAmp;
        posArray[i3] = ox + (ox / 60) * wave;
        posArray[i3 + 1] = oy + (oy / 60) * wave;
        posArray[i3 + 2] = oz + (oz / 30) * wave;
      }
      posAttr.needsUpdate = true;

      // Color shifts when thinking
      const colAttr = geometry.attributes.color as THREE.BufferAttribute;
      const colArray = colAttr.array as Float32Array;
      if (currentState === 'thinking' || currentState === 'calling_tool') {
        for (let i = 0; i < PARTICLE_COUNT; i++) {
          const i3 = i * 3;
          colArray[i3] = Math.min(1.0, colArray[i3] + 0.02);
          colArray[i3 + 1] = Math.max(0.6, colArray[i3 + 1] - 0.01);
        }
        colAttr.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    // 6. Responsive Resize Observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: newWidth, height: newHeight } = entry.contentRect;
        if (newWidth > 0 && newHeight > 0) {
          camera.aspect = newWidth / newHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(newWidth, newHeight);
        }
      }
    });
    resizeObserver.observe(container);

    // 7. Cleanup on unmount
    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }

      geometry.dispose();
      material.dispose();
      coreGeometry.dispose();
      coreMaterial.dispose();
      ringGeo.dispose();
      ringMat.dispose();
      pointTexture.dispose();
      renderer.dispose();
    };
  }, [size]);

  return (
    <div
      ref={mountRef}
      className={`relative flex items-center justify-center pointer-events-none select-none ${className}`}
      style={{ width: '100%', height: '100%' }}
    >
      {/* Holographic backdrop glow & cyber grid marker */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-64 h-64 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
        <div className="w-48 h-48 rounded-full border border-cyan-500/15 animate-ping opacity-25 pointer-events-none" />
      </div>
    </div>
  );
};

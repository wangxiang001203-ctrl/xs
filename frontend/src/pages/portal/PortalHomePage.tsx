import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import gsap from 'gsap'
import * as THREE from 'three'

import titleLogo from '../../assets/generated/xiantu-ai-logo-crop.png'
import heroBg from '../../assets/xiantu-ai-hero-bg.png'
import styles from './PortalHomePage.module.css'

function CameraRig() {
  const { camera, pointer } = useThree()

  useFrame((state) => {
    const t = state.clock.elapsedTime
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pointer.x * 0.55, 0.035)
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, 0.2 + pointer.y * 0.24 + Math.sin(t * 0.35) * 0.04, 0.035)
    camera.lookAt(0, 0.2, -2.5)
  })

  return null
}

function SpiritMotes() {
  const particleCount = 760
  const particles = useMemo(() => {
    const positions = new Float32Array(particleCount * 3)
    const colors = new Float32Array(particleCount * 3)
    const baseX = new Float32Array(particleCount)
    const baseZ = new Float32Array(particleCount)
    const speed = new Float32Array(particleCount)
    const sway = new Float32Array(particleCount)
    const phase = new Float32Array(particleCount)
    const palette = [
      new THREE.Color('#fff0bd'),
      new THREE.Color('#baf7e7'),
      new THREE.Color('#f6c96e'),
      new THREE.Color('#dffcff'),
    ]

    for (let i = 0; i < particleCount; i += 1) {
      const nearGate = Math.random() > 0.28
      const x = nearGate ? 0.55 + Math.random() * 4.65 : -5.2 + Math.random() * 4.7
      const y = -2.72 + Math.random() * 5.65
      const z = nearGate ? -3.1 - Math.random() * 2.7 : -2.5 - Math.random() * 3.8
      const color = palette[Math.floor(Math.random() * palette.length)]

      baseX[i] = x
      baseZ[i] = z
      positions[i * 3] = x
      positions[i * 3 + 1] = y
      positions[i * 3 + 2] = z
      colors[i * 3] = color.r
      colors[i * 3 + 1] = color.g
      colors[i * 3 + 2] = color.b
      speed[i] = 0.025 + Math.random() * 0.135
      sway[i] = 0.035 + Math.random() * 0.16
      phase[i] = Math.random() * Math.PI * 2
    }

    return { positions, colors, baseX, baseZ, speed, sway, phase }
  }, [])

  const ref = useRef<THREE.Points>(null)

  useFrame((state, delta) => {
    if (!ref.current) return
    const attribute = ref.current.geometry.getAttribute('position') as THREE.BufferAttribute
    const positions = attribute.array as Float32Array
    const t = state.clock.elapsedTime

    for (let i = 0; i < particleCount; i += 1) {
      const yIndex = i * 3 + 1
      positions[yIndex] += particles.speed[i] * delta * 7.8
      if (positions[yIndex] > 2.86) positions[yIndex] = -2.76 - Math.random() * 0.28
      positions[i * 3] = particles.baseX[i] + Math.sin(t * 0.48 + particles.phase[i] + positions[yIndex] * 0.7) * particles.sway[i]
      positions[i * 3 + 2] = particles.baseZ[i] + Math.cos(t * 0.32 + particles.phase[i]) * particles.sway[i] * 0.72
    }

    attribute.needsUpdate = true
    ref.current.rotation.y = Math.sin(t * 0.12) * 0.04
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[particles.positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[particles.colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.025}
        transparent
        opacity={0.78}
        depthWrite={false}
        vertexColors
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

function EnergyFountain() {
  const particleCount = 420
  const particles = useMemo(() => {
    const positions = new Float32Array(particleCount * 3)
    const baseX = new Float32Array(particleCount)
    const baseZ = new Float32Array(particleCount)
    const speed = new Float32Array(particleCount)
    const phase = new Float32Array(particleCount)

    for (let i = 0; i < particleCount; i += 1) {
      const spread = Math.random() ** 1.8
      baseX[i] = 1.45 + Math.random() * 3.05
      baseZ[i] = -3.8 - Math.random() * 2.2
      positions[i * 3] = baseX[i] + (Math.random() - 0.5) * spread * 0.9
      positions[i * 3 + 1] = -2.65 + Math.random() * 5.2
      positions[i * 3 + 2] = baseZ[i]
      speed[i] = 0.22 + Math.random() * 0.72
      phase[i] = Math.random() * Math.PI * 2
    }

    return { positions, baseX, baseZ, speed, phase }
  }, [])

  const ref = useRef<THREE.Points>(null)

  useFrame((state, delta) => {
    if (!ref.current) return
    const attribute = ref.current.geometry.getAttribute('position') as THREE.BufferAttribute
    const positions = attribute.array as Float32Array
    const t = state.clock.elapsedTime

    for (let i = 0; i < particleCount; i += 1) {
      const yIndex = i * 3 + 1
      positions[yIndex] += particles.speed[i] * delta
      if (positions[yIndex] > 2.9) {
        positions[yIndex] = -2.6 - Math.random() * 0.4
      }
      positions[i * 3] = particles.baseX[i] + Math.sin(t * 0.9 + particles.phase[i] + positions[yIndex]) * 0.08
      positions[i * 3 + 2] = particles.baseZ[i] + Math.cos(t * 0.7 + particles.phase[i]) * 0.05
    }

    attribute.needsUpdate = true
    ref.current.rotation.z = Math.sin(t * 0.18) * 0.015
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[particles.positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.031}
        color="#ffedaa"
        transparent
        opacity={0.82}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

function HeroFxScene() {
  return (
    <>
      <CameraRig />
      <SpiritMotes />
      <EnergyFountain />
      <Sparkles count={76} size={1.7} scale={[6.8, 3.2, 3.7]} position={[2.05, 0.35, -3.35]} speed={0.24} color="#fff0b8" opacity={0.38} />
    </>
  )
}

export default function PortalHomePage() {
  const navigate = useNavigate()
  const shellRef = useRef<HTMLDivElement>(null)
  const artRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    if (!shellRef.current) return
    document.title = '仙途AI - AI 长篇小说创作引擎'
    document.body.classList.add('portal-home-active')
    document.documentElement.classList.add('portal-home-active')
    const ctx = gsap.context(() => {
      const timeline = gsap.timeline({ defaults: { ease: 'power3.out' } })
      timeline
        .fromTo(artRef.current, { scale: 1.08, opacity: 0.7, filter: 'saturate(0.9) contrast(1.12) brightness(0.72)' }, { scale: 1, opacity: 1, filter: 'saturate(1.06) contrast(1.05) brightness(1)', duration: 2.8, ease: 'sine.out' })
        .fromTo('[data-portal-nav]', { y: -14 }, { y: 0, duration: 1.1 }, 0.25)
        .fromTo('[data-portal-reveal]', { y: 22 }, { y: 0, duration: 1.25, stagger: 0.12 }, 0.62)
        .fromTo('[data-portal-title-img]', { scale: 0.94 }, { scale: 1, duration: 1.45, ease: 'expo.out' }, 0.72)

      gsap.to(artRef.current, { scale: 1.025, duration: 18, ease: 'sine.inOut', repeat: -1, yoyo: true, delay: 2.6 })
      gsap.to('[data-portal-title-img]', { y: -6, duration: 5.8, ease: 'sine.inOut', repeat: -1, yoyo: true, delay: 1.8 })
      gsap.to('[data-portal-primary]', { y: -2, duration: 2.9, ease: 'sine.inOut', repeat: -1, yoyo: true, delay: 1.4 })
    }, shellRef)
    return () => {
      ctx.revert()
      document.body.classList.remove('portal-home-active')
      document.documentElement.classList.remove('portal-home-active')
    }
  }, [])

  return (
    <main className={styles.page} ref={shellRef}>
      <section className={styles.hero}>
        <div className={styles.artLayer} aria-hidden="true">
          <img ref={artRef} src={heroBg} alt="" />
        </div>
        <div className={styles.sceneLayer} aria-hidden="true">
          <Canvas
            dpr={[1, 1.6]}
            camera={{ position: [0, 0.22, 6.6], fov: 45, near: 0.1, far: 40 }}
            gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
          >
            <Suspense fallback={null}>
              <HeroFxScene />
            </Suspense>
          </Canvas>
        </div>
        <div className={styles.mistLayer} aria-hidden="true" />
        <div className={styles.lightVeil} aria-hidden="true" />
        <div className={styles.gradeLayer} aria-hidden="true" />
        <div className={styles.noiseLayer} aria-hidden="true" />

        <header className={styles.nav} data-portal-nav>
          <Link to="/" className={styles.brand} aria-label="仙途AI官网首页">
            <img src={titleLogo} className={styles.brandLogo} alt="仙途AI" />
            <span className={styles.brandLine} />
          </Link>
          <nav className={styles.navLinks} aria-label="官网导航">
            <a href="#world">世界观</a>
            <a href="#graph">关系星图</a>
            <a href="#engine">AI引擎</a>
            <Link to="/bookshelf">作品库</Link>
          </nav>
          <button type="button" className={styles.navCta} onClick={() => navigate('/bookshelf')}>
            进入创作
          </button>
        </header>

        <div className={styles.copy}>
          <div className={styles.kicker} data-portal-reveal>
            <span /> 一剑开天门，长篇自成道
          </div>
          <h1 className={styles.titleMark} data-portal-reveal>
            <img src={titleLogo} alt="仙途AI" data-portal-title-img />
          </h1>
          <p data-portal-reveal>
            让 AI 统御大纲、设定、关系网与百万字长篇记忆，把一部修仙长篇从灵感推到定稿。
          </p>
          <div className={styles.actions} data-portal-reveal>
            <button type="button" className={styles.primaryAction} data-portal-primary onClick={() => navigate('/bookshelf')}>
              进入创作
            </button>
            <button type="button" className={styles.secondaryAction} onClick={() => navigate('/editor/admin')}>
              <span className={styles.playIcon} aria-hidden="true" />
              查看引擎
            </button>
          </div>
          <div className={styles.metrics} data-portal-reveal>
            <span><strong>百万字</strong> 长线记忆</span>
            <span><strong>3D</strong> 关系星图</span>
            <span><strong>非流式</strong> 审计生成</span>
          </div>
        </div>

        <div className={styles.cornerSeal} aria-hidden="true">长篇成道</div>
      </section>
    </main>
  )
}

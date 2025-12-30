<template>
  <div class="not-found">
    <v-container fluid class="text-center">
      <!-- Animated 404 -->
      <div class="error-container">
        <div class="error-code" :class="{ 'neon-text': themeStore.isRetrowave }">
          <span class="four">4</span>
          <span class="zero">0</span>
          <span class="four">4</span>
        </div>
        
        <!-- Glitch Effect -->
        <div class="glitch-overlay" v-if="themeStore.isRetrowave">
          <div class="glitch-text">404</div>
          <div class="glitch-text glitch-text-2">404</div>
          <div class="glitch-text glitch-text-3">404</div>
        </div>

        <!-- Hacker Terminal Lines -->
        <div class="terminal-lines" v-if="themeStore.isRetrowave">
          <div class="terminal-line" v-for="(line, index) in terminalLines" :key="index" :style="{ '--delay': index * 0.1 + 's' }">
            {{ line }}
          </div>
        </div>

        <!-- Binary Rain -->
        <div class="binary-rain" v-if="themeStore.isRetrowave">
          <div class="binary-column" v-for="i in 15" :key="i" :style="getBinaryColumnStyle(i)">
            <span v-for="j in 20" :key="j" class="binary-char">{{ Math.random() > 0.5 ? '1' : '0' }}</span>
          </div>
        </div>
      </div>

      <!-- Main Message -->
      <div class="error-message">
        <h1 class="text-h3 font-weight-bold mb-4" :class="{ 'neon-text': themeStore.isRetrowave }">
          <span class="hacker-text" v-if="themeStore.isRetrowave">ACCESS DENIED</span>
          <span class="enhanced-text" v-else>Page Not Found</span>
        </h1>
        <p class="text-h6 mb-6" :class="{ 'neon-subtitle': themeStore.isRetrowave }">
          <span class="terminal-prompt" v-if="themeStore.isRetrowave">$</span> 
          <span v-if="themeStore.isRetrowave">ERROR: 404 - RESOURCE NOT FOUND</span>
          <span v-else>The page you're looking for doesn't exist or has been moved.</span>
        </p>
        <div class="hacker-status" v-if="themeStore.isRetrowave">
          <div class="status-line">
            <span class="status-label">STATUS:</span>
            <span class="status-value error">CONNECTION TERMINATED</span>
          </div>
          <div class="status-line">
            <span class="status-label">PROTOCOL:</span>
            <span class="status-value">HTTP/1.1 404</span>
          </div>
          <div class="status-line">
            <span class="status-label">SECURITY:</span>
            <span class="status-value warning">UNAUTHORIZED ACCESS</span>
          </div>
        </div>
      </div>

      <!-- Animated Elements -->
      <div class="animated-elements" v-if="themeStore.isRetrowave">
        <div class="floating-particles">
          <div class="particle" v-for="i in 30" :key="i" :style="getParticleStyle(i)"></div>
        </div>
        <div class="scan-lines"></div>
        
        <!-- Hacker Grid -->
        <div class="hacker-grid">
          <div class="grid-line" v-for="i in 20" :key="i" :style="getGridLineStyle(i)"></div>
        </div>
        
        <!-- Circuit Board Pattern -->
        <div class="circuit-board">
          <div class="circuit-line" v-for="i in 8" :key="i" :style="getCircuitLineStyle(i)"></div>
          <div class="circuit-node" v-for="i in 12" :key="i" :style="getCircuitNodeStyle(i)"></div>
        </div>
        
        <!-- Data Streams -->
        <div class="data-streams">
          <div class="data-stream" v-for="i in 5" :key="i" :style="getDataStreamStyle(i)">
            <span class="data-char" v-for="j in 10" :key="j">{{ getRandomChar() }}</span>
          </div>
        </div>
      </div>

      <!-- Enhanced Background Elements for Normal Theme -->
      <div class="background-elements" v-if="!themeStore.isRetrowave && !themeStore.isMatrix">
        <!-- Geometric Shapes -->
        <div class="geometric-shapes">
          <div class="shape triangle" v-for="i in 8" :key="`triangle-${i}`" :style="getGeometricShapeStyle('triangle', i)"></div>
          <div class="shape circle" v-for="i in 12" :key="`circle-${i}`" :style="getGeometricShapeStyle('circle', i)"></div>
          <div class="shape square" v-for="i in 6" :key="`square-${i}`" :style="getGeometricShapeStyle('square', i)"></div>
        </div>
        
        <!-- Floating Orbs -->
        <div class="floating-orbs">
          <div class="orb" v-for="i in 15" :key="`orb-${i}`" :style="getOrbStyle(i)"></div>
        </div>
        
        <!-- Gradient Waves -->
        <div class="gradient-waves">
          <div class="wave" v-for="i in 3" :key="`wave-${i}`" :style="getWaveStyle(i)"></div>
        </div>
        
        <!-- Subtle Grid Pattern -->
        <div class="subtle-grid"></div>
      </div>

      <!-- Enhanced Retrowave 16-bit/8-bit Background Elements -->
      <div class="retrowave-background" v-if="themeStore.isRetrowave">
        <!-- Pixel Grid Background -->
        <div class="pixel-grid"></div>
        
        <!-- Retro City Skyline -->
        <div class="city-skyline">
          <div class="building" v-for="i in 12" :key="`building-${i}`" :style="getBuildingStyle(i)"></div>
        </div>
        
        <!-- Floating Pixels -->
        <div class="floating-pixels">
          <div class="pixel" v-for="i in 50" :key="`pixel-${i}`" :style="getPixelStyle(i)"></div>
        </div>
        
        <!-- Retro Sun/Moon -->
        <div class="retro-sun" :style="getRetroSunStyle()"></div>
        
        <!-- Neon Grid Lines -->
        <div class="neon-grid">
          <div class="grid-line" v-for="i in 8" :key="`neon-line-${i}`" :style="getNeonGridStyle(i)"></div>
        </div>
        
        <!-- Retro Stars -->
        <div class="retro-stars">
          <div class="star" v-for="i in 30" :key="`star-${i}`" :style="getStarStyle(i)"></div>
        </div>
        
        <!-- Pixel Mountains -->
        <div class="pixel-mountains">
          <div class="mountain" v-for="i in 5" :key="`mountain-${i}`" :style="getMountainStyle(i)"></div>
        </div>
        
        <!-- Retro Clouds -->
        <div class="retro-clouds">
          <div class="cloud" v-for="i in 8" :key="`cloud-${i}`" :style="getCloudStyle(i)"></div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-home"
          @click="goHome"
          class="mr-4 mb-2"
          :class="{ 'retrowave-btn': themeStore.isRetrowave }"
        >
          Go Home
        </v-btn>
        
        <v-btn
          color="secondary"
          size="large"
          prepend-icon="mdi-arrow-left"
          @click="goBack"
          class="mb-2"
          :class="{ 'retrowave-btn': themeStore.isRetrowave }"
        >
          Go Back
        </v-btn>
      </div>

      <!-- Matrix Rain Effect (for Matrix theme) -->
      <div class="matrix-rain" v-if="themeStore.isMatrix">
        <div class="matrix-column" v-for="i in 20" :key="i" :style="getMatrixColumnStyle(i)">
          <span v-for="j in 30" :key="j" class="matrix-char">{{ getMatrixChar() }}</span>
        </div>
      </div>

      <!-- Debug Info (only in development) -->
      <v-card v-if="isDev" class="mt-8 debug-info" elevation="2">
        <v-card-title>Debug Information</v-card-title>
        <v-card-text>
          <p><strong>Requested URL:</strong> {{ route.path }}</p>
          <p><strong>Timestamp:</strong> {{ new Date().toISOString() }}</p>
          <p><strong>User Agent:</strong> {{ userAgent }}</p>
        </v-card-text>
      </v-card>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const route = useRoute()
const themeStore = useThemeStore()

// Computed property for user agent
const userAgent = computed(() => {
  if (typeof window !== 'undefined') {
    return window.navigator.userAgent
  }
  return 'Unknown'
})

const isDev = import.meta.env.DEV

// Animation state
const animationFrame = ref<number>()

// Matrix rain characters
const matrixChars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'

// Terminal lines for hacker effect
const terminalLines = ref([
  '> INITIALIZING SECURITY PROTOCOL...',
  '> SCANNING FOR TARGET RESOURCE...',
  '> ERROR: RESOURCE NOT FOUND',
  '> ATTEMPTING TO RECONNECT...',
  '> CONNECTION FAILED',
  '> FALLBACK TO DEFAULT ROUTE...',
  '> SYSTEM STATUS: OFFLINE',
  '> SECURITY ALERT: UNAUTHORIZED ACCESS',
  '> TERMINATING CONNECTION...',
  '> RETURNING TO SAFE MODE...'
])

// Hacker characters for data streams
const hackerChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?'

const goHome = () => {
  router.push('/')
}

const goBack = () => {
  router.back()
}

const getParticleStyle = (index: number) => {
  const delay = Math.random() * 5
  const duration = 3 + Math.random() * 4
  const x = Math.random() * 100
  const y = Math.random() * 100
  
  return {
    '--delay': `${delay}s`,
    '--duration': `${duration}s`,
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${2 + Math.random() * 4}px`
  }
}

const getMatrixColumnStyle = (index: number) => {
  const delay = Math.random() * 10
  const duration = 2 + Math.random() * 3
  
  return {
    '--delay': `${delay}s`,
    '--duration': `${duration}s`,
    '--x': `${index * 5}%`
  }
}

const getMatrixChar = () => {
  return matrixChars[Math.floor(Math.random() * matrixChars.length)]
}

const getRandomChar = () => {
  return hackerChars[Math.floor(Math.random() * hackerChars.length)]
}

const getBinaryColumnStyle = (index: number) => {
  const delay = Math.random() * 8
  const duration = 3 + Math.random() * 4
  
  return {
    '--delay': `${delay}s`,
    '--duration': `${duration}s`,
    '--x': `${index * 6.67}%`
  }
}

const getGridLineStyle = (index: number) => {
  const isVertical = index % 2 === 0
  const position = (index / 20) * 100
  
  return {
    '--position': `${position}%`,
    '--angle': isVertical ? '0deg' : '90deg',
    '--delay': `${index * 0.1}s`
  }
}

const getCircuitLineStyle = (index: number) => {
  const startX = Math.random() * 100
  const startY = Math.random() * 100
  const endX = Math.random() * 100
  const endY = Math.random() * 100
  
  return {
    '--start-x': `${startX}%`,
    '--start-y': `${startY}%`,
    '--end-x': `${endX}%`,
    '--end-y': `${endY}%`,
    '--delay': `${index * 0.2}s`
  }
}

const getCircuitNodeStyle = (index: number) => {
  const x = Math.random() * 100
  const y = Math.random() * 100
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--delay': `${index * 0.15}s`
  }
}

const getDataStreamStyle = (index: number) => {
  const startX = Math.random() * 100
  const endX = Math.random() * 100
  const duration = 2 + Math.random() * 3
  
  return {
    '--start-x': `${startX}%`,
    '--end-x': `${endX}%`,
    '--duration': `${duration}s`,
    '--delay': `${index * 0.5}s`
  }
}

// New functions for enhanced background elements
const getGeometricShapeStyle = (type: string, index: number) => {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 20 + Math.random() * 40
  const rotation = Math.random() * 360
  const duration = 8 + Math.random() * 12
  const delay = Math.random() * 5
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--rotation': `${rotation}deg`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getOrbStyle = (index: number) => {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 30 + Math.random() * 60
  const duration = 6 + Math.random() * 8
  const delay = Math.random() * 4
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getWaveStyle = (index: number) => {
  const height = 100 + Math.random() * 200
  const duration = 10 + Math.random() * 15
  const delay = Math.random() * 5
  const opacity = 0.1 + Math.random() * 0.2
  
  return {
    '--height': `${height}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`,
    '--opacity': opacity
  }
}

// Retrowave 16-bit/8-bit background functions
const getBuildingStyle = (index: number) => {
  const width = 40 + Math.random() * 80
  const height = 100 + Math.random() * 200
  const x = (index * 8) + Math.random() * 5
  const duration = 8 + Math.random() * 12
  const delay = Math.random() * 3
  
  return {
    '--width': `${width}px`,
    '--height': `${height}px`,
    '--x': `${x}%`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getPixelStyle = (index: number) => {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 2 + Math.random() * 6
  const duration = 3 + Math.random() * 6
  const delay = Math.random() * 4
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getRetroSunStyle = () => {
  const x = 20 + Math.random() * 60
  const y = 10 + Math.random() * 20
  const size = 60 + Math.random() * 40
  const duration = 20 + Math.random() * 10
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--duration': `${duration}s`
  }
}

const getNeonGridStyle = (index: number) => {
  const isVertical = index % 2 === 0
  const position = (index / 8) * 100
  const duration = 4 + Math.random() * 6
  const delay = Math.random() * 2
  
  return {
    '--position': `${position}%`,
    '--is-vertical': isVertical ? '1' : '0',
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getStarStyle = (index: number) => {
  const x = Math.random() * 100
  const y = Math.random() * 100
  const size = 1 + Math.random() * 3
  const duration = 2 + Math.random() * 4
  const delay = Math.random() * 3
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getMountainStyle = (index: number) => {
  const x = (index * 20) + Math.random() * 10
  const height = 80 + Math.random() * 120
  const width = 100 + Math.random() * 150
  const duration = 15 + Math.random() * 10
  const delay = Math.random() * 5
  
  return {
    '--x': `${x}%`,
    '--height': `${height}px`,
    '--width': `${width}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

const getCloudStyle = (index: number) => {
  const x = Math.random() * 100
  const y = 20 + Math.random() * 30
  const size = 30 + Math.random() * 50
  const duration = 20 + Math.random() * 15
  const delay = Math.random() * 10
  
  return {
    '--x': `${x}%`,
    '--y': `${y}%`,
    '--size': `${size}px`,
    '--duration': `${duration}s`,
    '--delay': `${delay}s`
  }
}

// Animation loop
const animate = () => {
  // Update any animations here if needed
  animationFrame.value = requestAnimationFrame(animate)
}

onMounted(() => {
  animate()
})

onUnmounted(() => {
  if (animationFrame.value) {
    cancelAnimationFrame(animationFrame.value)
  }
})
</script>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  align-items: center;
  background: #ffffff;
  position: relative;
  overflow: hidden;
}

/* Retrowave theme specific background */
.retrowave-theme .not-found {
  background: 
    radial-gradient(circle at 30% 20%, rgba(255, 0, 150, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 70% 80%, rgba(0, 255, 255, 0.2) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(150, 0, 255, 0.1) 0%, transparent 50%),
    linear-gradient(135deg, #0a0a0f 0%, #1a0a1f 50%, #0f0a1a 100%) !important;
}

/* Matrix theme specific background */
.v-theme--matrix .not-found {
  background: #000 !important;
}

.error-container {
  position: relative;
  margin-bottom: 2rem;
}

.error-code {
  font-size: 12rem;
  font-weight: 900;
  line-height: 0.8;
  color: #2c3e50;
  text-shadow: 0 0 20px rgba(0, 0, 0, 0.3);
  position: relative;
  z-index: 2;
}

.error-code .four {
  display: inline-block;
  animation: bounce 2s ease-in-out infinite;
}

.error-code .zero {
  display: inline-block;
  animation: bounce 2s ease-in-out infinite 0.2s;
}

.error-code .four:last-child {
  display: inline-block;
  animation: bounce 2s ease-in-out infinite 0.4s;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-30px);
  }
  60% {
    transform: translateY(-15px);
  }
}

/* Glitch Effect for Retrowave */
.glitch-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
  pointer-events: none;
}

.glitch-text {
  font-size: 12rem;
  font-weight: 900;
  line-height: 0.8;
  color: #ff1493;
  opacity: 0.7;
  animation: glitch 0.3s infinite;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.glitch-text-2 {
  color: #00bfff;
  animation: glitch 0.3s infinite 0.1s;
  transform: translate(2px, -2px);
}

.glitch-text-3 {
  color: #8a2be2;
  animation: glitch 0.3s infinite 0.2s;
  transform: translate(-2px, 2px);
}

@keyframes glitch {
  0% {
    transform: translate(0);
    filter: hue-rotate(0deg);
  }
  20% {
    transform: translate(-2px, 2px);
    filter: hue-rotate(90deg);
  }
  40% {
    transform: translate(-2px, -2px);
    filter: hue-rotate(180deg);
  }
  60% {
    transform: translate(2px, 2px);
    filter: hue-rotate(270deg);
  }
  80% {
    transform: translate(2px, -2px);
    filter: hue-rotate(360deg);
  }
  100% {
    transform: translate(0);
    filter: hue-rotate(0deg);
  }
}

/* Terminal Lines */
.terminal-lines {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  color: #00ff00;
  text-shadow: 0 0 10px #00ff00;
  opacity: 0.8;
  max-width: 400px;
  text-align: left;
}

.terminal-line {
  margin-bottom: 4px;
  animation: terminal-type 0.5s ease-in-out var(--delay) both;
  white-space: nowrap;
  overflow: hidden;
}

@keyframes terminal-type {
  0% {
    width: 0;
    opacity: 0;
  }
  100% {
    width: 100%;
    opacity: 1;
  }
}

/* Binary Rain */
.binary-rain {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
}

.binary-column {
  position: absolute;
  top: -100%;
  left: var(--x);
  width: 20px;
  height: 100vh;
  animation: binary-fall var(--duration) linear infinite var(--delay);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.2;
  color: #00bfff;
  text-shadow: 0 0 5px #00bfff;
}

@keyframes binary-fall {
  0% {
    top: -100%;
    opacity: 1;
  }
  100% {
    top: 100vh;
    opacity: 0;
  }
}

.binary-char {
  display: block;
  animation: binary-flicker 0.1s infinite;
}

@keyframes binary-flicker {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

/* Hacker Text Effects */
.hacker-text {
  font-family: 'Courier New', monospace;
  letter-spacing: 2px;
  animation: hacker-glow 2s ease-in-out infinite alternate;
}

@keyframes hacker-glow {
  0% {
    text-shadow: 
      0 0 5px #00ff00,
      0 0 10px #00ff00,
      0 0 15px #00ff00,
      0 0 20px #00ff00;
  }
  100% {
    text-shadow: 
      0 0 10px #00ff00,
      0 0 20px #00ff00,
      0 0 30px #00ff00,
      0 0 40px #00ff00;
  }
}

.terminal-prompt {
  color: #00ff00;
  font-family: 'Courier New', monospace;
  font-weight: bold;
  margin-right: 8px;
}

/* Hacker Status */
.hacker-status {
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid #00ff00;
  border-radius: 8px;
  padding: 16px;
  margin: 20px auto;
  max-width: 500px;
  font-family: 'Courier New', monospace;
  font-size: 0.9rem;
}

.status-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  animation: status-appear 0.5s ease-in-out var(--delay) both;
}

.status-label {
  color: #00bfff;
  font-weight: bold;
}

.status-value {
  color: #00ff00;
}

.status-value.error {
  color: #ff4444;
  animation: error-blink 1s infinite;
}

.status-value.warning {
  color: #ffaa00;
  animation: warning-pulse 2s infinite;
}

@keyframes status-appear {
  0% {
    opacity: 0;
    transform: translateX(-20px);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes error-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0.3; }
}

@keyframes warning-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* Hacker Grid */
.hacker-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
}

.grid-line {
  position: absolute;
  background: linear-gradient(90deg, transparent, #00bfff, transparent);
  height: 1px;
  width: 100%;
  top: var(--position);
  animation: grid-scan 3s ease-in-out infinite var(--delay);
  opacity: 0.3;
}

.grid-line:nth-child(even) {
  transform: rotate(90deg);
  width: 100vh;
  height: 1px;
  left: var(--position);
  top: 0;
}

@keyframes grid-scan {
  0%, 100% {
    opacity: 0.1;
    transform: scaleX(0);
  }
  50% {
    opacity: 0.6;
    transform: scaleX(1);
  }
}

/* Circuit Board */
.circuit-board {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
}

.circuit-line {
  position: absolute;
  height: 2px;
  background: linear-gradient(90deg, #00bfff, #ff1493, #00bfff);
  border-radius: 1px;
  animation: circuit-pulse 2s ease-in-out infinite var(--delay);
  box-shadow: 0 0 10px #00bfff;
}

.circuit-line::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: inherit;
  border-radius: inherit;
  animation: circuit-flow 3s linear infinite;
}

@keyframes circuit-pulse {
  0%, 100% {
    opacity: 0.3;
    transform: scaleY(1);
  }
  50% {
    opacity: 1;
    transform: scaleY(1.5);
  }
}

@keyframes circuit-flow {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.circuit-node {
  position: absolute;
  width: 8px;
  height: 8px;
  background: #00bfff;
  border-radius: 50%;
  left: var(--x);
  top: var(--y);
  animation: node-pulse 1.5s ease-in-out infinite var(--delay);
  box-shadow: 0 0 15px #00bfff;
}

@keyframes node-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.7;
  }
  50% {
    transform: scale(1.5);
    opacity: 1;
  }
}

/* Data Streams */
.data-streams {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
}

.data-stream {
  position: absolute;
  top: 20%;
  left: var(--start-x);
  animation: data-flow var(--duration) linear infinite var(--delay);
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #00ff00;
  text-shadow: 0 0 5px #00ff00;
  white-space: nowrap;
}

@keyframes data-flow {
  0% {
    left: var(--start-x);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    left: var(--end-x);
    opacity: 0;
  }
}

.data-char {
  display: inline-block;
  animation: char-flicker 0.1s infinite;
  margin-right: 2px;
}

@keyframes char-flicker {
  0%, 90% {
    opacity: 1;
  }
  95% {
    opacity: 0.3;
  }
  100% {
    opacity: 1;
  }
}

.error-message {
  margin-bottom: 3rem;
  position: relative;
  z-index: 2;
}

/* Floating Particles for Retrowave */
.floating-particles {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
}

.particle {
  position: absolute;
  width: var(--size);
  height: var(--size);
  background: #00bfff;
  border-radius: 50%;
  animation: float var(--duration) ease-in-out infinite var(--delay);
  left: var(--x);
  top: var(--y);
  box-shadow: 0 0 10px #00bfff;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.7;
  }
  50% {
    transform: translateY(-20px) scale(1.2);
    opacity: 1;
  }
}

/* Scan Lines for Retrowave */
.scan-lines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 191, 255, 0.1) 2px,
    rgba(0, 191, 255, 0.1) 4px
  );
  animation: scan 2s linear infinite;
  pointer-events: none;
  z-index: 1;
}

@keyframes scan {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(100vh);
  }
}

.action-buttons {
  position: relative;
  z-index: 2;
}

.retrowave-btn {
  background: linear-gradient(45deg, #00bfff 0%, #0066cc 50%, #00aaff 100%) !important;
  color: #000000 !important;
  font-weight: bold !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
  box-shadow: 
    0 0 25px rgba(0, 191, 255, 0.8),
    0 0 50px rgba(0, 102, 204, 0.6),
    inset 0 0 20px rgba(255, 255, 255, 0.2) !important;
  border: 2px solid #00bfff !important;
  transition: all 0.3s ease !important;
}

.retrowave-btn:hover {
  transform: translateY(-3px) scale(1.02) !important;
  box-shadow: 
    0 0 40px rgba(0, 191, 255, 1),
    0 0 80px rgba(0, 102, 204, 0.8),
    inset 0 0 30px rgba(255, 255, 255, 0.3) !important;
}

/* Matrix Rain Effect */
.matrix-rain {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
}

.matrix-column {
  position: absolute;
  top: -100%;
  left: var(--x);
  width: 20px;
  height: 100vh;
  animation: matrix-fall var(--duration) linear infinite var(--delay);
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.2;
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

@keyframes matrix-fall {
  0% {
    top: -100%;
    opacity: 1;
  }
  100% {
    top: 100vh;
    opacity: 0;
  }
}

.matrix-char {
  display: block;
  animation: matrix-flicker 0.1s infinite;
}

@keyframes matrix-flicker {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

/* Debug Info */
.debug-info {
  max-width: 600px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.9) !important;
}

.v-theme--matrix .debug-info {
  background: rgba(0, 0, 0, 0.9) !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.retrowave-theme .debug-info {
  background: rgba(10, 10, 15, 0.9) !important;
  color: #00bfff !important;
  border: 1px solid #00bfff !important;
}

/* Responsive Design */
@media (max-width: 768px) {
  .error-code {
    font-size: 8rem;
  }
  
  .glitch-text {
    font-size: 8rem;
  }
  
  .action-buttons {
    flex-direction: column;
    align-items: center;
  }
  
  .action-buttons .v-btn {
    width: 200px;
    margin: 8px 0;
  }
}

@media (max-width: 480px) {
  .error-code {
    font-size: 6rem;
  }
  
  .glitch-text {
    font-size: 6rem;
  }
}

/* Enhanced Background Elements for Normal Theme */
.background-elements {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
}

/* Geometric Shapes */
.geometric-shapes {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.shape {
  position: absolute;
  opacity: 0.1;
  animation: geometric-float var(--duration) ease-in-out infinite var(--delay);
}

.shape.triangle {
  width: 0;
  height: 0;
  border-left: calc(var(--size) / 2) solid transparent;
  border-right: calc(var(--size) / 2) solid transparent;
  border-bottom: var(--size) solid rgba(120, 119, 198, 0.4);
  left: var(--x);
  top: var(--y);
  transform: rotate(var(--rotation));
}

.shape.circle {
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 119, 198, 0.3) 0%, transparent 70%);
  left: var(--x);
  top: var(--y);
  transform: rotate(var(--rotation));
}

.shape.square {
  width: var(--size);
  height: var(--size);
  background: linear-gradient(45deg, rgba(120, 219, 255, 0.3) 0%, transparent 100%);
  left: var(--x);
  top: var(--y);
  transform: rotate(var(--rotation));
}

@keyframes geometric-float {
  0%, 100% {
    transform: translateY(0) rotate(var(--rotation)) scale(1);
    opacity: 0.1;
  }
  25% {
    transform: translateY(-20px) rotate(calc(var(--rotation) + 90deg)) scale(1.1);
    opacity: 0.2;
  }
  50% {
    transform: translateY(-40px) rotate(calc(var(--rotation) + 180deg)) scale(0.9);
    opacity: 0.15;
  }
  75% {
    transform: translateY(-20px) rotate(calc(var(--rotation) + 270deg)) scale(1.05);
    opacity: 0.2;
  }
}

/* Floating Orbs */
.floating-orbs {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.orb {
  position: absolute;
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.8) 0%, rgba(120, 219, 255, 0.4) 50%, transparent 100%);
  left: var(--x);
  top: var(--y);
  animation: orb-float var(--duration) ease-in-out infinite var(--delay);
  box-shadow: 
    0 0 20px rgba(120, 219, 255, 0.3),
    inset 0 0 20px rgba(255, 255, 255, 0.2);
}

@keyframes orb-float {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.6;
  }
  33% {
    transform: translateY(-30px) scale(1.1);
    opacity: 0.8;
  }
  66% {
    transform: translateY(-60px) scale(0.9);
    opacity: 0.4;
  }
}

/* Gradient Waves */
.gradient-waves {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.wave {
  position: absolute;
  width: 100%;
  height: var(--height);
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(120, 119, 198, var(--opacity)) 25%,
    rgba(255, 119, 198, var(--opacity)) 50%,
    rgba(120, 219, 255, var(--opacity)) 75%,
    transparent 100%
  );
  animation: wave-flow var(--duration) linear infinite var(--delay);
  opacity: var(--opacity);
}

.wave:nth-child(1) {
  top: 20%;
  transform: rotate(-2deg);
}

.wave:nth-child(2) {
  top: 60%;
  transform: rotate(1deg);
}

.wave:nth-child(3) {
  top: 80%;
  transform: rotate(-1deg);
}

@keyframes wave-flow {
  0% {
    transform: translateX(-100%) rotate(var(--rotation, 0deg));
  }
  100% {
    transform: translateX(100%) rotate(var(--rotation, 0deg));
  }
}

/* Subtle Grid Pattern */
.subtle-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(120, 119, 198, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120, 119, 198, 0.1) 1px, transparent 1px);
  background-size: 50px 50px;
  animation: grid-pulse 8s ease-in-out infinite;
  opacity: 0.3;
}

@keyframes grid-pulse {
  0%, 100% {
    opacity: 0.1;
  }
  50% {
    opacity: 0.3;
  }
}

/* Enhanced Error Code Styling */
.error-code {
  font-size: 12rem;
  font-weight: 900;
  line-height: 0.8;
  color: #2c3e50;
  text-shadow: 
    0 0 20px rgba(0, 0, 0, 0.3),
    0 0 40px rgba(120, 119, 198, 0.2),
    0 0 60px rgba(255, 119, 198, 0.1);
  position: relative;
  z-index: 2;
  background: linear-gradient(45deg, #2c3e50, #34495e, #2c3e50);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: gradient-shift 3s ease-in-out infinite;
}

@keyframes gradient-shift {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

/* Enhanced Action Buttons */
.action-buttons .v-btn {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.action-buttons .v-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.action-buttons .v-btn:hover::before {
  left: 100%;
}

.action-buttons .v-btn:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 
    0 8px 25px rgba(0, 0, 0, 0.15),
    0 0 20px rgba(120, 119, 198, 0.3);
}

/* Enhanced Text Styling for Normal Theme */
.enhanced-text {
  background: linear-gradient(45deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: gradient-shift 3s ease-in-out infinite;
  font-weight: 700;
  letter-spacing: 1px;
  text-shadow: 0 0 30px rgba(102, 126, 234, 0.3);
}

/* Enhanced Error Message Styling */
.error-message p {
  color: #5a6c7d;
  font-weight: 500;
  line-height: 1.6;
  max-width: 600px;
  margin: 0 auto;
}

/* Additional Visual Enhancements */
.error-container::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 300px;
  height: 300px;
  border: 2px solid rgba(120, 119, 198, 0.2);
  border-radius: 50%;
  animation: pulse-ring 2s ease-out infinite;
  z-index: 1;
}

.error-container::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 200px;
  height: 200px;
  border: 1px solid rgba(255, 119, 198, 0.3);
  border-radius: 50%;
  animation: pulse-ring 2s ease-out infinite 0.5s;
  z-index: 1;
}

@keyframes pulse-ring {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.2);
    opacity: 0;
  }
}

/* Improved Responsive Design */
@media (max-width: 768px) {
  .enhanced-text {
    font-size: 2rem;
  }
  
  .error-message p {
    font-size: 1.1rem;
  }
  
  .background-elements .shape {
    opacity: 0.05;
  }
  
  .background-elements .orb {
    opacity: 0.3;
  }
}

@media (max-width: 480px) {
  .enhanced-text {
    font-size: 1.5rem;
  }
  
  .error-message p {
    font-size: 1rem;
  }
}

/* Enhanced Retrowave 16-bit/8-bit Background Elements */
.retrowave-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
}

/* Pixel Grid Background */
.pixel-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px);
  background-size: 20px 20px;
  animation: pixel-grid-pulse 4s ease-in-out infinite;
  opacity: 0.3;
}

@keyframes pixel-grid-pulse {
  0%, 100% { opacity: 0.1; }
  50% { opacity: 0.3; }
}

/* Retro City Skyline */
.city-skyline {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40%;
  z-index: 2;
}

.building {
  position: absolute;
  bottom: 0;
  left: var(--x);
  width: var(--width);
  height: var(--height);
  background: linear-gradient(
    180deg,
    #ff00ff 0%,
    #ff0080 25%,
    #8000ff 50%,
    #0080ff 75%,
    #0000ff 100%
  );
  animation: building-glow var(--duration) ease-in-out infinite var(--delay);
  box-shadow: 
    0 0 20px rgba(255, 0, 255, 0.5),
    inset 0 0 20px rgba(0, 255, 255, 0.3);
  clip-path: polygon(0% 100%, 0% 0%, 100% 0%, 100% 100%, 90% 100%, 90% 20%, 80% 20%, 80% 40%, 70% 40%, 70% 60%, 60% 60%, 60% 80%, 50% 80%, 50% 100%);
}

@keyframes building-glow {
  0%, 100% {
    box-shadow: 
      0 0 20px rgba(255, 0, 255, 0.5),
      inset 0 0 20px rgba(0, 255, 255, 0.3);
    filter: hue-rotate(0deg);
  }
  50% {
    box-shadow: 
      0 0 40px rgba(255, 0, 255, 0.8),
      inset 0 0 40px rgba(0, 255, 255, 0.6);
    filter: hue-rotate(30deg);
  }
}

/* Floating Pixels */
.floating-pixels {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
}

.pixel {
  position: absolute;
  width: var(--size);
  height: var(--size);
  background: #00ffff;
  animation: pixel-float var(--duration) ease-in-out infinite var(--delay);
  left: var(--x);
  top: var(--y);
  box-shadow: 0 0 10px #00ffff;
  image-rendering: pixelated;
}

@keyframes pixel-float {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.8;
    filter: hue-rotate(0deg);
  }
  25% {
    transform: translateY(-20px) scale(1.2);
    opacity: 1;
    filter: hue-rotate(90deg);
  }
  50% {
    transform: translateY(-40px) scale(0.8);
    opacity: 0.6;
    filter: hue-rotate(180deg);
  }
  75% {
    transform: translateY(-20px) scale(1.1);
    opacity: 0.9;
    filter: hue-rotate(270deg);
  }
}

/* Retro Sun/Moon */
.retro-sun {
  position: absolute;
  left: var(--x);
  top: var(--y);
  width: var(--size);
  height: var(--size);
  background: radial-gradient(circle, #ffff00 0%, #ff8000 50%, #ff0080 100%);
  border-radius: 50%;
  animation: retro-sun-pulse var(--duration) ease-in-out infinite;
  box-shadow: 
    0 0 50px rgba(255, 255, 0, 0.8),
    0 0 100px rgba(255, 128, 0, 0.6),
    0 0 150px rgba(255, 0, 128, 0.4);
  z-index: 2;
}

@keyframes retro-sun-pulse {
  0%, 100% {
    transform: scale(1);
    filter: hue-rotate(0deg);
  }
  50% {
    transform: scale(1.1);
    filter: hue-rotate(180deg);
  }
}

/* Neon Grid Lines */
.neon-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}

.neon-grid .grid-line {
  position: absolute;
  background: linear-gradient(90deg, transparent, #00ffff, transparent);
  height: 2px;
  width: 100%;
  top: var(--position);
  animation: neon-scan var(--duration) ease-in-out infinite var(--delay);
  box-shadow: 0 0 10px #00ffff;
}

.neon-grid .grid-line:nth-child(even) {
  transform: rotate(90deg);
  width: 100vh;
  height: 2px;
  left: var(--position);
  top: 0;
}

@keyframes neon-scan {
  0%, 100% {
    opacity: 0.2;
    transform: scaleX(0);
  }
  50% {
    opacity: 1;
    transform: scaleX(1);
  }
}

/* Retro Stars */
.retro-stars {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}

.star {
  position: absolute;
  width: var(--size);
  height: var(--size);
  background: #ffffff;
  left: var(--x);
  top: var(--y);
  animation: star-twinkle var(--duration) ease-in-out infinite var(--delay);
  box-shadow: 0 0 5px #ffffff;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
}

@keyframes star-twinkle {
  0%, 100% {
    opacity: 0.3;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.5);
  }
}

/* Pixel Mountains */
.pixel-mountains {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 30%;
  z-index: 1;
}

.mountain {
  position: absolute;
  bottom: 0;
  left: var(--x);
  width: var(--width);
  height: var(--height);
  background: linear-gradient(180deg, #8000ff 0%, #400080 100%);
  animation: mountain-glow var(--duration) ease-in-out infinite var(--delay);
  clip-path: polygon(0% 100%, 0% 60%, 20% 40%, 40% 50%, 60% 30%, 80% 45%, 100% 35%, 100% 100%);
  box-shadow: 0 0 30px rgba(128, 0, 255, 0.5);
}

@keyframes mountain-glow {
  0%, 100% {
    box-shadow: 0 0 30px rgba(128, 0, 255, 0.5);
    filter: hue-rotate(0deg);
  }
  50% {
    box-shadow: 0 0 50px rgba(128, 0, 255, 0.8);
    filter: hue-rotate(30deg);
  }
}

/* Retro Clouds */
.retro-clouds {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 40%;
  z-index: 1;
}

.cloud {
  position: absolute;
  left: var(--x);
  top: var(--y);
  width: var(--size);
  height: calc(var(--size) * 0.6);
  background: linear-gradient(180deg, #ffffff 0%, #e0e0e0 100%);
  animation: cloud-drift var(--duration) linear infinite var(--delay);
  border-radius: 50px;
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
}

.cloud::before {
  content: '';
  position: absolute;
  top: -30%;
  left: 10%;
  width: 40%;
  height: 60%;
  background: inherit;
  border-radius: 50px;
}

.cloud::after {
  content: '';
  position: absolute;
  top: -20%;
  right: 10%;
  width: 50%;
  height: 50%;
  background: inherit;
  border-radius: 50px;
}

@keyframes cloud-drift {
  0% {
    transform: translateX(-100px);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateX(calc(100vw + 100px));
    opacity: 0;
  }
}

/* Enhanced Retrowave Text Effects */
.retrowave-theme .hacker-text {
  font-family: 'Courier New', monospace;
  letter-spacing: 3px;
  animation: retrowave-glow 2s ease-in-out infinite alternate;
  text-shadow: 
    0 0 5px #ff00ff,
    0 0 10px #ff00ff,
    0 0 15px #ff00ff,
    0 0 20px #ff00ff,
    0 0 35px #ff00ff,
    0 0 40px #ff00ff;
}

@keyframes retrowave-glow {
  0% {
    text-shadow: 
      0 0 5px #ff00ff,
      0 0 10px #ff00ff,
      0 0 15px #ff00ff,
      0 0 20px #ff00ff,
      0 0 35px #ff00ff,
      0 0 40px #ff00ff;
    filter: hue-rotate(0deg);
  }
  100% {
    text-shadow: 
      0 0 10px #00ffff,
      0 0 20px #00ffff,
      0 0 30px #00ffff,
      0 0 40px #00ffff,
      0 0 50px #00ffff,
      0 0 60px #00ffff;
    filter: hue-rotate(180deg);
  }
}

/* Enhanced Retrowave Error Code */
.retrowave-theme .error-code {
  background: linear-gradient(45deg, #ff00ff, #00ffff, #8000ff, #ff0080);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 400% 400%;
  animation: retrowave-gradient 3s ease-in-out infinite;
  text-shadow: 
    0 0 30px rgba(255, 0, 255, 0.8),
    0 0 60px rgba(0, 255, 255, 0.6),
    0 0 90px rgba(128, 0, 255, 0.4);
}

@keyframes retrowave-gradient {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}
</style>

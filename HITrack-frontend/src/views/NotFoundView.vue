<template>
  <div class="not-found">
    <v-container fluid class="text-center">
      <!-- Animated 404 -->
      <div class="error-container">
        <div class="error-code">
          <span class="four">4</span>
          <span class="zero">0</span>
          <span class="four">4</span>
        </div>
      </div>

      <!-- Main Message -->
      <div class="error-message">
        <h1 class="text-h3 font-weight-bold mb-4">
          <span class="enhanced-text">Page Not Found</span>
        </h1>
        <p class="text-h6 mb-6">
          <span>The page you're looking for doesn't exist or has been moved.</span>
        </p>
      </div>

      <!-- Enhanced Background Elements for Normal Theme -->
      <div class="background-elements" v-if="!themeStore.isMatrix">
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

      <!-- Action Buttons -->
      <div class="action-buttons">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-home"
          @click="goHome"
          class="mr-4 mb-2"
        >
          Go Home
        </v-btn>
        
        <v-btn
          color="secondary"
          size="large"
          prepend-icon="mdi-arrow-left"
          @click="goBack"
          class="mb-2"
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



const goHome = () => {
  router.push('/')
}

const goBack = () => {
  router.back()
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

</style>

import type { GameEvent } from './types'

export type CueName = 'gong' | 'bell' | 'hit' | 'dodge' | 'sunrise' | 'defeat'

type Layer = Readonly<{
  kind: 'tone' | 'noise'
  wave: OscillatorType
  from: number
  to: number | null
  level: number
  at: number
  attack: number
  decay: number
}>

type Voice = Readonly<{ stop: () => void }>

type Engine = Readonly<{ ctx: AudioContext; master: GainNode; noise: AudioBuffer }>

type Bed = {
  gain: GainNode
  source: AudioBufferSourceNode
  timer: ReturnType<typeof setTimeout> | null
}

const STORAGE_KEY = 'desktop.sound'
const MASTER_GAIN = 0.25
const BED_SHARE = 0.3
const MAX_VOICES = 4
const MIN_ATTACK_S = 0.005
const MIN_RELEASE_S = 0.02
const FADE_S = 0.3
const BED_RELEASE_S = 0.25
const SILENT = 0.0001
const NOISE_SECONDS = 2
const NOISE_LEVEL = 0.5
const BED_LOWPASS_HZ = 380
const BAND_Q = 1.5
const CHIRP_GAP_MS: readonly [number, number] = [800, 3000]
const CHIRP_PULSES: readonly [number, number] = [2, 3]
const CHIRP_PITCH_HZ: readonly [number, number] = [4000, 5000]
const CHIRP_STEP_S = 0.09
const CHIRP_LEVEL = 0.4

function tone(
  from: number,
  level: number,
  decay: number,
  extra: Partial<Pick<Layer, 'to' | 'at' | 'attack' | 'wave'>> = {}
): Layer {
  return { kind: 'tone', wave: 'sine', to: null, at: 0, attack: 0.01, ...extra, from, level, decay }
}

function noise(from: number, level: number, decay: number): Layer {
  return { kind: 'noise', wave: 'sine', from, to: null, level, at: 0, attack: 0.005, decay }
}

const NOTES_HZ: readonly number[] = [523.25, 659.25, 783.99, 1046.5]

const CUES: Readonly<Record<CueName, readonly Layer[]>> = {
  gong: [tone(110, 0.9, 1.2), tone(220, 0.4, 0.9), tone(331, 0.25, 0.6)],
  bell: [tone(880, 0.5, 0.8, { attack: 0.02 }), tone(1320, 0.3, 0.6, { attack: 0.02 })],
  hit: [noise(1200, 0.6, 0.15), tone(160, 0.7, 0.19, { to: 70, attack: 0.005 })],
  dodge: [tone(600, 0.3, 0.14, { to: 900, attack: 0.01 })],
  sunrise: [
    ...NOTES_HZ.map((hz, index) => tone(hz, 0.45, 1, { at: index * 0.25, attack: 0.02 })),
    tone(500, 0.15, 0.5, { at: 1.3, to: 950, attack: 0.03, wave: 'triangle' })
  ],
  defeat: [tone(98, 0.8, 2, { to: 65, attack: 0.05 })]
}

let enabled = readEnabled()
let unlocked = false
let engine: Engine | null = null
let bed: Bed | null = null
let bedWanted = false
let bedHeld = false
let voices: Voice[] = []
const listeners = new Set<() => void>()

function readEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== 'off'
  } catch {
    return true
  }
}

function writeEnabled(on: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, on ? 'on' : 'off')
  } catch {
    return
  }
}

function safely(action: () => void): void {
  try {
    action()
  } catch {
    return
  }
}

function between(range: readonly [number, number]): number {
  return range[0] + Math.random() * (range[1] - range[0])
}

function makeNoise(ctx: AudioContext): AudioBuffer {
  const buffer = ctx.createBuffer(1, ctx.sampleRate * NOISE_SECONDS, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let index = 0; index < data.length; index += 1) data[index] = Math.random() * 2 - 1
  return buffer
}

function getEngine(): Engine | null {
  if (!enabled || !unlocked) return null
  if (engine) return engine
  const ctx = new AudioContext()
  const master = ctx.createGain()
  master.gain.value = MASTER_GAIN
  master.connect(ctx.destination)
  engine = { ctx, master, noise: makeNoise(ctx) }
  return engine
}

function shape(param: AudioParam, start: number, layer: Layer): number {
  const attack = Math.max(layer.attack, MIN_ATTACK_S)
  const decay = Math.max(layer.decay, MIN_RELEASE_S)
  param.setValueAtTime(SILENT, start)
  param.linearRampToValueAtTime(layer.level, start + attack)
  param.exponentialRampToValueAtTime(SILENT, start + attack + decay)
  return start + attack + decay
}

function makeSource(e: Engine, layer: Layer, start: number, end: number): AudioScheduledSourceNode {
  if (layer.kind === 'noise') {
    const source = e.ctx.createBufferSource()
    source.buffer = e.noise
    source.loop = true
    return source
  }
  const osc = e.ctx.createOscillator()
  osc.type = layer.wave
  osc.frequency.setValueAtTime(layer.from, start)
  if (layer.to !== null) osc.frequency.exponentialRampToValueAtTime(layer.to, end)
  return osc
}

function playLayer(
  e: Engine,
  layer: Layer,
  out: AudioNode,
  origin: number
): AudioScheduledSourceNode {
  const start = origin + layer.at
  const amp = e.ctx.createGain()
  const end = shape(amp.gain, start, layer)
  const source = makeSource(e, layer, start, end)
  if (layer.kind === 'noise') {
    const band = e.ctx.createBiquadFilter()
    band.type = 'bandpass'
    band.frequency.value = layer.from
    band.Q.value = BAND_Q
    source.connect(band)
    band.connect(amp)
  } else {
    source.connect(amp)
  }
  amp.connect(out)
  source.start(start)
  source.stop(end + 0.05)
  return source
}

function startVoice(e: Engine, layers: readonly Layer[], origin: number): Voice {
  const bus = e.ctx.createGain()
  bus.connect(e.master)
  const sources = layers.map((layer) => playLayer(e, layer, bus, origin))
  let remaining = sources.length
  const voice: Voice = {
    stop: () => {
      const now = e.ctx.currentTime
      bus.gain.setTargetAtTime(0, now, MIN_RELEASE_S / 2)
      sources.forEach((source) => safely(() => source.stop(now + MIN_RELEASE_S * 3)))
    }
  }
  sources.forEach((source) => {
    source.onended = () => {
      remaining -= 1
      if (remaining > 0) return
      voices = voices.filter((candidate) => candidate !== voice)
      bus.disconnect()
    }
  })
  return voice
}

function admit(voice: Voice): void {
  voices.push(voice)
  while (voices.length > MAX_VOICES) voices.shift()?.stop()
}

export function playCue(name: CueName, delay = 0): void {
  safely(() => {
    const e = getEngine()
    if (!e) return
    admit(startVoice(e, CUES[name], e.ctx.currentTime + delay))
  })
}

function chirp(e: Engine, current: Bed): void {
  const pulses = Math.round(between(CHIRP_PULSES))
  const pitch = between(CHIRP_PITCH_HZ)
  const origin = e.ctx.currentTime
  for (let index = 0; index < pulses; index += 1) {
    const layer = tone(pitch, CHIRP_LEVEL, 0.04, { at: index * CHIRP_STEP_S, attack: 0.005 })
    playLayer(e, layer, current.gain, origin)
  }
}

function scheduleChirp(current: Bed): void {
  current.timer = setTimeout(() => {
    safely(() => {
      const e = getEngine()
      if (!e || bed !== current) return
      chirp(e, current)
      scheduleChirp(current)
    })
  }, between(CHIRP_GAP_MS))
}

function makeBed(e: Engine): Bed {
  const source = e.ctx.createBufferSource()
  source.buffer = e.noise
  source.loop = true
  const low = e.ctx.createBiquadFilter()
  low.type = 'lowpass'
  low.frequency.value = BED_LOWPASS_HZ
  const level = e.ctx.createGain()
  level.gain.value = NOISE_LEVEL
  const gain = e.ctx.createGain()
  gain.gain.value = 0
  source.connect(low)
  low.connect(level)
  level.connect(gain)
  gain.connect(e.master)
  source.start()
  const created: Bed = { gain, source, timer: null }
  scheduleChirp(created)
  return created
}

function rampBed(current: Bed, e: Engine, level: number, seconds: number): void {
  const param = current.gain.gain
  const now = e.ctx.currentTime
  param.cancelScheduledValues(now)
  param.setValueAtTime(param.value, now)
  param.linearRampToValueAtTime(level, now + seconds)
}

function teardownBed(): void {
  const current = bed
  bed = null
  if (!current) return
  if (current.timer !== null) clearTimeout(current.timer)
  const e = engine
  if (!e) return
  rampBed(current, e, 0, BED_RELEASE_S)
  current.source.onended = () => current.gain.disconnect()
  current.source.stop(e.ctx.currentTime + BED_RELEASE_S + 0.05)
}

function syncBed(): void {
  safely(() => {
    if (!bedWanted || !enabled || !unlocked) {
      teardownBed()
      return
    }
    const e = getEngine()
    if (!e) return
    if (!bed) bed = makeBed(e)
    rampBed(bed, e, bedHeld ? 0 : BED_SHARE, FADE_S)
  })
}

export function startBed(): void {
  bedWanted = true
  syncBed()
}

export function stopBed(): void {
  bedWanted = false
  bedHeld = false
  syncBed()
}

export function holdBed(held: boolean): void {
  bedHeld = held
  syncBed()
}

export function unlockSound(): void {
  unlocked = true
  safely(() => {
    const e = getEngine()
    if (e && e.ctx.state === 'suspended') void e.ctx.resume().catch(() => undefined)
  })
  syncBed()
}

export function armSoundUnlock(): () => void {
  const events = ['pointerdown', 'keydown'] as const
  const release = (): void => {
    events.forEach((name) => window.removeEventListener(name, onGesture))
  }
  function onGesture(): void {
    release()
    unlockSound()
  }
  events.forEach((name) => window.addEventListener(name, onGesture))
  return release
}

export function soundEnabled(): boolean {
  return enabled
}

export function subscribeSound(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setSoundEnabled(on: boolean): void {
  enabled = on
  writeEnabled(on)
  if (!on) voices.forEach((voice) => safely(voice.stop))
  syncBed()
  listeners.forEach((listener) => listener())
}

function isHit(
  event: GameEvent,
  attackTargets: ReadonlySet<string | null>,
  isAlly: (id: string | null) => boolean
): boolean {
  if (event.dmg === null || event.dmg <= 0) return false
  if (event.type === 'kubo_hit') return !attackTargets.has(event.dst)
  return (event.type === 'attack' || event.type === 'power') && isAlly(event.dst)
}

export function cuesFromEvents(
  events: readonly GameEvent[],
  isAlly: (id: string | null) => boolean
): readonly CueName[] {
  const attackTargets = new Set(
    events.filter((event) => event.type === 'attack' && event.dst !== null).map((e) => e.dst)
  )
  const out: CueName[] = []
  events.forEach((event) => {
    if (event.type === 'dodge') out.push('dodge')
    else if (isHit(event, attackTargets, isAlly)) out.push('hit')
  })
  return out
}

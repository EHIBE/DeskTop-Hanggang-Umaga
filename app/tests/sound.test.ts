import test from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import { installWindow, makeEvent, RENDERER_SRC, readText } from './helpers'

type ParamLog = {
  value: number
  linear: number[]
  exponential: number[]
  targets: number[]
  sets: number[]
}

type NodeLog = {
  kind: string
  gain?: ParamLog
  freq?: ParamLog
  starts: number[]
  stops: number[]
  connected: unknown[]
}

const nodes: NodeLog[] = []
let contexts = 0
const masters: ParamLog[] = []

function param(): ParamLog {
  return { value: 1, linear: [], exponential: [], targets: [], sets: [] }
}

function paramApi(log: ParamLog): Record<string, unknown> {
  return {
    set value(next: number) {
      log.value = next
    },
    get value(): number {
      return log.value
    },
    setValueAtTime: (value: number) => log.sets.push(value),
    linearRampToValueAtTime: (value: number) => log.linear.push(value),
    exponentialRampToValueAtTime: (value: number) => log.exponential.push(value),
    setTargetAtTime: (value: number) => log.targets.push(value)
  }
}

function makeNode(kind: string): NodeLog & Record<string, unknown> {
  const log: NodeLog = { kind, starts: [], stops: [], connected: [] }
  const node: NodeLog & Record<string, unknown> = Object.assign(log, {
    connect: (target: unknown) => log.connected.push(target),
    disconnect: () => undefined,
    start: (at: number) => log.starts.push(at),
    stop: (at: number) => log.stops.push(at),
    onended: null as null | (() => void)
  })
  nodes.push(log)
  return node
}

class FakeAudioContext {
  currentTime = 0
  sampleRate = 8000
  state = 'running'
  destination = { kind: 'destination' }
  constructor() {
    contexts += 1
  }
  resume(): Promise<void> {
    return Promise.resolve()
  }
  createGain(): unknown {
    const node = makeNode('gain')
    const log = param()
    node.gain = log
    masters.push(log)
    return { ...node, gain: paramApi(log) }
  }
  createOscillator(): unknown {
    const node = makeNode('osc')
    const log = param()
    node.freq = log
    return Object.assign(node, { frequency: paramApi(log), type: 'sine' })
  }
  createBufferSource(): unknown {
    return makeNode('noise')
  }
  createBiquadFilter(): unknown {
    return Object.assign(makeNode('filter'), { frequency: { value: 0 }, Q: { value: 0 } })
  }
  createBuffer(_channels: number, length: number): unknown {
    return { getChannelData: () => new Float32Array(length) }
  }
}

class ThrowingAudioContext {
  constructor() {
    throw new Error('no audio device')
  }
}

const CUE_NAMES = [
  'gong',
  'bell',
  'hit',
  'dodge',
  'sunrise',
  'defeat',
  'smoke',
  'lost',
  'found',
  'badge'
] as const

const storage = installWindow({
  addEventListener: () => undefined,
  removeEventListener: () => undefined
})

const sound = await import('../src/renderer/src/lib/sound')

function reset(): void {
  nodes.length = 0
}

function gains(): NodeLog[] {
  return nodes.filter((node) => node.kind === 'gain')
}

test('CueName union matches the cue list under test', () => {
  const source = readText(join(RENDERER_SRC, 'lib', 'sound.ts'))
  const block = /export type CueName =([\s\S]*?)\n\ntype Layer/.exec(source)
  assert.ok(block)
  const declared = [...block[1].matchAll(/'([a-z]+)'/g)].map((match) => match[1])
  assert.deepEqual(declared.sort(), [...CUE_NAMES].sort())
})

test('nothing plays before the first user gesture unlocks audio', () => {
  Reflect.set(globalThis, 'AudioContext', FakeAudioContext)
  sound.playCue('gong')
  assert.equal(contexts, 0)
  assert.equal(nodes.length, 0)
})

test('a failing audio device never throws', () => {
  Reflect.set(globalThis, 'AudioContext', ThrowingAudioContext)
  assert.doesNotThrow(() => sound.unlockSound())
  assert.doesNotThrow(() => sound.playCue('hit'))
  assert.doesNotThrow(() => sound.startBed())
  assert.doesNotThrow(() => sound.stopBed())
})

test('every cue builds well formed voices', () => {
  Reflect.set(globalThis, 'AudioContext', FakeAudioContext)
  sound.unlockSound()
  assert.equal(contexts, 1)
  for (const name of CUE_NAMES) {
    reset()
    sound.playCue(name, 0.5)
    const sources = nodes.filter((node) => node.kind === 'osc' || node.kind === 'noise')
    assert.ok(sources.length >= 1, name)
    for (const source of sources) {
      assert.equal(source.starts.length, 1, name)
      assert.equal(source.stops.length, 1, name)
      assert.ok(source.starts[0] >= 0.5, name)
      assert.ok(source.stops[0] > source.starts[0], name)
      if (source.freq) {
        for (const hz of [...source.freq.sets, ...source.freq.exponential]) {
          assert.ok(Number.isFinite(hz) && hz > 0 && hz < 20000, `${name} ${hz}`)
        }
      }
    }
    for (const gain of gains()) {
      for (const level of gain.gain?.linear ?? []) {
        assert.ok(level > 0 && level <= 1, `${name} level ${level}`)
      }
      for (const floor of gain.gain?.exponential ?? []) {
        assert.ok(floor > 0, `${name} exponential floor ${floor}`)
      }
    }
  }
})

test('the master gain leaves headroom', () => {
  assert.equal(masters[0].value, 0.25)
  assert.ok(masters.every((log) => log.value <= 1))
})

test('at most four voices sound at once', () => {
  reset()
  for (let index = 0; index < 7; index += 1) sound.playCue('bell')
  const stopped = gains().filter((gain) => (gain.gain?.targets.length ?? 0) > 0)
  assert.equal(stopped.length, 3)
})

test('muting persists, notifies and silences new cues', () => {
  let heard = 0
  const off = sound.subscribeSound(() => {
    heard += 1
  })
  sound.setSoundEnabled(false)
  assert.equal(sound.soundEnabled(), false)
  assert.equal(storage.getItem('desktop.sound'), 'off')
  assert.equal(heard, 1)
  reset()
  sound.playCue('gong')
  assert.equal(nodes.length, 0)
  sound.setSoundEnabled(true)
  assert.equal(storage.getItem('desktop.sound'), 'on')
  assert.equal(heard, 2)
  off()
  sound.setSoundEnabled(true)
  assert.equal(heard, 2)
})

test('armSoundUnlock returns a release that removes both listeners', () => {
  const added: string[] = []
  const removed: string[] = []
  installWindow({
    addEventListener: (name: string) => added.push(name),
    removeEventListener: (name: string) => removed.push(name)
  })
  const release = sound.armSoundUnlock()
  assert.deepEqual(added.sort(), ['keydown', 'pointerdown'])
  release()
  assert.deepEqual(removed.sort(), ['keydown', 'pointerdown'])
})

const ALLY = (id: string | null): boolean => id !== null && id.startsWith('u_')

test('cuesFromEvents maps events to cues in order', () => {
  const events = [
    makeEvent({ type: 'dodge', src: 'u_mug' }),
    makeEvent({ type: 'smoke' }),
    makeEvent({ type: 'lost', src: 'u_pen' }),
    makeEvent({ type: 'found', src: 'u_pen' }),
    makeEvent({ type: 'attack', src: 'e_aswang_1', dst: 'u_mug', dmg: 2 })
  ]
  assert.deepEqual(sound.cuesFromEvents(events, ALLY), ['dodge', 'smoke', 'lost', 'found', 'hit'])
})

test('cuesFromEvents ignores zero damage, null damage and hits on enemies', () => {
  const events = [
    makeEvent({ type: 'attack', src: 'e_aswang_1', dst: 'u_mug', dmg: 0 }),
    makeEvent({ type: 'attack', src: 'e_aswang_1', dst: 'u_mug', dmg: null }),
    makeEvent({ type: 'attack', src: 'u_mug', dst: 'e_aswang_1', dmg: 3 }),
    makeEvent({ type: 'heal', src: 'u_mug', dst: 'u_pen', dmg: 2 })
  ]
  assert.deepEqual(sound.cuesFromEvents(events, ALLY), [])
})

test('cuesFromEvents counts power damage on an ally and kubo hits once', () => {
  const power = makeEvent({ type: 'power', src: 'e_kapre_1', dst: 'u_mug', dmg: 1 })
  assert.deepEqual(sound.cuesFromEvents([power], ALLY), ['hit'])
  const kubo = makeEvent({ type: 'kubo_hit', src: 'e_aswang_1', dst: 'kubo', dmg: 2 })
  assert.deepEqual(sound.cuesFromEvents([kubo], ALLY), ['hit'])
  const covered = [
    makeEvent({ type: 'attack', src: 'e_aswang_1', dst: 'kubo', dmg: 2 }),
    makeEvent({ type: 'kubo_hit', src: 'e_aswang_1', dst: 'kubo', dmg: 2 })
  ]
  assert.deepEqual(
    sound.cuesFromEvents(covered, () => false),
    []
  )
  assert.deepEqual(sound.cuesFromEvents([], ALLY), [])
})

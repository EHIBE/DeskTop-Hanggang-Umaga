import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type {
  EnemySummary,
  GameEvent,
  NightSummary,
  NightUnit
} from '../src/renderer/src/lib/types'

export const APP_ROOT = fileURLToPath(new URL('../', import.meta.url))
export const REPO_ROOT = fileURLToPath(new URL('../../', import.meta.url))
export const RENDERER_SRC = join(APP_ROOT, 'src', 'renderer', 'src')

export function readText(path: string): string {
  return readFileSync(path, 'utf8')
}

export function walk(dir: string, extensions: readonly string[]): string[] {
  const found: string[] = []
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === '.venv' || name === '__pycache__') continue
    const full = join(dir, name)
    if (statSync(full).isDirectory()) found.push(...walk(full, extensions))
    else if (extensions.some((extension) => name.endsWith(extension))) found.push(full)
  }
  return found
}

export type FakeStorage = Storage & { data: Map<string, string> }

export function makeStorage(options: { throws?: boolean } = {}): FakeStorage {
  const data = new Map<string, string>()
  const fail = (): never => {
    throw new Error('storage unavailable')
  }
  const storage = {
    data,
    get length(): number {
      return data.size
    },
    clear: () => (options.throws ? fail() : data.clear()),
    getItem: (key: string) => (options.throws ? fail() : (data.get(key) ?? null)),
    key: (index: number) => [...data.keys()][index] ?? null,
    removeItem: (key: string) => (options.throws ? fail() : void data.delete(key)),
    setItem: (key: string, value: string) => (options.throws ? fail() : void data.set(key, value))
  }
  return storage as unknown as FakeStorage
}

export function installWindow(extra: Record<string, unknown> = {}): FakeStorage {
  const localStorage = makeStorage()
  Object.defineProperty(globalThis, 'window', {
    value: { localStorage, ...extra },
    configurable: true,
    writable: true
  })
  return localStorage
}

export function makeUnit(overrides: Partial<NightUnit> = {}): NightUnit {
  return {
    id: 'u_mug',
    hp: 5,
    hp_max: 5,
    cooldown: 0,
    is_down: false,
    is_move_legal: true,
    start_x_cm: 10,
    start_y_cm: 10,
    move_cm: 8,
    range_cm: 4,
    owner: null,
    status: [],
    badges: [],
    scars: 0,
    cooldown_cut: 0,
    smoked: false,
    ...overrides
  }
}

export function makeEnemy(overrides: Partial<EnemySummary> = {}): EnemySummary {
  return {
    id: 'e_aswang_1',
    type: 'aswang',
    part: null,
    hp: 3,
    hp_max: 3,
    x_cm: 20,
    y_cm: 5,
    intent: null,
    stunned: false,
    ...overrides
  }
}

export function makeNight(overrides: Partial<NightSummary> = {}): NightSummary {
  return {
    number: 1,
    turn: 1,
    difficulty: 'normal',
    players: [],
    units: [],
    enemies: [],
    chips: [],
    illegal_units: [],
    kubo_hp: 10,
    kubo_hp_max: 10,
    effects: [],
    effect_seconds_left: 0,
    smoke: [],
    ...overrides
  } as NightSummary
}

export function makeEvent(overrides: Partial<GameEvent> = {}): GameEvent {
  return {
    type: 'attack',
    src: null,
    dst: null,
    dmg: null,
    edge: null,
    pos: null,
    ...overrides
  }
}

import type { AppPhase, NightSummary } from './types'

export type HintKey = 'tut.telegraph' | 'tut.move' | 'tut.order' | 'tut.end_turn' | 'tut.push'

export const HINT_KEYS: readonly HintKey[] = [
  'tut.telegraph',
  'tut.move',
  'tut.order',
  'tut.end_turn',
  'tut.push'
]

const STORAGE_KEY = 'desktop.tutorial'
const LAST_CHAIN_TURN = 2
const LAST_PUSH_TURN = 3

export type HintContext = Readonly<{
  phase: AppPhase
  night: NightSummary
  seen: ReadonlySet<string>
}>

function isHintKey(value: unknown): value is HintKey {
  return typeof value === 'string' && HINT_KEYS.some((key) => key === value)
}

function readAll(): Record<string, unknown> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw === null) return {}
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {}
    return { ...parsed }
  } catch {
    return {}
  }
}

export function readSeen(campaignId: string): ReadonlySet<HintKey> {
  const stored = readAll()[campaignId]
  if (!Array.isArray(stored)) return new Set()
  return new Set(stored.filter(isHintKey))
}

export function writeSeen(campaignId: string, seen: ReadonlySet<HintKey>): void {
  try {
    const next = { ...readAll(), [campaignId]: [...seen] }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    return
  }
}

function tikbalangTelegraphed(night: NightSummary): boolean {
  return night.enemies.some(
    (enemy) => enemy.type === 'tikbalang' && enemy.intent !== null && !enemy.stunned
  )
}

function eligible(key: HintKey, night: NightSummary): boolean {
  if (key === 'tut.push') return night.turn <= LAST_PUSH_TURN && tikbalangTelegraphed(night)
  if (night.turn > LAST_CHAIN_TURN) return false
  if (key === 'tut.end_turn') return night.chips.length > 0 || night.turn >= 2
  return true
}

export function nextHint({ phase, night, seen }: HintContext): HintKey | null {
  if (phase !== 'PLAYER_PHASE') return null
  return HINT_KEYS.find((key) => !seen.has(key) && eligible(key, night)) ?? null
}

export function reservesHintSlot(night: NightSummary, seenAtMount: ReadonlySet<string>): boolean {
  if (night.turn > LAST_PUSH_TURN) return false
  return HINT_KEYS.some((key) => !seenAtMount.has(key))
}

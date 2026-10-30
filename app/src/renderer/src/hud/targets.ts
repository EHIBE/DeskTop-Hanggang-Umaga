import { say } from '../lib/copy'
import type { EnemySummary, IntentAction, PowerId, UnitSummary } from '../lib/types'

export type TargetKind = 'enemy' | 'ally' | 'none'

const POWER_TARGETS: Readonly<Record<PowerId, TargetKind | 'passive'>> = {
  none: 'passive',
  P01: 'ally',
  P02: 'ally',
  P03: 'enemy',
  P04: 'enemy',
  P05: 'none',
  P06: 'none',
  P07: 'passive',
  P08: 'none',
  P09: 'enemy',
  P10: 'none',
  P11: 'enemy',
  P12: 'enemy'
}

export function powerTarget(power: PowerId): TargetKind | 'passive' {
  return POWER_TARGETS[power]
}

export function actionTarget(action: IntentAction, power: PowerId): TargetKind {
  if (action === 'attack') return 'enemy'
  if (action === 'heal') return 'ally'
  const kind = powerTarget(power)
  return kind === 'passive' ? 'none' : kind
}

export function enemyLabel(enemies: readonly EnemySummary[], enemy: EnemySummary): string {
  const sameType = enemies.filter((other) => other.type === enemy.type && other.part === enemy.part)
  const index = sameType.findIndex((other) => other.id === enemy.id) + 1
  const base = say(`enemy.${enemy.type}`)
  const part = enemy.part === null ? '' : ` ${say(`enemy.${enemy.part}`)}`
  return sameType.length > 1 ? `${base}${part} ${index}` : `${base}${part}`
}

export function targetLabel(
  id: string,
  units: readonly UnitSummary[],
  enemies: readonly EnemySummary[]
): string {
  const unit = units.find((candidate) => candidate.id === id)
  if (unit) return unit.name
  const enemy = enemies.find((candidate) => candidate.id === id)
  return enemy ? enemyLabel(enemies, enemy) : id
}

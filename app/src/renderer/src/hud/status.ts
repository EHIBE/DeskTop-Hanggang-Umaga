import { say } from '../lib/copy'
import type { NightUnit } from '../lib/types'

export type UnitStatus = Readonly<{
  outTurns: number | null
  stolen: boolean
  lost: boolean
  unavailable: boolean
}>

const OUT_PATTERN = /^out_(\d+)$/

export function parseStatus(tags: readonly string[]): UnitStatus {
  let outTurns: number | null = null
  let stolen = false
  let lost = false
  tags.forEach((tag) => {
    const match = OUT_PATTERN.exec(tag)
    if (match) outTurns = Number(match[1])
    else if (tag.startsWith('stolen_by:')) stolen = true
    else if (tag === 'lost' || tag === 'off_desk') lost = true
  })
  return { outTurns, stolen, lost, unavailable: outTurns !== null || stolen || lost }
}

export type StatusKind = 'out' | 'stolen' | 'lost' | 'smoked'

export type StatusEntry = Readonly<{ kind: StatusKind; text: string }>

export function statusEntries(status: UnitStatus): readonly StatusEntry[] {
  const entries: StatusEntry[] = []
  if (status.outTurns !== null) {
    entries.push({ kind: 'out', text: say('status.out', { turns: status.outTurns }) })
  }
  if (status.stolen) entries.push({ kind: 'stolen', text: say('status.stolen') })
  if (status.lost) entries.push({ kind: 'lost', text: say('status.lost') })
  return entries
}

export function nightUnitEntries(unit: NightUnit): readonly StatusEntry[] {
  const entries = [...statusEntries(parseStatus(unit.status))]
  if (unit.smoked) entries.push({ kind: 'smoked', text: say('status.smoked') })
  return entries
}

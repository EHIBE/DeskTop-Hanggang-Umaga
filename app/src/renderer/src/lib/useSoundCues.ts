import { useEffect, useRef } from 'react'
import { holdBed, playCue, startBed, stopBed } from './sound'
import type { AppPhase, StateMessage } from './types'

type SeenEnemies = { night: number; ids: Set<string> }

function phaseCue(previous: AppPhase, phase: AppPhase): 'bell' | 'sunrise' | 'defeat' | null {
  if (phase === 'SUNRISE') return 'sunrise'
  if (phase === 'DEFEAT') return 'defeat'
  if (previous === 'PLAYER_PHASE' && phase === 'END_TURN_SNAPSHOT') return 'bell'
  return null
}

export function useSoundCues(state: StateMessage | null, inNight: boolean): void {
  const phase = state ? state.phase : null
  const previousRef = useRef<AppPhase | null>(null)
  const seenRef = useRef<SeenEnemies | null>(null)
  const night = state ? state.night : null
  const enemyIds = night ? night.enemies.map((enemy) => enemy.id) : []
  const enemyKey = enemyIds.join(',')
  const nightNumber = night ? night.number : null
  const nightTurn = night ? night.turn : null

  useEffect(() => {
    if (!inNight) return
    startBed()
    return stopBed
  }, [inNight])

  useEffect(() => {
    holdBed(phase === 'PAUSED')
  }, [phase])

  useEffect(() => {
    const previous = previousRef.current
    previousRef.current = phase
    if (previous === null || phase === null || previous === phase) return
    const cue = phaseCue(previous, phase)
    if (cue !== null) playCue(cue)
  }, [phase])

  useEffect(() => {
    if (!inNight || nightNumber === null || nightTurn === null) {
      seenRef.current = null
      return
    }
    const ids = enemyKey === '' ? [] : enemyKey.split(',')
    const seen = seenRef.current
    if (seen === null || seen.night !== nightNumber) {
      seenRef.current = { night: nightNumber, ids: new Set(ids) }
      if (nightTurn <= 1 && ids.length > 0) playCue('gong')
      return
    }
    const fresh = ids.filter((id) => !seen.ids.has(id))
    if (fresh.length === 0) return
    fresh.forEach((id) => seen.ids.add(id))
    playCue('gong')
  }, [inNight, nightNumber, nightTurn, enemyKey])
}

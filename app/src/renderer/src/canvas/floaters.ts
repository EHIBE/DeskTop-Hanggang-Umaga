import { palette } from '../lib/palette'
import type { GameEvent } from '../lib/types'
import { FONT } from './draw'

export const FLOAT_MS = 600
const RISE_PX = 48
const POOF_MS = 400
const POOF_OFFSETS: readonly (readonly [number, number])[] = [
  [-1, -1],
  [1, -1],
  [-1, 1],
  [1, 1]
]

export type Floater = Readonly<{
  kind: 'damage' | 'heal' | 'dodge' | 'poof'
  text: string
  x_cm: number
  y_cm: number
  start: number
}>

export type Locator = (id: string | null) => Readonly<{ x_cm: number; y_cm: number }> | null

export function floatersFromEvents(
  events: readonly GameEvent[],
  locate: Locator,
  now: number,
  dodgeText: string
): readonly Floater[] {
  const out: Floater[] = []
  const attackTargets = new Set(
    events.filter((event) => event.type === 'attack' && event.dst !== null).map((e) => e.dst)
  )
  events.forEach((event) => {
    const at = event.pos ?? locate(event.dst)
    if (at === null) return
    const base = { x_cm: at.x_cm, y_cm: at.y_cm, start: now }
    if (event.type === 'dodge') {
      out.push({ ...base, kind: 'dodge', text: dodgeText })
    } else if (event.type === 'heal' && event.dmg !== null && event.dmg > 0) {
      out.push({ ...base, kind: 'heal', text: `+${event.dmg}` })
    } else if (event.type === 'defeat_enemy') {
      out.push({ ...base, kind: 'poof', text: '' })
    } else if (
      (event.type === 'attack' || event.type === 'power' || event.type === 'kubo_hit') &&
      event.dmg !== null &&
      event.dmg > 0
    ) {
      if (event.type === 'kubo_hit' && attackTargets.has(event.dst)) return
      out.push({ ...base, kind: 'damage', text: `-${event.dmg}` })
    }
  })
  return out
}

export function drawFloaters(
  ctx: CanvasRenderingContext2D,
  floaters: readonly Floater[],
  toCanvas: (xCm: number, yCm: number) => readonly [number, number],
  now: number
): readonly Floater[] {
  const alive: Floater[] = []
  floaters.forEach((floater) => {
    const age = now - floater.start
    const life = floater.kind === 'poof' ? POOF_MS : FLOAT_MS
    if (age >= life) return
    alive.push(floater)
    const progress = Math.max(0, age) / life
    const [x, y] = toCanvas(floater.x_cm, floater.y_cm)
    if (floater.kind === 'poof') {
      const spread = 8 + Math.round(progress * 5) * 6
      const size = 12
      ctx.globalAlpha = 1 - progress
      ctx.fillStyle = palette.mist
      POOF_OFFSETS.forEach(([sx, sy]) => {
        ctx.fillRect(
          Math.round(x + sx * spread - size / 2),
          Math.round(y + sy * spread - size / 2),
          size,
          size
        )
      })
      ctx.globalAlpha = 1
      return
    }
    const rise = Math.round(progress * RISE_PX)
    const color =
      floater.kind === 'heal'
        ? palette.dahon
        : floater.kind === 'dodge'
          ? palette.moon
          : palette.ember
    ctx.globalAlpha = progress < 0.6 ? 1 : 1 - (progress - 0.6) / 0.4
    ctx.font = FONT
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    const width = Math.ceil(ctx.measureText(floater.text).width) + 16
    const top = Math.round(y - 72 - rise)
    ctx.fillStyle = palette.ink
    ctx.fillRect(Math.round(x - width / 2), top, width, 28)
    ctx.fillStyle = color
    ctx.fillText(floater.text, Math.round(x), top + 15)
    ctx.globalAlpha = 1
  })
  return alive
}

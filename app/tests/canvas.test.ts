import test from 'node:test'
import assert from 'node:assert/strict'
import { drawGuideArrow, drawIntentArrow } from '../src/renderer/src/canvas/arrows'
import { drawSmoke } from '../src/renderer/src/canvas/smoke'
import {
  drawMoveRing,
  drawRemoveMark,
  drawStartGhost,
  type RingSpec
} from '../src/renderer/src/canvas/rings'
import { palette } from '../src/renderer/src/lib/palette'
import type { SmokeCloud } from '../src/renderer/src/lib/types'

type Call = readonly [string, ...unknown[]]

type Recorder = Readonly<{ ctx: CanvasRenderingContext2D; calls: Call[] }>

function recorder(): Recorder {
  const calls: Call[] = []
  const target = {}
  const ctx = new Proxy(target, {
    get(_target, name) {
      if (name === 'measureText') {
        return (text: string) => ({ width: text.length * 16 })
      }
      return (...args: unknown[]) => {
        calls.push([String(name), ...args])
      }
    },
    set(_target, name, value) {
      calls.push([`set:${String(name)}`, value])
      return true
    }
  }) as unknown as CanvasRenderingContext2D
  return { ctx, calls }
}

function named(calls: readonly Call[], name: string): Call[] {
  return calls.filter((call) => call[0] === name)
}

function dashes(calls: readonly Call[]): unknown[] {
  return named(calls, 'setLineDash').map((call) => call[1])
}

function colors(calls: readonly Call[]): unknown[] {
  return named(calls, 'set:strokeStyle').map((call) => call[1])
}

const STOP_SHORT = 52
const HEAD = 20

test('intent arrow draws nothing when the span is shorter than head plus stop', () => {
  const { ctx, calls } = recorder()
  drawIntentArrow(ctx, 0, 0, 40, 0, 3)
  drawIntentArrow(ctx, 5, 5, 5, 5, 3)
  assert.equal(calls.length, 0)
})

test('intent arrow stops short of the target and prints the damage', () => {
  const { ctx, calls } = recorder()
  drawIntentArrow(ctx, 0, 0, 300, 0, 7)
  const moves = named(calls, 'moveTo')
  assert.deepEqual(moves[0].slice(1), [40, 0])
  const tail = named(calls, 'lineTo')[0]
  assert.deepEqual(tail.slice(1), [300 - STOP_SHORT - HEAD, 0])
  assert.deepEqual(moves[1].slice(1), [300 - STOP_SHORT, 0])
  assert.ok(named(calls, 'fillText').some((call) => call[1] === '7'))
  assert.ok(colors(calls).includes(palette.sindak))
})

test('intent arrow is rotation safe', () => {
  const { ctx, calls } = recorder()
  drawIntentArrow(ctx, 0, 0, 0, 400, 2)
  const tip = named(calls, 'moveTo')[1]
  assert.ok(Math.abs(Number(tip[1])) < 1e-9)
  assert.ok(Math.abs(Number(tip[2]) - (400 - STOP_SHORT)) < 1e-9)
  assert.ok(
    calls.every((call) => call.every((arg) => typeof arg !== 'number' || !Number.isNaN(arg)))
  )
})

test('guide arrow is dashed for the shaft and solid for the head', () => {
  const { ctx, calls } = recorder()
  drawGuideArrow(ctx, 10, 10, 310, 10, palette.lantern)
  assert.deepEqual(dashes(calls), [[16, 10], []])
  assert.deepEqual(colors(calls), [palette.lantern])
  const { ctx: shortCtx, calls: shortCalls } = recorder()
  drawGuideArrow(shortCtx, 0, 0, 30, 0, palette.lantern)
  assert.equal(shortCalls.length, 0)
})

test('move ring is skipped for a non positive radius', () => {
  const { ctx, calls } = recorder()
  const ring: RingSpec = {
    centerX: 100,
    centerY: 100,
    radiusPx: 0,
    unitX: 100,
    unitY: 100,
    legal: true,
    down: false
  }
  drawMoveRing(ctx, ring)
  drawMoveRing(ctx, { ...ring, radiusPx: -5 })
  assert.equal(calls.length, 0)
})

test('move ring differs by shape as well as color for legal and illegal', () => {
  const base: RingSpec = {
    centerX: 200,
    centerY: 200,
    radiusPx: 80,
    unitX: 200,
    unitY: 200,
    legal: true,
    down: false
  }
  const legal = recorder()
  const illegal = recorder()
  drawMoveRing(legal.ctx, base)
  drawMoveRing(illegal.ctx, { ...base, legal: false })
  assert.deepEqual(dashes(legal.calls)[0], [])
  assert.deepEqual(dashes(illegal.calls)[0], [16, 10])
  assert.equal(colors(legal.calls)[0], palette.kawayan)
  assert.equal(colors(illegal.calls)[0], palette.sindak)
  assert.equal(named(legal.calls, 'lineTo').length, 2)
  assert.equal(named(illegal.calls, 'lineTo').length, 2)
  assert.equal(named(legal.calls, 'moveTo').length, 1)
  assert.equal(named(illegal.calls, 'moveTo').length, 2)
})

test('a downed unit ring is a faint dotted circle with no badge', () => {
  const { ctx, calls } = recorder()
  drawMoveRing(ctx, {
    centerX: 50,
    centerY: 50,
    radiusPx: 40,
    unitX: 50,
    unitY: 50,
    legal: true,
    down: true
  })
  assert.deepEqual(dashes(calls)[0], [2, 8])
  assert.equal(colors(calls)[0], palette.slate)
  assert.equal(named(calls, 'fillRect').length, 0)
})

test('start ghost without an image still draws a dashed box', () => {
  const { ctx, calls } = recorder()
  drawStartGhost(ctx, null, 100, 100, 4)
  assert.equal(named(calls, 'drawImage').length, 0)
  assert.equal(named(calls, 'strokeRect').length, 1)
  assert.deepEqual(named(calls, 'strokeRect')[0].slice(1), [64, 64, 72, 72])
})

test('remove mark draws a circle, a cross and a label', () => {
  const { ctx, calls } = recorder()
  drawRemoveMark(ctx, 200, 200, 'Remove')
  assert.equal(named(calls, 'arc').length, 1)
  assert.equal(named(calls, 'lineTo').length, 2)
  assert.ok(named(calls, 'fillText').some((call) => call[1] === 'Remove'))
})

const CLOUD: SmokeCloud = { source_id: 'e_kapre_1', x_cm: 10, y_cm: 10, radius_cm: 6 }
const toCanvas = (x: number, y: number): [number, number] => [x * 10, y * 10]

test('smoke draws nothing for no clouds', () => {
  const { ctx, calls } = recorder()
  drawSmoke(ctx, [], toCanvas, 10, 0, false, 'Smoke')
  assert.equal(calls.length, 0)
})

test('smoke is frozen when reduced motion is on', () => {
  const first = recorder()
  const later = recorder()
  drawSmoke(first.ctx, [CLOUD], toCanvas, 10, 0, true, 'Smoke')
  drawSmoke(later.ctx, [CLOUD], toCanvas, 10, 123456, true, 'Smoke')
  assert.deepEqual(first.calls, later.calls)
})

test('smoke animates between steps and holds inside one step', () => {
  const a = recorder()
  const b = recorder()
  const c = recorder()
  drawSmoke(a.ctx, [CLOUD], toCanvas, 10, 0, false, 'Smoke')
  drawSmoke(b.ctx, [CLOUD], toCanvas, 10, 599, false, 'Smoke')
  drawSmoke(c.ctx, [CLOUD], toCanvas, 10, 600, false, 'Smoke')
  assert.deepEqual(a.calls, b.calls)
  assert.notDeepEqual(a.calls, c.calls)
})

test('smoke cells stay on the pixel grid inside the cloud and the ring is dashed', () => {
  const { ctx, calls } = recorder()
  drawSmoke(ctx, [CLOUD], toCanvas, 10, 0, false, 'Smoke')
  const cells = named(calls, 'fillRect').filter((call) => call[4] === 12)
  assert.ok(cells.length > 10)
  for (const cell of cells) {
    assert.ok(Number.isInteger(cell[1]) && Number.isInteger(cell[2]))
    assert.equal(cell[3], 12)
    const dx = Number(cell[1]) + 6 - 100
    const dy = Number(cell[2]) + 6 - 100
    assert.ok(Math.hypot(dx, dy) <= 60 + 1e-9)
  }
  assert.ok(dashes(calls).some((pattern) => JSON.stringify(pattern) === '[8,8]'))
  assert.equal(named(calls, 'arc').length, 1)
  assert.ok(named(calls, 'fillText').some((call) => call[1] === 'Smoke'))
})

test('smoke draws one ring and label per cloud', () => {
  const { ctx, calls } = recorder()
  drawSmoke(ctx, [CLOUD, { ...CLOUD, x_cm: 30 }], toCanvas, 10, 0, true, 'Smoke')
  assert.equal(named(calls, 'arc').length, 2)
  assert.equal(named(calls, 'fillText').filter((call) => call[1] === 'Smoke').length, 2)
})

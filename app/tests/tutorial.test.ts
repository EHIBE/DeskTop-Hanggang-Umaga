import test from 'node:test'
import assert from 'node:assert/strict'
import {
  HINT_KEYS,
  nextHint,
  readSeen,
  reservesHintSlot,
  writeSeen,
  type HintKey
} from '../src/renderer/src/lib/tutorial'
import { copyKeys } from '../src/renderer/src/lib/copy'
import type { AppPhase, Chip, NightSummary } from '../src/renderer/src/lib/types'
import { installWindow, makeEnemy, makeNight, makeStorage } from './helpers'

const CHIP: Chip = { chip_id: 'c1', unit_id: 'u_mug', action: 'attack', target_id: null }
const TELEGRAPH = makeEnemy({
  id: 'e_tikbalang_1',
  type: 'tikbalang',
  intent: { target_id: 'u_mug', dmg: 2 }
})
const ALL_BUT_PUSH: readonly string[] = ['tut.telegraph', 'tut.move', 'tut.order', 'tut.end_turn']

function hint(
  turn: number,
  seen: readonly string[],
  extra: Partial<NightSummary> = {},
  phase: AppPhase = 'PLAYER_PHASE'
): HintKey | null {
  return nextHint({ phase, night: makeNight({ turn, ...extra }), seen: new Set(seen) })
}

function setStorage(storage: Storage): void {
  Object.defineProperty(globalThis, 'window', {
    value: { localStorage: storage },
    configurable: true,
    writable: true
  })
}

test('hint keys all exist in the copy deck', () => {
  for (const key of HINT_KEYS) assert.ok((copyKeys as readonly string[]).includes(key), key)
})

test('hints only show during the player phase', () => {
  assert.equal(hint(1, [], {}, 'RESOLVE_ENEMY'), null)
  assert.equal(hint(1, [], {}, 'PAUSED'), null)
  assert.equal(hint(1, []), 'tut.telegraph')
})

test('hints advance through the chain as each one is seen', () => {
  const seen: HintKey[] = []
  const order: (HintKey | null)[] = []
  for (let step = 0; step < 4; step += 1) {
    const next = hint(1, seen, { chips: [CHIP] })
    order.push(next)
    if (next) seen.push(next)
  }
  assert.deepEqual(order, ['tut.telegraph', 'tut.move', 'tut.order', 'tut.end_turn'])
  assert.equal(hint(1, seen, { chips: [CHIP] }), null)
})

test('end turn hint waits for a chip on turn 1 and shows on turn 2', () => {
  const seen = ['tut.telegraph', 'tut.move', 'tut.order']
  assert.equal(hint(1, seen), null)
  assert.equal(hint(1, seen, { chips: [CHIP] }), 'tut.end_turn')
  assert.equal(hint(2, seen), 'tut.end_turn')
})

test('chain hints stop after turn 2', () => {
  assert.equal(hint(3, []), null)
  assert.equal(hint(8, []), null)
})

test('push hint needs a live tikbalang telegraph within turn 3', () => {
  assert.equal(hint(3, ALL_BUT_PUSH), null)
  assert.equal(hint(3, ALL_BUT_PUSH, { enemies: [TELEGRAPH] }), 'tut.push')
  assert.equal(hint(4, ALL_BUT_PUSH, { enemies: [TELEGRAPH] }), null)
  assert.equal(hint(3, ALL_BUT_PUSH, { enemies: [{ ...TELEGRAPH, stunned: true }] }), null)
  assert.equal(hint(3, ALL_BUT_PUSH, { enemies: [{ ...TELEGRAPH, intent: null }] }), null)
  assert.equal(hint(3, ALL_BUT_PUSH, { enemies: [makeEnemy({ intent: TELEGRAPH.intent })] }), null)
})

test('reservesHintSlot holds the slot until turn 3 while hints remain', () => {
  assert.equal(reservesHintSlot(makeNight({ turn: 1 }), new Set()), true)
  assert.equal(reservesHintSlot(makeNight({ turn: 3 }), new Set()), true)
  assert.equal(reservesHintSlot(makeNight({ turn: 4 }), new Set()), false)
  assert.equal(reservesHintSlot(makeNight({ turn: 1 }), new Set(HINT_KEYS)), false)
})

test('writeSeen then readSeen round trips per campaign', () => {
  installWindow()
  writeSeen('camp-a', new Set<HintKey>(['tut.move']))
  writeSeen('camp-b', new Set<HintKey>(['tut.push', 'tut.order']))
  assert.deepEqual([...readSeen('camp-a')], ['tut.move'])
  assert.deepEqual([...readSeen('camp-b')].sort(), ['tut.order', 'tut.push'])
  assert.equal(readSeen('camp-c').size, 0)
})

test('readSeen drops unknown keys and survives corrupt storage', () => {
  const storage = installWindow()
  storage.setItem('desktop.tutorial', JSON.stringify({ a: ['tut.move', 'bogus', 7, null] }))
  assert.deepEqual([...readSeen('a')], ['tut.move'])
  const corrupt = ['not json', '[]', 'null', '42', '"str"', JSON.stringify({ a: 'tut.move' })]
  for (const raw of corrupt) {
    storage.setItem('desktop.tutorial', raw)
    assert.equal(readSeen('a').size, 0, raw)
  }
})

test('readSeen and writeSeen never throw when localStorage throws', () => {
  setStorage(makeStorage({ throws: true }))
  assert.equal(readSeen('a').size, 0)
  assert.doesNotThrow(() => writeSeen('a', new Set<HintKey>(['tut.move'])))
})

test('readSeen and writeSeen never throw when window is missing', () => {
  Reflect.deleteProperty(globalThis, 'window')
  assert.equal(readSeen('a').size, 0)
  assert.doesNotThrow(() => writeSeen('a', new Set<HintKey>()))
})

test('writeSeen recovers when the stored blob was corrupt', () => {
  const storage = installWindow()
  storage.setItem('desktop.tutorial', 'garbage')
  writeSeen('a', new Set<HintKey>(['tut.move']))
  assert.deepEqual([...readSeen('a')], ['tut.move'])
})

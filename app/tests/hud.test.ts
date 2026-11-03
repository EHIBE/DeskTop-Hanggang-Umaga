import test from 'node:test'
import assert from 'node:assert/strict'
import { setLang } from '../src/renderer/src/lib/lang'
import { isCopyKey } from '../src/renderer/src/lib/copy'
import { nightUnitEntries, parseStatus, statusEntries } from '../src/renderer/src/hud/status'
import { actionTarget, enemyLabel, powerTarget, targetLabel } from '../src/renderer/src/hud/targets'
import { MOOD_BORDER, MOOD_KEY, MOOD_TEXT } from '../src/renderer/src/hud/mood'
import type { PowerId, UnitSummary } from '../src/renderer/src/lib/types'
import { makeEnemy, makeUnit } from './helpers'

setLang('en')

test('parseStatus reads out, stolen, lost and off_desk tags', () => {
  assert.deepEqual(parseStatus([]), {
    outTurns: null,
    stolen: false,
    lost: false,
    unavailable: false
  })
  assert.equal(parseStatus(['out_2']).outTurns, 2)
  assert.equal(parseStatus(['out_2']).unavailable, true)
  assert.equal(parseStatus(['stolen_by:e_duwende_1']).stolen, true)
  assert.equal(parseStatus(['lost']).lost, true)
  assert.equal(parseStatus(['off_desk']).lost, true)
  assert.equal(parseStatus(['shielded', 'out_x']).unavailable, false)
})

test('parseStatus out_0 still counts as unavailable', () => {
  const status = parseStatus(['out_0'])
  assert.equal(status.outTurns, 0)
  assert.equal(status.unavailable, true)
})

test('statusEntries gives a kind and filled text for every flag', () => {
  const entries = statusEntries(parseStatus(['out_3', 'stolen_by:e1', 'lost']))
  assert.deepEqual(
    entries.map((entry) => entry.kind),
    ['out', 'stolen', 'lost']
  )
  assert.match(entries[0].text, /3/)
  assert.ok(entries.every((entry) => entry.text.length > 0 && !entry.text.includes('[')))
})

test('nightUnitEntries adds the smoked entry', () => {
  assert.deepEqual(nightUnitEntries(makeUnit()), [])
  const entries = nightUnitEntries(makeUnit({ smoked: true, status: ['out_1'] }))
  assert.deepEqual(
    entries.map((entry) => entry.kind),
    ['out', 'smoked']
  )
})

test('every power id has a target kind', () => {
  const ids: PowerId[] = ['none', 'P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07']
  ids.push('P08', 'P09', 'P10', 'P11', 'P12')
  for (const id of ids) assert.ok(['enemy', 'ally', 'none', 'passive'].includes(powerTarget(id)))
  assert.equal(powerTarget('P03'), 'enemy')
  assert.equal(powerTarget('P01'), 'ally')
})

test('actionTarget follows the action first and the power second', () => {
  assert.equal(actionTarget('attack', 'P01'), 'enemy')
  assert.equal(actionTarget('heal', 'P03'), 'ally')
  assert.equal(actionTarget('power', 'P03'), 'enemy')
  assert.equal(actionTarget('power', 'P01'), 'ally')
  assert.equal(actionTarget('power', 'P07'), 'none')
  assert.equal(actionTarget('power', 'none'), 'none')
  assert.equal(actionTarget('power', 'P05'), 'none')
})

test('enemyLabel numbers duplicates and names parts', () => {
  const a = makeEnemy({ id: 'e1' })
  const b = makeEnemy({ id: 'e2' })
  const upper = makeEnemy({ id: 'e3', type: 'manananggal', part: 'upper' })
  const lower = makeEnemy({ id: 'e4', type: 'manananggal', part: 'lower' })
  const all = [a, b, upper, lower]
  assert.equal(enemyLabel(all, a), 'Aswang 1')
  assert.equal(enemyLabel(all, b), 'Aswang 2')
  assert.equal(enemyLabel([a], a), 'Aswang')
  assert.notEqual(enemyLabel(all, upper), enemyLabel(all, lower))
  assert.ok(!enemyLabel(all, upper).includes('undefined'))
})

test('targetLabel prefers unit names, then enemy labels, then the raw id', () => {
  const unit = { id: 'u_mug', name: 'Mug' } as UnitSummary
  const enemy = makeEnemy({ id: 'e1', type: 'kapre' })
  assert.equal(targetLabel('u_mug', [unit], [enemy]), 'Mug')
  assert.equal(targetLabel('e1', [unit], [enemy]), enemyLabel([enemy], enemy))
  assert.equal(targetLabel('zzz', [unit], [enemy]), 'zzz')
})

test('mood maps cover every mood and use valid copy keys', () => {
  const moods = ['kalmado', 'kaba', 'takot', 'tagumpay', 'umaga'] as const
  for (const mood of moods) {
    assert.ok(MOOD_BORDER[mood].startsWith('border-gabi-'))
    assert.ok(MOOD_TEXT[mood].startsWith('text-gabi-'))
    assert.ok(isCopyKey(MOOD_KEY[mood]))
  }
  for (const map of [MOOD_BORDER, MOOD_TEXT, MOOD_KEY]) {
    assert.deepEqual(Object.keys(map).sort(), [...moods].sort())
  }
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { speakerSlot } from '../src/renderer/src/lib/speaker'

const PLAYERS = ['Ana', 'Ben', 'Carla', 'Dino']

test('speakerSlot maps names to slots 1 to 4', () => {
  assert.equal(speakerSlot('Ana', PLAYERS), 1)
  assert.equal(speakerSlot('Dino', PLAYERS), 4)
})

test('speakerSlot ignores case and padding', () => {
  assert.equal(speakerSlot('  bEn ', PLAYERS), 2)
  assert.equal(speakerSlot('CARLA', ['  carla  ']), 1)
})

test('speakerSlot returns null for empty, unknown and overflow speakers', () => {
  assert.equal(speakerSlot(null, PLAYERS), null)
  assert.equal(speakerSlot(undefined, PLAYERS), null)
  assert.equal(speakerSlot('', PLAYERS), null)
  assert.equal(speakerSlot('Zed', PLAYERS), null)
  assert.equal(speakerSlot('Eli', [...PLAYERS, 'Eli']), null)
  assert.equal(speakerSlot('Ana', []), null)
})

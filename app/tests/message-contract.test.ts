import test from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import { REPO_ROOT, RENDERER_SRC, readText, walk } from './helpers'

function unique(values: Iterable<string>): string[] {
  return [...new Set(values)].sort()
}

function matches(text: string, pattern: RegExp): string[] {
  return [...text.matchAll(pattern)].map((match) => match[1])
}

const SERVER_PY = readText(join(REPO_ROOT, 'backend', 'server.py'))
const NIGHT_PY = readText(join(REPO_ROOT, 'backend', 'game', 'night.py'))
const SOCKET_TS = readText(join(RENDERER_SRC, 'lib', 'socket.ts'))
const TYPES_TS = readText(join(RENDERER_SRC, 'lib', 'types.ts'))

const EMITTED = unique([
  ...matches(SERVER_PY, /"type":\s*"([a-z_.]+)"/g),
  ...matches(NIGHT_PY, /"type":\s*"([a-z_.]+)"/g)
]).filter((type) => type !== 'state.changed')

const FILTER_BLOCK = /const SERVER_TYPES[^[]*\[([\s\S]*?)\]\)/.exec(SOCKET_TS)
const ACCEPTED = unique(matches(FILTER_BLOCK?.[1] ?? '', /'([a-z_.]+)'/g))

const CLIENT_BLOCK = TYPES_TS.slice(TYPES_TS.indexOf('export type CampaignStartMessage'))
const CLIENT_UNION = unique(matches(CLIENT_BLOCK, /type:\s*'([a-z_.]+)'/g))

const SERVER_ACCEPTS = unique(matches(SERVER_PY, /type:\s*Literal\["([a-z_.]+)"\]/g))

function sentByRenderer(): string[] {
  const sent: string[] = []
  for (const file of walk(RENDERER_SRC, ['.ts', '.tsx'])) {
    if (file.endsWith('types.ts')) continue
    sent.push(...matches(readText(file), /\bsend\(\s*\{\s*type:\s*'([a-z_.]+)'/g))
  }
  return unique(sent)
}

function consumerSource(): string {
  return walk(RENDERER_SRC, ['.ts', '.tsx'])
    .filter((file) => !file.endsWith('types.ts') && !file.endsWith('socket.ts'))
    .map(readText)
    .join('\n')
}

test('the scan finds the messages the backend is known to emit', () => {
  for (const type of ['state', 'notice', 'moment', 'events', 'summon.result', 'recap', 'sprite']) {
    assert.ok(EMITTED.includes(type), type)
  }
  assert.ok(EMITTED.length >= 17)
})

test('every server message type is let through the socket filter', () => {
  assert.deepEqual(
    EMITTED.filter((type) => !ACCEPTED.includes(type)),
    []
  )
})

test('the socket filter lists no type the backend never emits', () => {
  assert.deepEqual(
    ACCEPTED.filter((type) => !EMITTED.includes(type)),
    []
  )
})

test('every server message type has a ServerMessage union member', () => {
  const members = unique(
    matches(TYPES_TS, /\btype:\s*'([a-z_.]+)'/g).filter((type) => EMITTED.includes(type))
  )
  assert.deepEqual(
    EMITTED.filter((type) => !members.includes(type)),
    []
  )
})

const CARRIED_BY_STATE: Readonly<Record<string, string>> = {
  recap: 'recap: RecapPayload | null',
  settings: 'settings: SettingsValues',
  sprite: 'sprite_png: string | null'
}

test('every server message type is consumed or its data rides on the state message', () => {
  const source = consumerSource()
  const unhandled = EMITTED.filter(
    (type) => !new RegExp(`type\\s*(?:===|!==)\\s*'${type}'|case\\s*'${type}'`).test(source)
  )
  assert.deepEqual(unhandled.sort(), Object.keys(CARRIED_BY_STATE).sort())
  for (const type of unhandled) assert.ok(TYPES_TS.includes(CARRIED_BY_STATE[type]), type)
})

test('every message type the renderer sends is in the ClientMessage union', () => {
  const sent = sentByRenderer()
  assert.ok(sent.length >= 30)
  assert.deepEqual(
    sent.filter((type) => !CLIENT_UNION.includes(type)),
    []
  )
})

test('every message type the renderer sends is accepted by the server', () => {
  assert.ok(SERVER_ACCEPTS.length >= 30)
  assert.deepEqual(
    sentByRenderer().filter((type) => !SERVER_ACCEPTS.includes(type)),
    []
  )
})

test('the ClientMessage union and the server accept list are the same set', () => {
  assert.deepEqual(
    CLIENT_UNION.filter((type) => !SERVER_ACCEPTS.includes(type)),
    []
  )
  assert.deepEqual(
    SERVER_ACCEPTS.filter((type) => !CLIENT_UNION.includes(type)),
    []
  )
})

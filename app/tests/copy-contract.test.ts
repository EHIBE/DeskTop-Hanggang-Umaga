import test from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import { copyKeys, isCopyKey, t } from '../src/renderer/src/lib/copy'
import { MOOD_KEY } from '../src/renderer/src/hud/mood'
import { REPO_ROOT, RENDERER_SRC, readText, walk } from './helpers'

const PLACEHOLDER = /\[([A-Za-z_]+)\]/g

function placeholders(text: string): string[] {
  return [...text.matchAll(PLACEHOLDER)].map((match) => match[1]).sort()
}

function rendererSources(): string[] {
  return walk(RENDERER_SRC, ['.ts', '.tsx']).filter((file) => !file.endsWith('copy.ts'))
}

const COPY_SOURCE = readText(join(RENDERER_SRC, 'lib', 'copy.ts'))
const ENTRIES_BLOCK = COPY_SOURCE.slice(
  COPY_SOURCE.indexOf('const entries = {'),
  COPY_SOURCE.indexOf('} as const satisfies')
)
const DECLARED_KEYS = [...ENTRIES_BLOCK.matchAll(/^ {2}(?:'([^']+)'|([A-Za-z_]+)):/gm)].map(
  (match) => match[1] ?? match[2]
)
const LITERAL_TEMPLATE_KEYS: readonly string[] = ['claim.prompt', 'claim.voice_hint']

test('copy source declares each key exactly once', () => {
  const seen = new Set<string>()
  const duplicates = DECLARED_KEYS.filter((key) => (seen.has(key) ? true : !seen.add(key)))
  assert.deepEqual(duplicates, [])
  assert.equal(DECLARED_KEYS.length, copyKeys.length)
  assert.deepEqual([...DECLARED_KEYS].sort(), [...copyKeys].sort())
})

test('copy keys are lowercase identifiers with optional dots', () => {
  for (const key of copyKeys) assert.match(key, /^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$/, key)
})

test('every copy key has non empty tl and en', () => {
  for (const key of copyKeys) {
    const entry = t(key)
    assert.ok(entry.tl.trim().length > 0, `${key} tl`)
    assert.ok(entry.en.trim().length > 0, `${key} en`)
  }
})

test('placeholders match between tl and en', () => {
  for (const key of copyKeys) {
    if (LITERAL_TEMPLATE_KEYS.includes(key)) continue
    const entry = t(key)
    assert.deepEqual(placeholders(entry.tl), placeholders(entry.en), key)
  }
})

test('copy text has no stray brackets, double spaces or edge whitespace', () => {
  for (const key of copyKeys) {
    const entry = t(key)
    for (const text of [entry.tl, entry.en]) {
      assert.equal(text, text.trim(), `${key} edge whitespace`)
      assert.ok(!text.includes('  '), `${key} double space`)
      assert.equal(text.replace(PLACEHOLDER, '').match(/[[\]]/), null, `${key} bracket`)
    }
  }
})

test('t fills placeholders and leaves unknown ones visible', () => {
  const entry = t('unit.lost', { unit: 'Mug' })
  assert.ok(entry.tl.includes('Mug') && entry.en.includes('Mug'))
  assert.ok(t('unit.lost').tl.includes('[unit]'))
  assert.ok(t('unit.lost', { other: 'x' }).en.includes('[unit]'))
})

test('isCopyKey rejects prototype names', () => {
  assert.equal(isCopyKey('unit.lost'), true)
  assert.equal(isCopyKey('toString'), false)
  assert.equal(isCopyKey('constructor'), false)
  assert.equal(isCopyKey(''), false)
})

test('every static say, t or pick key used in the renderer exists in copy.ts', () => {
  const missing: string[] = []
  for (const file of rendererSources()) {
    const text = readText(file)
    for (const call of text.matchAll(/\b(?:say|t)\(([^()]*)\)/g)) {
      for (const literal of call[1].matchAll(/'([a-z0-9_]+(?:\.[A-Za-z0-9_]+)+)'/g)) {
        if (!isCopyKey(literal[1])) missing.push(`${file}: ${literal[1]}`)
      }
    }
  }
  assert.deepEqual(missing, [])
})

test('dynamic enemy keys exist for every enemy type and part', () => {
  for (const name of ['aswang', 'tikbalang', 'kapre', 'manananggal', 'duwende', 'upper', 'lower']) {
    assert.ok(isCopyKey(`enemy.${name}`), name)
  }
})

test('mood keys point at real copy', () => {
  for (const key of Object.values(MOOD_KEY)) assert.ok(isCopyKey(key), key)
})

type Line = { tl: string; en: string; mood: string }

const BANK = JSON.parse(readText(join(REPO_ROOT, 'assets', 'lines.json'))) as {
  version: number
  moments: Record<string, Line[]>
}

test('line bank has moments and every one has at least one line', () => {
  assert.ok(Object.keys(BANK.moments).length >= 31)
  for (const [moment, lines] of Object.entries(BANK.moments)) {
    assert.ok(Array.isArray(lines) && lines.length > 0, moment)
  }
})

test('every line bank line has tl, en and a known mood with matching placeholders', () => {
  const moods = new Set(Object.keys(MOOD_KEY))
  for (const [moment, lines] of Object.entries(BANK.moments)) {
    lines.forEach((line, index) => {
      const where = `${moment}[${index}]`
      assert.ok(line.tl.trim().length > 0, `${where} tl`)
      assert.ok(line.en.trim().length > 0, `${where} en`)
      assert.ok(moods.has(line.mood), `${where} mood ${line.mood}`)
      assert.deepEqual(placeholders(line.tl), placeholders(line.en), where)
    })
  }
})

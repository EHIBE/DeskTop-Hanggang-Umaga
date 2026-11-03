import test from 'node:test'
import assert from 'node:assert/strict'
import { prefersReducedMotion } from '../src/renderer/src/lib/motion'
import { installWindow } from './helpers'

test('prefersReducedMotion is false without matchMedia', () => {
  installWindow()
  assert.equal(prefersReducedMotion(), false)
})

test('prefersReducedMotion follows the media query', () => {
  const queries: string[] = []
  installWindow({
    matchMedia: (query: string) => {
      queries.push(query)
      return { matches: true }
    }
  })
  assert.equal(prefersReducedMotion(), true)
  assert.deepEqual(queries, ['(prefers-reduced-motion: reduce)'])
  installWindow({ matchMedia: () => ({ matches: false }) })
  assert.equal(prefersReducedMotion(), false)
})

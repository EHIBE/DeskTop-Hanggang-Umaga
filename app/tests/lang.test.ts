import test from 'node:test'
import assert from 'node:assert/strict'
import { installWindow, makeStorage } from './helpers'

test('lang starts as tl and unchosen when storage is unreachable', async () => {
  Reflect.deleteProperty(globalThis, 'window')
  const lang = await import('../src/renderer/src/lib/lang')
  assert.equal(lang.currentLang(), 'tl')
  assert.equal(lang.langChosen(), false)
})

test('setLang persists the choice and survives a throwing storage', async () => {
  const lang = await import('../src/renderer/src/lib/lang')
  const storage = installWindow()
  lang.setLang('en')
  assert.equal(lang.currentLang(), 'en')
  assert.equal(lang.langChosen(), true)
  assert.equal(storage.getItem('desktop.lang'), 'en')
  Object.defineProperty(globalThis, 'window', {
    value: { localStorage: makeStorage({ throws: true }) },
    configurable: true,
    writable: true
  })
  assert.doesNotThrow(() => lang.setLang('tl'))
  assert.equal(lang.currentLang(), 'tl')
})

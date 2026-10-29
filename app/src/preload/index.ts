import { contextBridge, ipcRenderer } from 'electron'

type DesktopConfig = Readonly<{ port: number; token: string }>
type KeyStatus = 'stored' | 'missing'

const CONFIG_CHANNEL = 'desktop:config'
const KEY_STATUS_CHANNEL = 'desktop:key-status'
const SAVE_KEY_CHANNEL = 'desktop:save-key'
const SHOW_REEL_CHANNEL = 'desktop:show-reel'
const REEL_NAME = /^reel_[A-Za-z0-9_]{1,80}\.mp4$/

function isDesktopConfig(value: unknown): value is DesktopConfig {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate['port'] === 'number' && typeof candidate['token'] === 'string'
}

function toKeyStatus(value: unknown): KeyStatus {
  if (value === 'stored' || value === 'missing') return value
  throw new Error('invalid key status')
}

async function getConfig(): Promise<DesktopConfig> {
  const value: unknown = await ipcRenderer.invoke(CONFIG_CHANNEL)
  if (value === null) throw new Error('backend not ready')
  if (!isDesktopConfig(value)) throw new Error('invalid desktop config')
  return Object.freeze({ port: value.port, token: value.token })
}

async function getKeyStatus(): Promise<KeyStatus> {
  return toKeyStatus(await ipcRenderer.invoke(KEY_STATUS_CHANNEL))
}

async function saveKey(key: string): Promise<KeyStatus> {
  if (typeof key !== 'string') throw new Error('invalid key')
  return toKeyStatus(await ipcRenderer.invoke(SAVE_KEY_CHANNEL, key))
}

async function showReel(name: string): Promise<boolean> {
  if (typeof name !== 'string' || !REEL_NAME.test(name)) return false
  return (await ipcRenderer.invoke(SHOW_REEL_CHANNEL, name)) === true
}

contextBridge.exposeInMainWorld(
  'desktop',
  Object.freeze({ getConfig, getKeyStatus, saveKey, showReel })
)

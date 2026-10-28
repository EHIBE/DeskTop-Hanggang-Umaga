import { contextBridge, ipcRenderer } from 'electron'

type DesktopConfig = Readonly<{ port: number; token: string }>

const CONFIG_CHANNEL = 'desktop:config'

function isDesktopConfig(value: unknown): value is DesktopConfig {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate['port'] === 'number' && typeof candidate['token'] === 'string'
}

async function getConfig(): Promise<DesktopConfig> {
  const value: unknown = await ipcRenderer.invoke(CONFIG_CHANNEL)
  if (!isDesktopConfig(value)) throw new Error('invalid desktop config')
  return Object.freeze({ port: value.port, token: value.token })
}

contextBridge.exposeInMainWorld('desktop', Object.freeze({ getConfig }))

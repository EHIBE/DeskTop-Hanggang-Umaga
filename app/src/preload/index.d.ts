export type DesktopConfig = Readonly<{ port: number; token: string }>

export type KeyStatus = 'stored' | 'missing'

export type DesktopBridge = Readonly<{
  getConfig: () => Promise<DesktopConfig>
  getKeyStatus: () => Promise<KeyStatus>
  saveKey: (key: string) => Promise<KeyStatus>
}>

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

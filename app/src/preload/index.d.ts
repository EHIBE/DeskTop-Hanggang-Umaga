export type DesktopConfig = Readonly<{ port: number; token: string }>

export type DesktopBridge = Readonly<{ getConfig: () => Promise<DesktopConfig> }>

declare global {
  interface Window {
    desktop: DesktopBridge
  }
}

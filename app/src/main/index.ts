import { app, shell, session, BrowserWindow, ipcMain, IpcMainInvokeEvent } from 'electron'
import { join } from 'path'
import { pathToFileURL } from 'url'
import { randomBytes } from 'crypto'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'

const APP_USER_MODEL_ID = 'com.ehibe.desktop'
const BACKEND_PORT = 8765
const TOKEN_BYTES = 32
const CONFIG_CHANNEL = 'desktop:config'
const EXTERNAL_URL_ALLOWLIST: readonly Readonly<{ origin: string; path: string }>[] = [
  { origin: 'https://github.com', path: '/EHIBE/DeskTop-Hanggang-Umaga' },
  { origin: 'https://dev.meta.ai', path: '/docs' }
]

type DesktopConfig = Readonly<{ port: number; token: string }>

const desktopConfig: DesktopConfig = Object.freeze({
  port: BACKEND_PORT,
  token: randomBytes(TOKEN_BYTES).toString('hex')
})

const RENDERER_FILE_URL = pathToFileURL(join(__dirname, '../renderer/index.html')).href

function rendererUrl(): string | undefined {
  if (!is.dev) return undefined
  return process.env['ELECTRON_RENDERER_URL']
}

function isAllowedExternalUrl(rawUrl: string): boolean {
  if (!URL.canParse(rawUrl)) return false
  const url = new URL(rawUrl)
  if (url.protocol !== 'https:') return false
  return EXTERNAL_URL_ALLOWLIST.some(
    (allowed) =>
      url.origin === allowed.origin &&
      (url.pathname === allowed.path || url.pathname.startsWith(`${allowed.path}/`))
  )
}

function isAppUrl(rawUrl: string): boolean {
  if (!URL.canParse(rawUrl)) return false
  const url = new URL(rawUrl)
  const devUrl = rendererUrl()
  if (devUrl !== undefined) return url.origin === new URL(devUrl).origin
  return url.protocol === 'file:' && `file://${url.pathname}` === RENDERER_FILE_URL
}

function isTrustedSender(event: IpcMainInvokeEvent): boolean {
  const frame = event.senderFrame
  if (frame === null || frame !== event.sender.mainFrame) return false
  return isAppUrl(frame.url)
}

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    show: false,
    title: 'DeskTop',
    backgroundColor: '#0B0E1A',
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    if (isAllowedExternalUrl(details.url)) void shell.openExternal(details.url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
  })

  mainWindow.webContents.on('will-redirect', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
  })

  mainWindow.webContents.on('will-attach-webview', (event) => {
    event.preventDefault()
  })

  const devUrl = rendererUrl()
  if (devUrl !== undefined) {
    void mainWindow.loadURL(devUrl)
    return
  }
  void mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
}

function denyAllPermissions(): void {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false)
  })
  session.defaultSession.setPermissionCheckHandler(() => false)
}

function handleConfigRequest(event: IpcMainInvokeEvent): DesktopConfig {
  if (!isTrustedSender(event)) throw new Error('untrusted sender')
  return desktopConfig
}

void app.whenReady().then(() => {
  electronApp.setAppUserModelId(APP_USER_MODEL_ID)
  denyAllPermissions()

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  ipcMain.handle(CONFIG_CHANNEL, handleConfigRequest)

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

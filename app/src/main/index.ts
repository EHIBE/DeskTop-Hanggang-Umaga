import { app, shell, session, BrowserWindow, ipcMain, IpcMainInvokeEvent } from 'electron'
import { join } from 'path'
import { pathToFileURL } from 'url'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { BackendProcess } from './backend'
import { Keystore, KeystoreError } from './keystore'

const APP_USER_MODEL_ID = 'com.ehibe.desktop'
const CONFIG_CHANNEL = 'desktop:config'
const KEY_STATUS_CHANNEL = 'desktop:key-status'
const SAVE_KEY_CHANNEL = 'desktop:save-key'
const MAX_KEY_INPUT = 1024
const FILE_ORIGINS: readonly string[] = ['file://', 'null']
const EXTERNAL_URL_ALLOWLIST: readonly Readonly<{ origin: string; path: string }>[] = [
  { origin: 'https://github.com', path: '/EHIBE/DeskTop-Hanggang-Umaga' },
  { origin: 'https://dev.meta.ai', path: '/docs' }
]

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

function backendDir(): string {
  if (is.dev) return join(app.getAppPath(), '..', 'backend')
  return join(process.resourcesPath, 'backend')
}

function allowedOrigins(): readonly string[] {
  const devUrl = rendererUrl()
  if (devUrl !== undefined) return [new URL(devUrl).origin]
  return FILE_ORIGINS
}

function requireTrusted(event: IpcMainInvokeEvent): void {
  if (!isTrustedSender(event)) throw new Error('untrusted sender')
}

function registerIpc(keystore: Keystore, backend: BackendProcess): void {
  ipcMain.handle(CONFIG_CHANNEL, (event) => {
    requireTrusted(event)
    const config = backend.config()
    if (config === undefined) throw new Error('backend not ready')
    return config
  })
  ipcMain.handle(KEY_STATUS_CHANNEL, (event) => {
    requireTrusted(event)
    return keystore.status()
  })
  ipcMain.handle(SAVE_KEY_CHANNEL, async (event, rawKey: unknown) => {
    requireTrusted(event)
    if (typeof rawKey !== 'string' || rawKey.length > MAX_KEY_INPUT) {
      throw new KeystoreError('invalid key format')
    }
    const status = keystore.save(rawKey)
    await backend.restart()
    return status
  })
}

const hasInstanceLock = app.requestSingleInstanceLock()
if (!hasInstanceLock) app.quit()

void app.whenReady().then(async () => {
  electronApp.setAppUserModelId(APP_USER_MODEL_ID)
  denyAllPermissions()
  const userDataDir = app.getPath('userData')
  const keystore = new Keystore(userDataDir)
  const dir = backendDir()
  const backend = new BackendProcess({
    pythonPath: join(dir, '.venv', 'Scripts', 'python.exe'),
    backendDir: dir,
    userDataDir,
    allowedOrigins: allowedOrigins(),
    apiKey: () => keystore.load()
  })
  registerIpc(keystore, backend)
  app.on('before-quit', () => void backend.stop())

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  createWindow()
  await backend.start().catch(() => undefined)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

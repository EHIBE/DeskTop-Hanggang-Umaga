import { ChildProcess, spawn } from 'child_process'
import { randomBytes } from 'crypto'
import { createWriteStream, mkdirSync, WriteStream } from 'fs'
import { createServer } from 'net'
import { join } from 'path'

export type BackendConfig = Readonly<{ port: number; token: string }>

export type BackendOptions = Readonly<{
  pythonPath: string
  backendDir: string
  userDataDir: string
  allowedOrigins: readonly string[]
  apiKey: () => string | undefined
}>

const HOST = '127.0.0.1'
const TOKEN_BYTES = 32
const HEALTH_TIMEOUT_MS = 20_000
const HEALTH_INTERVAL_MS = 250
const RESTART_DELAYS_MS: readonly number[] = [1_000, 2_000, 4_000, 8_000, 8_000]
const TOKEN_HEADER = 'X-Desktop-Token'
const LOG_DIR_NAME = 'logs'
const LOG_FILE_NAME = 'backend.log'
const PASSTHROUGH_ENV: readonly string[] = [
  'SYSTEMROOT',
  'WINDIR',
  'PATH',
  'PATHEXT',
  'TEMP',
  'TMP',
  'APPDATA',
  'LOCALAPPDATA',
  'USERPROFILE',
  'HOMEDRIVE',
  'HOMEPATH',
  'COMPUTERNAME'
]

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(0, HOST, () => {
      const address = server.address()
      if (address === null || typeof address === 'string') {
        server.close()
        reject(new Error('no port assigned'))
        return
      }
      server.close(() => resolve(address.port))
    })
  })
}

function childEnv(options: BackendOptions, config: BackendConfig): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {}
  for (const name of PASSTHROUGH_ENV) {
    const value = process.env[name]
    if (value !== undefined) env[name] = value
  }
  env['PYTHONUNBUFFERED'] = '1'
  env['DESKTOP_TOKEN'] = config.token
  env['DESKTOP_PORT'] = String(config.port)
  env['DESKTOP_DATA_DIR'] = options.userDataDir
  env['DESKTOP_ALLOWED_ORIGINS'] = options.allowedOrigins.join(',')
  const apiKey = options.apiKey()
  if (apiKey !== undefined) env['MODEL_API_KEY'] = apiKey
  return env
}

export class BackendProcess {
  private child: ChildProcess | undefined
  private current: BackendConfig | undefined
  private log: WriteStream | undefined
  private isStopping = false
  private restarts = 0

  constructor(private readonly options: BackendOptions) {}

  config(): BackendConfig | undefined {
    return this.current
  }

  async start(): Promise<BackendConfig> {
    this.isStopping = false
    const config: BackendConfig = Object.freeze({
      port: await findFreePort(),
      token: randomBytes(TOKEN_BYTES).toString('hex')
    })
    this.current = config
    this.child = spawn(
      this.options.pythonPath,
      [
        '-m',
        'uvicorn',
        'server:create_app_from_env',
        '--factory',
        '--host',
        HOST,
        '--port',
        String(config.port),
        '--no-access-log'
      ],
      { cwd: this.options.backendDir, env: childEnv(this.options, config), windowsHide: true }
    )
    this.pipeLogs(this.child)
    this.child.once('exit', (code) => void this.onExit(code))
    await this.waitHealthy(config)
    this.restarts = 0
    return config
  }

  async restart(): Promise<BackendConfig> {
    await this.stop()
    return this.start()
  }

  async stop(): Promise<void> {
    this.isStopping = true
    const child = this.child
    this.child = undefined
    this.current = undefined
    if (child === undefined || child.exitCode !== null) return
    await new Promise<void>((resolve) => {
      child.once('exit', () => resolve())
      child.kill()
    })
  }

  private async onExit(code: number | null): Promise<void> {
    if (this.isStopping) return
    this.current = undefined
    this.writeLog(`backend exited with code ${code ?? 'signal'}\n`)
    const wait = RESTART_DELAYS_MS[this.restarts]
    if (wait === undefined) return
    this.restarts += 1
    await delay(wait)
    if (this.isStopping) return
    await this.start().catch((error: unknown) => {
      this.writeLog(
        `backend restart failed: ${error instanceof Error ? error.message : 'unknown'}\n`
      )
    })
  }

  private async waitHealthy(config: BackendConfig): Promise<void> {
    const deadline = Date.now() + HEALTH_TIMEOUT_MS
    while (Date.now() < deadline) {
      if (this.child === undefined || this.child.exitCode !== null) {
        throw new Error('backend exited before it was healthy')
      }
      if (await this.isHealthy(config)) return
      await delay(HEALTH_INTERVAL_MS)
    }
    throw new Error('backend health check timed out')
  }

  private async isHealthy(config: BackendConfig): Promise<boolean> {
    try {
      const response = await fetch(`http://${HOST}:${config.port}/health`, {
        headers: { [TOKEN_HEADER]: config.token }
      })
      if (!response.ok) return false
      const body: unknown = await response.json()
      return (
        typeof body === 'object' &&
        body !== null &&
        (body as Record<string, unknown>)['ok'] === true
      )
    } catch {
      return false
    }
  }

  private pipeLogs(child: ChildProcess): void {
    if (this.log === undefined) {
      const dir = join(this.options.userDataDir, LOG_DIR_NAME)
      mkdirSync(dir, { recursive: true })
      this.log = createWriteStream(join(dir, LOG_FILE_NAME), { flags: 'a' })
    }
    child.stdout?.on('data', (chunk: Buffer) => this.writeLog(chunk.toString('utf8')))
    child.stderr?.on('data', (chunk: Buffer) => this.writeLog(chunk.toString('utf8')))
  }

  private writeLog(text: string): void {
    const token = this.current?.token
    const safe = token === undefined ? text : text.split(token).join('[redacted]')
    this.log?.write(safe)
  }
}

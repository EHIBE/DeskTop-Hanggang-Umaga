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
  isDev: boolean
  isPackaged: boolean
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
const WS_MAX_SIZE_BYTES = 16_384
const REDACTED = '[redacted]'
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
  'COMPUTERNAME',
  'DESKTOP_FFMPEG'
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

export class BackendProcess {
  private child: ChildProcess | undefined
  private current: BackendConfig | undefined
  private log: WriteStream | undefined
  private readonly secrets = new Set<string>()
  private generation = 0
  private restarts = 0
  private isStopping = false
  private queue: Promise<unknown> = Promise.resolve()

  constructor(private readonly options: BackendOptions) {}

  config(): BackendConfig | undefined {
    return this.current
  }

  start(): Promise<BackendConfig> {
    return this.enqueue(() => this.launch())
  }

  restart(): Promise<BackendConfig> {
    return this.enqueue(async () => {
      await this.terminate()
      return this.launch()
    })
  }

  stop(): Promise<void> {
    this.isStopping = true
    return this.enqueue(() => this.terminate())
  }

  recordFailure(error: unknown): void {
    this.writeLog(`backend start failed: ${error instanceof Error ? error.message : 'unknown'}\n`)
  }

  private enqueue<T>(task: () => Promise<T>): Promise<T> {
    const next = this.queue.then(task, task)
    this.queue = next.catch(() => undefined)
    return next
  }

  private childEnv(config: BackendConfig): NodeJS.ProcessEnv {
    const env: NodeJS.ProcessEnv = {}
    for (const name of PASSTHROUGH_ENV) {
      const value = process.env[name]
      if (value !== undefined) env[name] = value
    }
    env['PYTHONUNBUFFERED'] = '1'
    env['DESKTOP_TOKEN'] = config.token
    env['DESKTOP_PORT'] = String(config.port)
    env['DESKTOP_DATA_DIR'] = this.options.userDataDir
    env['DESKTOP_ALLOWED_ORIGINS'] = this.options.allowedOrigins.join(',')
    env['DESKTOP_PARENT_WATCH'] = '1'
    if (this.options.isDev) env['DESKTOP_DEV'] = '1'
    if (this.options.isPackaged) env['DESKTOP_PACKAGED'] = '1'
    const apiKey = this.options.apiKey()
    if (apiKey !== undefined) {
      this.secrets.add(apiKey)
      env['MODEL_API_KEY'] = apiKey
    }
    return env
  }

  private async launch(): Promise<BackendConfig> {
    this.isStopping = false
    this.generation += 1
    const generation = this.generation
    const config: BackendConfig = Object.freeze({
      port: await findFreePort(),
      token: randomBytes(TOKEN_BYTES).toString('hex')
    })
    this.secrets.add(config.token)
    const child = spawn(
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
        '--no-access-log',
        '--ws-max-size',
        String(WS_MAX_SIZE_BYTES)
      ],
      {
        cwd: this.options.backendDir,
        env: this.childEnv(config),
        windowsHide: true,
        stdio: ['pipe', 'pipe', 'pipe']
      }
    )
    this.child = child
    this.pipeLogs(child)
    child.once('exit', (code) => void this.onExit(generation, code))
    try {
      await this.waitHealthy(child, config)
    } catch (error) {
      child.kill()
      throw error
    }
    this.current = config
    this.restarts = 0
    return config
  }

  private async terminate(): Promise<void> {
    this.generation += 1
    const child = this.child
    this.child = undefined
    this.current = undefined
    if (child === undefined || child.exitCode !== null) return
    await new Promise<void>((resolve) => {
      child.once('exit', () => resolve())
      child.kill()
    })
  }

  private async onExit(generation: number, code: number | null): Promise<void> {
    if (this.isStopping || generation !== this.generation) return
    this.current = undefined
    this.writeLog(`backend exited with code ${code ?? 'signal'}\n`)
    const wait = RESTART_DELAYS_MS[this.restarts]
    if (wait === undefined) return
    this.restarts += 1
    await delay(wait)
    if (this.isStopping || generation !== this.generation) return
    await this.start().catch((error: unknown) => this.recordFailure(error))
  }

  private async waitHealthy(child: ChildProcess, config: BackendConfig): Promise<void> {
    const deadline = Date.now() + HEALTH_TIMEOUT_MS
    while (Date.now() < deadline) {
      if (child.exitCode !== null) throw new Error('backend exited before it was healthy')
      if (await this.isHealthy(config)) return
      await delay(HEALTH_INTERVAL_MS)
    }
    throw new Error('backend health check timed out')
  }

  private async isHealthy(config: BackendConfig): Promise<boolean> {
    const response = await fetch(`http://${HOST}:${config.port}/health`, {
      headers: { [TOKEN_HEADER]: config.token }
    }).catch(() => undefined)
    if (response === undefined || !response.ok) return false
    const body: unknown = await response.json().catch(() => undefined)
    return (
      typeof body === 'object' && body !== null && (body as Record<string, unknown>)['ok'] === true
    )
  }

  private pipeLogs(child: ChildProcess): void {
    if (this.log === undefined) {
      const dir = join(this.options.userDataDir, LOG_DIR_NAME)
      mkdirSync(dir, { recursive: true })
      this.log = createWriteStream(join(dir, LOG_FILE_NAME), { flags: 'w' })
    }
    this.lineWriter(child.stdout)
    this.lineWriter(child.stderr)
  }

  private lineWriter(stream: NodeJS.ReadableStream | null): void {
    if (stream === null) return
    let pending = ''
    stream.on('data', (chunk: Buffer) => {
      const lines = (pending + chunk.toString('utf8')).split('\n')
      pending = lines.pop() ?? ''
      for (const line of lines) this.writeLog(`${line}\n`)
    })
    stream.on('end', () => {
      if (pending !== '') this.writeLog(`${pending}\n`)
      pending = ''
    })
  }

  private writeLog(text: string): void {
    let safe = text
    for (const secret of this.secrets) safe = safe.split(secret).join(REDACTED)
    this.log?.write(safe)
  }
}

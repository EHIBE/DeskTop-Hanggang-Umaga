import { safeStorage } from 'electron'
import { existsSync, readFileSync, renameSync, writeFileSync } from 'fs'
import { join } from 'path'

export type KeyStatus = 'stored' | 'missing'

const KEY_FILE_NAME = 'model-key.bin'
const MIN_KEY_LENGTH = 20
const MAX_KEY_LENGTH = 512
const KEY_PATTERN = /^[\x21-\x7e]+$/

export class KeystoreError extends Error {}

export class Keystore {
  private readonly keyPath: string

  constructor(userDataDir: string) {
    this.keyPath = join(userDataDir, KEY_FILE_NAME)
  }

  status(): KeyStatus {
    return this.load() === undefined ? 'missing' : 'stored'
  }

  load(): string | undefined {
    if (!existsSync(this.keyPath)) return undefined
    if (!safeStorage.isEncryptionAvailable()) return undefined
    const key = this.decrypt()
    return key !== undefined && isValidKey(key) ? key : undefined
  }

  private decrypt(): string | undefined {
    try {
      return safeStorage.decryptString(readFileSync(this.keyPath))
    } catch {
      return undefined
    }
  }

  save(rawKey: string): KeyStatus {
    const key = rawKey.trim()
    if (!isValidKey(key)) throw new KeystoreError('invalid key format')
    if (!safeStorage.isEncryptionAvailable()) throw new KeystoreError('encryption unavailable')
    const temporary = `${this.keyPath}.tmp`
    writeFileSync(temporary, safeStorage.encryptString(key), { mode: 0o600 })
    renameSync(temporary, this.keyPath)
    return 'stored'
  }
}

export function isValidKey(key: string): boolean {
  if (key.length < MIN_KEY_LENGTH || key.length > MAX_KEY_LENGTH) return false
  return KEY_PATTERN.test(key)
}

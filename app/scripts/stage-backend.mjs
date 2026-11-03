import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoDir = resolve(appDir, '..')
const backendSrc = join(repoDir, 'backend')
const venvPython = join(backendSrc, '.venv', 'Scripts', 'python.exe')
const stagingDir = join(appDir, 'staging')
const backendOut = join(stagingDir, 'backend')
const pythonOut = join(backendOut, 'python')

const SKIP_LIB = new Set([
  'site-packages',
  'test',
  'tests',
  'idlelib',
  'tkinter',
  'ensurepip',
  'turtledemo',
  '__pycache__'
])
const SKIP_DLL = /^(_tkinter|tcl.*|tk.*)\.(pyd|dll)$/i
const PACKAGES = ['capture', 'db', 'game', 'gm', 'replay', 'rules', 'vision', 'voice']
const SKIP_SOURCE =
  /(^|[\\/])(__pycache__|\.env|\.env\..*)$|\.(sqlite|sqlite-wal|sqlite-shm|log|mp4|pyc)$/i
const SKIP_SITE = /(^|[\\/])(__pycache__|tests?)$|\.pyc$/i
const DEV_PREFIXES = [
  'mypy',
  '_pytest',
  'pytest',
  'coverage',
  '.coverage',
  'a1_coverage',
  'ruff',
  'pygments',
  'librt',
  'ast_serialize',
  'pathspec',
  'pluggy',
  'iniconfig',
  'pip',
  'py.py',
  '6ec57f84c680d3a3778b__mypyc'
]

function basePrefix() {
  return execFileSync(venvPython, ['-c', 'import sys; print(sys.base_prefix)'], {
    encoding: 'utf8'
  }).trim()
}

function copyFiltered(from, to, reject) {
  cpSync(from, to, { recursive: true, filter: (src) => !reject(src) })
}

function stagePython(base) {
  mkdirSync(pythonOut, { recursive: true })
  for (const name of readdirSync(base)) {
    const path = join(base, name)
    if (!statSync(path).isFile()) continue
    if (/^(python.*|vcruntime.*)\.(exe|dll)$/i.test(name)) cpSync(path, join(pythonOut, name))
  }
  copyFiltered(join(base, 'DLLs'), join(pythonOut, 'DLLs'), (src) =>
    SKIP_DLL.test(src.split(sep).pop() ?? '')
  )
  copyFiltered(join(base, 'Lib'), join(pythonOut, 'Lib'), (src) => {
    const parts = src.slice(join(base, 'Lib').length).split(sep).filter(Boolean)
    return parts.some((part) => SKIP_LIB.has(part))
  })
  copyFiltered(
    join(backendSrc, '.venv', 'Lib', 'site-packages'),
    join(pythonOut, 'Lib', 'site-packages'),
    (src) => {
      const site = join(backendSrc, '.venv', 'Lib', 'site-packages')
      const top = src.slice(site.length).split(sep).filter(Boolean)[0] ?? ''
      return SKIP_SITE.test(src) || DEV_PREFIXES.some((prefix) => top.startsWith(prefix))
    }
  )
}

function stageSource() {
  for (const name of readdirSync(backendSrc)) {
    if (name.endsWith('.py') && statSync(join(backendSrc, name)).isFile()) {
      cpSync(join(backendSrc, name), join(backendOut, name))
    }
  }
  for (const pkg of PACKAGES) {
    copyFiltered(join(backendSrc, pkg), join(backendOut, pkg), (src) => SKIP_SOURCE.test(src))
  }
}

function verify() {
  const env = {
    SYSTEMROOT: process.env.SYSTEMROOT ?? String.raw`C:\Windows`,
    PATH: String.raw`C:\Windows\System32`
  }
  const python = join(pythonOut, 'python.exe')
  const code =
    'import cv2, numpy, fastapi, uvicorn, openai, sys; sys.path.insert(0, r"' +
    backendOut +
    '"); import server; print(sys.prefix)'
  const out = execFileSync(python, ['-c', code], { env, cwd: backendOut, encoding: 'utf8' })
  process.stdout.write(`staged python ok: ${out.trim()}\n`)
}

if (!existsSync(venvPython)) throw new Error('backend venv is missing')
rmSync(stagingDir, { recursive: true, force: true })
mkdirSync(backendOut, { recursive: true })
stagePython(basePrefix())
stageSource()
cpSync(join(repoDir, 'assets'), join(stagingDir, 'assets'), { recursive: true })
verify()

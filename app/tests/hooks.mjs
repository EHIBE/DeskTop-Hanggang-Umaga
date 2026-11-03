import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const EXTENSIONS = ['.ts', '/index.ts']

export async function resolve(specifier, context, next) {
  const relative = specifier.startsWith('./') || specifier.startsWith('../')
  if (relative && context.parentURL && !/\.[a-z]+$/.test(specifier)) {
    for (const extension of EXTENSIONS) {
      const candidate = new URL(specifier + extension, context.parentURL)
      if (existsSync(fileURLToPath(candidate))) return next(candidate.href, context)
    }
  }
  return next(specifier, context)
}

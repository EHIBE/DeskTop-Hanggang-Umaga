import { useEffect, useState } from 'react'
import { palette } from '../lib/palette'
import type { EnemySummary } from '../lib/types'
import { FONT, drawBadge } from './draw'

const enemyUrls = import.meta.glob('@assets/sprites/enemies/*.png', {
  eager: true,
  query: '?url',
  import: 'default'
}) as Record<string, string>

const frameCache = new Map<string, Promise<ImageBitmap | null>>()

export const ENEMY_RADIUS_CM = 2
export const ENEMY_SCALE = 2
export const BOB_MS = 500

export function enemyArtKey(enemy: EnemySummary): string {
  return enemy.part === null ? enemy.type : `${enemy.type}_${enemy.part}`
}

function urlFor(name: string): string | null {
  const suffix = `/${name}.png`
  const match = Object.keys(enemyUrls).find((path) => path.endsWith(suffix))
  return match === undefined ? null : enemyUrls[match]
}

function loadFrame(name: string): Promise<ImageBitmap | null> {
  let entry = frameCache.get(name)
  if (!entry) {
    const url = urlFor(name)
    entry =
      url === null
        ? Promise.resolve(null)
        : fetch(url)
            .then((response) => response.blob())
            .then((blob) => createImageBitmap(blob))
            .catch(() => null)
    frameCache.set(name, entry)
  }
  return entry
}

async function loadPair(key: string, fallbackKey: string): Promise<readonly ImageBitmap[]> {
  for (const base of [key, fallbackKey]) {
    const [a, b] = await Promise.all([loadFrame(`${base}_0`), loadFrame(`${base}_1`)])
    if (a && b) return [a, b]
    if (a) return [a]
  }
  return []
}

export function useEnemyFrames(
  enemies: readonly EnemySummary[]
): ReadonlyMap<string, readonly ImageBitmap[]> {
  const [frames, setFrames] = useState<ReadonlyMap<string, readonly ImageBitmap[]>>(new Map())
  const signature = Array.from(new Set(enemies.map(enemyArtKey)))
    .sort()
    .join('|')

  useEffect(() => {
    let active = true
    const keys = signature === '' ? [] : signature.split('|')
    void Promise.all(
      keys.map((key) => {
        const type = key.split('_')[0]
        return loadPair(key, type).then((pair) => [key, pair] as const)
      })
    ).then((pairs) => {
      if (active) setFrames(new Map(pairs))
    })
    return () => {
      active = false
    }
  }, [signature])

  return frames
}

export function drawEnemy(
  ctx: CanvasRenderingContext2D,
  enemy: EnemySummary,
  frames: readonly ImageBitmap[],
  x: number,
  y: number,
  pxPerCm: number,
  now: number
): void {
  const phase = Math.floor(now / BOB_MS) % 2
  if (frames.length > 0) {
    const image = frames[phase % frames.length]
    const width = image.width * ENEMY_SCALE
    const height = image.height * ENEMY_SCALE
    const bob = frames.length === 1 && phase === 1 ? 4 : 0
    const left = Math.round(x - width / 2)
    const top = Math.round(y - height / 2) - bob
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(image, left, top, width, height)
    if (enemy.stunned) drawBadge(ctx, left + width, top, palette.lantern, 'zz')
    return
  }
  const radius = Math.max(16, Math.round(ENEMY_RADIUS_CM * pxPerCm))
  const cy = y - (phase === 1 ? 4 : 0)
  ctx.fillStyle = palette.sindak
  ctx.strokeStyle = palette.ink
  ctx.lineWidth = 4
  ctx.setLineDash([])
  ctx.beginPath()
  if (enemy.part === 'lower') {
    ctx.moveTo(x, cy - radius)
    ctx.lineTo(x + radius, cy)
    ctx.lineTo(x, cy + radius)
    ctx.lineTo(x - radius, cy)
    ctx.closePath()
  } else {
    ctx.arc(x, cy, radius, 0, Math.PI * 2)
  }
  ctx.fill()
  ctx.stroke()
  const suffix = enemy.part === 'upper' ? 'U' : enemy.part === 'lower' ? 'L' : ''
  ctx.fillStyle = palette.moon
  ctx.font = FONT
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(`${enemy.type.charAt(0).toUpperCase()}${suffix}`, Math.round(x), Math.round(cy) + 1)
  if (enemy.stunned) drawBadge(ctx, x + radius, cy - radius, palette.lantern, 'zz')
}

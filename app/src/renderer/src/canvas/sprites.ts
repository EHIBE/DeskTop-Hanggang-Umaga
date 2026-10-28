import { useEffect, useState } from 'react'
import type { UnitClass, UnitSummary } from '../lib/types'

export const SPRITE_SIZE = 48
export const MIN_SCALE = 2

const placeholderUrls = import.meta.glob('@assets/sprites/placeholders/*.png', {
  eager: true,
  query: '?url',
  import: 'default'
}) as Record<string, string>

const bitmapCache = new Map<string, Promise<ImageBitmap | null>>()
const keyByUnit = new Map<string, string>()

function hashOf(data: string): string {
  let h = 2166136261
  for (let i = 0; i < data.length; i += 1) {
    h = Math.imul(h ^ data.charCodeAt(i), 16777619)
  }
  return `${data.length}-${(h >>> 0).toString(16)}`
}

function decode(data: string): Promise<ImageBitmap | null> {
  try {
    const binary = atob(data)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
    return createImageBitmap(new Blob([bytes], { type: 'image/png' })).catch(() => null)
  } catch {
    return Promise.resolve(null)
  }
}

export function loadSprite(unitId: string, data: string): Promise<ImageBitmap | null> {
  const key = `${unitId}:${hashOf(data)}`
  const previous = keyByUnit.get(unitId)
  if (previous !== undefined && previous !== key) bitmapCache.delete(previous)
  keyByUnit.set(unitId, key)
  let entry = bitmapCache.get(key)
  if (!entry) {
    entry = decode(data)
    bitmapCache.set(key, entry)
  }
  return entry
}

export function placeholderUrl(unitClass: UnitClass): string | null {
  const suffix = `/${unitClass}.png`
  const match = Object.keys(placeholderUrls).find((path) => path.endsWith(suffix))
  return match === undefined ? null : placeholderUrls[match]
}

function loadPlaceholder(unitClass: UnitClass): Promise<ImageBitmap | null> {
  const url = placeholderUrl(unitClass)
  if (url === null) return Promise.resolve(null)
  const key = `placeholder:${unitClass}`
  let entry = bitmapCache.get(key)
  if (!entry) {
    entry = fetch(url)
      .then((response) => response.blob())
      .then((blob) => createImageBitmap(blob))
      .catch(() => null)
    bitmapCache.set(key, entry)
  }
  return entry
}

export function loadUnitImage(unit: UnitSummary): Promise<ImageBitmap | null> {
  if (unit.sprite_png !== null && unit.sprite_png !== '') {
    return loadSprite(unit.unit_id, unit.sprite_png).then(
      (bitmap) => bitmap ?? loadPlaceholder(unit.class)
    )
  }
  return loadPlaceholder(unit.class)
}

export function drawSprite(
  ctx: CanvasRenderingContext2D,
  image: ImageBitmap,
  centerX: number,
  centerY: number,
  scale: number = MIN_SCALE
): Readonly<{ left: number; top: number; width: number; height: number }> {
  const factor = Math.max(MIN_SCALE, Math.round(scale))
  const width = image.width * factor
  const height = image.height * factor
  const left = Math.round(centerX - width / 2)
  const top = Math.round(centerY - height / 2)
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(image, left, top, width, height)
  return { left, top, width, height }
}

export function useUnitImages(units: readonly UnitSummary[]): ReadonlyMap<string, ImageBitmap> {
  const [images, setImages] = useState<ReadonlyMap<string, ImageBitmap>>(new Map())

  useEffect(() => {
    let active = true
    void Promise.all(
      units.map((unit) => loadUnitImage(unit).then((bitmap) => [unit, bitmap] as const))
    ).then((pairs) => {
      if (!active) return
      const next = new Map<string, ImageBitmap>()
      pairs.forEach(([unit, bitmap]) => {
        if (bitmap) next.set(unit.unit_id, bitmap)
      })
      setImages(next)
    })
    return () => {
      active = false
    }
  }, [units])

  return images
}

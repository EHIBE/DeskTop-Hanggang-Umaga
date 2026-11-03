import { palette } from '../lib/palette'
import type { Point, SmokeCloud } from '../lib/types'
import { drawTag } from './draw'

const CELL = 12
const STEP_MS = 600
const DENSE_SHARE = 0.6
const EDGE_JITTER = 0.18
const DENSE_ALPHA = 0.62
const THIN_ALPHA = 0.4
const LABEL_GAP = 36

function noise(x: number, y: number, step: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(step, 1274126177)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295
}

export function drawSmoke(
  ctx: CanvasRenderingContext2D,
  clouds: readonly SmokeCloud[],
  toCanvas: (xCm: number, yCm: number) => Point,
  pxPerCm: number,
  now: number,
  reduced: boolean,
  label: string
): void {
  const step = reduced ? 0 : Math.floor(now / STEP_MS)
  clouds.forEach((cloud) => {
    const [cx, cy] = toCanvas(cloud.x_cm, cloud.y_cm)
    const radius = cloud.radius_cm * pxPerCm
    const span = Math.ceil(radius / CELL) + 1
    ctx.save()
    for (let gy = -span; gy <= span; gy += 1) {
      for (let gx = -span; gx <= span; gx += 1) {
        const distance = Math.hypot(gx * CELL, gy * CELL)
        const edge = radius * (1 - EDGE_JITTER + EDGE_JITTER * noise(gx, gy, step))
        if (distance > edge) continue
        ctx.globalAlpha = distance < radius * DENSE_SHARE ? DENSE_ALPHA : THIN_ALPHA
        ctx.fillStyle = noise(gx + 11, gy + 5, step) > 0.5 ? palette.mist : palette.slate
        ctx.fillRect(
          Math.round(cx + gx * CELL - CELL / 2),
          Math.round(cy + gy * CELL - CELL / 2),
          CELL,
          CELL
        )
      }
    }
    ctx.globalAlpha = 1
    ctx.strokeStyle = palette.mist
    ctx.lineWidth = 2
    ctx.setLineDash([8, 8])
    ctx.beginPath()
    ctx.arc(Math.round(cx), Math.round(cy), radius, 0, Math.PI * 2)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.restore()
    drawTag(ctx, label, cx, cy - radius - LABEL_GAP, palette.mist)
  })
}

import { palette } from '../lib/palette'
import { drawBadge } from './draw'

export type RingSpec = Readonly<{
  centerX: number
  centerY: number
  radiusPx: number
  unitX: number
  unitY: number
  legal: boolean
  down: boolean
}>

export function drawMoveRing(ctx: CanvasRenderingContext2D, ring: RingSpec): void {
  if (ring.radiusPx <= 0) return
  ctx.lineCap = 'butt'
  if (ring.down) {
    ctx.strokeStyle = palette.slate
    ctx.lineWidth = 2
    ctx.setLineDash([2, 8])
    ctx.beginPath()
    ctx.arc(ring.centerX, ring.centerY, ring.radiusPx, 0, Math.PI * 2)
    ctx.stroke()
    ctx.setLineDash([])
    return
  }
  const color = ring.legal ? palette.kawayan : palette.sindak
  ctx.strokeStyle = color
  ctx.lineWidth = 4
  ctx.setLineDash(ring.legal ? [] : [16, 10])
  ctx.beginPath()
  ctx.arc(ring.centerX, ring.centerY, ring.radiusPx, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])
  const badgeColor = ring.legal ? palette.dahon : palette.sindak
  drawBadge(ctx, ring.unitX + 56, ring.unitY - 56, badgeColor, ring.legal ? 'check' : 'cross')
}

export function drawStartGhost(
  ctx: CanvasRenderingContext2D,
  image: ImageBitmap | null,
  x: number,
  y: number,
  scale: number
): void {
  const size = (image ? image.width * scale : 64) + 8
  const left = Math.round(x - size / 2)
  const top = Math.round(y - size / 2)
  if (image) {
    ctx.save()
    ctx.globalAlpha = 0.4
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(image, left + 4, top + 4, image.width * scale, image.height * scale)
    ctx.restore()
  }
  ctx.strokeStyle = palette.moon
  ctx.lineWidth = 2
  ctx.setLineDash([8, 8])
  ctx.strokeRect(left, top, size, size)
  ctx.setLineDash([])
}

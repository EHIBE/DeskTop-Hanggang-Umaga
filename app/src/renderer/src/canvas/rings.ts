import { palette } from '../lib/palette'
import { drawBadge, drawTag } from './draw'

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

function drawDashedBox(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  color: string
): void {
  ctx.strokeStyle = color
  ctx.lineWidth = 4
  ctx.setLineDash([12, 8])
  ctx.strokeRect(Math.round(x - size / 2), Math.round(y - size / 2), size, size)
  ctx.setLineDash([])
}

function drawFaintSprite(
  ctx: CanvasRenderingContext2D,
  image: ImageBitmap | null,
  x: number,
  y: number,
  scale: number
): void {
  if (!image) return
  ctx.save()
  ctx.globalAlpha = 0.5
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(
    image,
    Math.round(x - (image.width * scale) / 2),
    Math.round(y - (image.height * scale) / 2),
    image.width * scale,
    image.height * scale
  )
  ctx.restore()
}

export function drawPushGhost(
  ctx: CanvasRenderingContext2D,
  image: ImageBitmap | null,
  x: number,
  y: number,
  scale: number,
  label: string
): void {
  const size = (image ? image.width * scale : 48) + 16
  drawFaintSprite(ctx, image, x, y, scale)
  drawDashedBox(ctx, x, y, size, palette.lantern)
  drawBadge(ctx, x + size / 2, y - size / 2, palette.lantern, 'question')
  drawTag(ctx, label, x, y + size / 2 + 4, palette.lantern)
}

export function drawRemoveMark(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  label: string
): void {
  const radius = 60
  ctx.strokeStyle = palette.sindak
  ctx.lineWidth = 6
  ctx.lineCap = 'butt'
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.stroke()
  const arm = radius * 0.6
  ctx.beginPath()
  ctx.moveTo(x - arm, y - arm)
  ctx.lineTo(x + arm, y + arm)
  ctx.moveTo(x + arm, y - arm)
  ctx.lineTo(x - arm, y + arm)
  ctx.stroke()
  drawTag(ctx, label, x, y - radius - 32, palette.sindak)
}

export function drawReturnMark(
  ctx: CanvasRenderingContext2D,
  image: ImageBitmap | null,
  x: number,
  y: number,
  scale: number,
  label: string
): void {
  const size = (image ? image.width * scale : 48) + 16
  drawFaintSprite(ctx, image, x, y, scale)
  drawDashedBox(ctx, x, y, size, palette.dahon)
  ctx.fillStyle = palette.dahon
  ctx.beginPath()
  ctx.moveTo(x, y + 14)
  ctx.lineTo(x - 16, y - 6)
  ctx.lineTo(x + 16, y - 6)
  ctx.closePath()
  ctx.fill()
  drawTag(ctx, label, x, y + size / 2 + 4, palette.dahon)
}

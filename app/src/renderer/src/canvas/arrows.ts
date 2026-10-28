import { palette } from '../lib/palette'
import { BADGE, FONT, drawBadge } from './draw'

const HEAD = 20
const STOP_SHORT = 52

export function drawIntentArrow(
  ctx: CanvasRenderingContext2D,
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  dmg: number
): void {
  const dx = toX - fromX
  const dy = toY - fromY
  const length = Math.hypot(dx, dy)
  if (length < STOP_SHORT + HEAD) return
  const ux = dx / length
  const uy = dy / length
  const tipX = toX - ux * STOP_SHORT
  const tipY = toY - uy * STOP_SHORT
  const baseX = tipX - ux * HEAD
  const baseY = tipY - uy * HEAD
  const startX = fromX + ux * 40
  const startY = fromY + uy * 40
  ctx.strokeStyle = palette.sindak
  ctx.fillStyle = palette.sindak
  ctx.lineWidth = 6
  ctx.lineCap = 'butt'
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(startX, startY)
  ctx.lineTo(baseX, baseY)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(tipX, tipY)
  ctx.lineTo(baseX - uy * HEAD * 0.7, baseY + ux * HEAD * 0.7)
  ctx.lineTo(baseX + uy * HEAD * 0.7, baseY - ux * HEAD * 0.7)
  ctx.closePath()
  ctx.fill()
  const midX = (startX + baseX) / 2
  const midY = (startY + baseY) / 2
  drawBadge(ctx, baseX - ux * 4, baseY - uy * 4 - BADGE, palette.sindak, 'bang')
  ctx.font = FONT
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const label = String(dmg)
  const width = Math.ceil(ctx.measureText(label).width) + 16
  ctx.fillStyle = palette.ink
  ctx.fillRect(Math.round(midX - width / 2), Math.round(midY - 14), width, 28)
  ctx.strokeStyle = palette.sindak
  ctx.lineWidth = 2
  ctx.strokeRect(Math.round(midX - width / 2) + 1, Math.round(midY - 14) + 1, width - 2, 26)
  ctx.fillStyle = palette.moon
  ctx.fillText(label, Math.round(midX), Math.round(midY) + 1)
}

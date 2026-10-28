import { palette } from '../lib/palette'

export const FONT = '16px "Press Start 2P"'
export const BADGE = 32

export function drawTag(
  ctx: CanvasRenderingContext2D,
  text: string,
  centerX: number,
  top: number,
  color: string = palette.moon
): void {
  ctx.font = FONT
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const width = Math.ceil(ctx.measureText(text).width) + 16
  const left = Math.round(centerX - width / 2)
  ctx.fillStyle = palette.ink
  ctx.fillRect(left, Math.round(top), width, 28)
  ctx.fillStyle = color
  ctx.fillText(text, Math.round(centerX), Math.round(top) + 15)
}

export function drawBadge(
  ctx: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  border: string,
  glyph: 'check' | 'cross' | 'bang' | 'zz' | 'question'
): void {
  const left = Math.round(centerX - BADGE / 2)
  const top = Math.round(centerY - BADGE / 2)
  ctx.fillStyle = palette.ink
  ctx.fillRect(left, top, BADGE, BADGE)
  ctx.strokeStyle = border
  ctx.lineWidth = 2
  ctx.setLineDash([])
  ctx.strokeRect(left + 1, top + 1, BADGE - 2, BADGE - 2)
  ctx.strokeStyle = border
  ctx.fillStyle = border
  ctx.lineWidth = 4
  ctx.lineCap = 'butt'
  if (glyph === 'check') {
    ctx.beginPath()
    ctx.moveTo(left + 7, top + 17)
    ctx.lineTo(left + 14, top + 24)
    ctx.lineTo(left + 26, top + 9)
    ctx.stroke()
  } else if (glyph === 'cross') {
    ctx.beginPath()
    ctx.moveTo(left + 8, top + 8)
    ctx.lineTo(left + 24, top + 24)
    ctx.moveTo(left + 24, top + 8)
    ctx.lineTo(left + 8, top + 24)
    ctx.stroke()
  } else {
    const label = glyph === 'bang' ? '!' : glyph === 'zz' ? 'zz' : '?'
    ctx.font = FONT
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, Math.round(centerX), Math.round(centerY) + 1)
  }
}

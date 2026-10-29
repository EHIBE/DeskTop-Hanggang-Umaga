import { palette } from '../lib/palette'
import { t } from '../lib/copy'
import type { SummonResultMessage } from '../lib/types'
import type { BoardMapping } from './Board'

const LABEL_FONT = '20px "Press Start 2P"'
const LABEL_HEIGHT = 36

function drawLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  left: number,
  top: number,
  color: string,
  minLeft: number,
  minTop: number,
  maxRight: number
): void {
  ctx.font = LABEL_FONT
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  const width = Math.ceil(ctx.measureText(text).width) + 16
  const x = Math.round(Math.max(minLeft, Math.min(left, maxRight - width)))
  const y = Math.round(Math.max(minTop, top))
  ctx.fillStyle = palette.ink
  ctx.fillRect(x, y, width, LABEL_HEIGHT)
  ctx.strokeStyle = color
  ctx.lineWidth = 2
  ctx.setLineDash([])
  ctx.strokeRect(x + 1, y + 1, width - 2, LABEL_HEIGHT - 2)
  ctx.fillStyle = color
  ctx.fillText(text, x + 8, y + LABEL_HEIGHT / 2 + 1)
}

export function drawSummonOverlay(
  ctx: CanvasRenderingContext2D,
  mapping: BoardMapping,
  made: SummonResultMessage,
  alpha: number
): void {
  if (alpha <= 0 || made.width <= 0 || made.height <= 0) return
  const sx = mapping.srcWidth / made.width
  const sy = mapping.srcHeight / made.height
  const [minLeft, minTop] = mapping.toCanvas(0, 0)
  const [maxRight] = mapping.toCanvas(mapping.srcWidth, mapping.srcHeight)
  ctx.save()
  ctx.globalAlpha = alpha

  if (made.mask_hull.length >= 3) {
    ctx.beginPath()
    made.mask_hull.forEach((point, index) => {
      const [x, y] = mapping.toCanvas(point[0] * sx, point[1] * sy)
      if (index === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.closePath()
    ctx.globalAlpha = alpha * 0.35
    ctx.fillStyle = palette.dahon
    ctx.fill()
    ctx.globalAlpha = alpha
    ctx.strokeStyle = palette.dahon
    ctx.lineWidth = 4
    ctx.setLineDash([])
    ctx.lineJoin = 'round'
    ctx.stroke()
    let bottom = -Infinity
    let left = Infinity
    made.mask_hull.forEach((point) => {
      const [x, y] = mapping.toCanvas(point[0] * sx, point[1] * sy)
      bottom = Math.max(bottom, y)
      left = Math.min(left, x)
    })
    drawLabel(ctx, t('model.sam').tl, left, bottom + 8, palette.dahon, minLeft, minTop, maxRight)
  }

  if (made.spark_box !== null) {
    const [l, tp, r, b] = made.spark_box
    const [x0, y0] = mapping.toCanvas(l * sx, tp * sy)
    const [x1, y1] = mapping.toCanvas(r * sx, b * sy)
    ctx.strokeStyle = palette.lantern
    ctx.lineWidth = 4
    ctx.setLineDash([16, 8])
    ctx.strokeRect(Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0))
    ctx.setLineDash([])
    drawLabel(
      ctx,
      t('model.spark').tl,
      x0,
      y0 - LABEL_HEIGHT - 8,
      palette.lantern,
      minLeft,
      minTop,
      maxRight
    )
  }

  ctx.restore()
}

export type Footprint = Readonly<{ left: number; top: number; width: number; height: number }>

export const FLASH_MS = 600

export function drawReanchorFlash(
  ctx: CanvasRenderingContext2D,
  mapping: BoardMapping,
  footprints: readonly Footprint[],
  elapsed: number,
  reduced: boolean
): boolean {
  if (elapsed < 0 || elapsed >= FLASH_MS || footprints.length === 0) return false
  const progress = elapsed / FLASH_MS
  const grow = reduced ? 4 : Math.round(4 + progress * 20)
  const alpha = reduced ? 1 : 1 - progress
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.strokeStyle = palette.moon
  ctx.lineWidth = 4
  ctx.setLineDash([])
  footprints.forEach((box) => {
    ctx.strokeRect(box.left - grow, box.top - grow, box.width + grow * 2, box.height + grow * 2)
  })
  ctx.globalAlpha = 1
  const [x0, y0] = mapping.toCanvas(0, 0)
  const [x1] = mapping.toCanvas(mapping.srcWidth, mapping.srcHeight)
  drawLabel(ctx, t('model.sam').tl, (x0 + x1) / 2 - 60, y0 + 12, palette.moon, x0, y0, x1)
  ctx.restore()
  return true
}

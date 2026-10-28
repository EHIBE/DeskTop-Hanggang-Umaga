import { useEffect, useRef } from 'react'
import { palette } from '../lib/palette'
import type { MessageHandler } from '../lib/socket'
import type { FrameView, Point, Pose } from '../lib/types'

export type BoardMapping = Readonly<{
  view: FrameView
  srcWidth: number
  srcHeight: number
  scale: number
  offsetX: number
  offsetY: number
  toCanvas: (x: number, y: number) => Point
  poses: readonly Pose[]
  now: number
  requestRedraw: () => void
}>

export type BoardOverlay = (ctx: CanvasRenderingContext2D, mapping: BoardMapping) => void

type BoardProps = Readonly<{
  subscribe: (handler: MessageHandler) => () => void
  onTap?: (point: Point, mapping: BoardMapping) => void
  overlay?: BoardOverlay
  label: string
}>

type LoadedFrame = {
  image: HTMLImageElement
  view: FrameView
  width: number
  height: number
  poses: readonly Pose[]
}

function buildMapping(
  frame: LoadedFrame,
  cw: number,
  ch: number,
  requestRedraw: () => void
): BoardMapping {
  const scale = Math.min(cw / frame.width, ch / frame.height)
  const offsetX = Math.floor((cw - frame.width * scale) / 2)
  const offsetY = Math.floor((ch - frame.height * scale) / 2)
  return {
    view: frame.view,
    srcWidth: frame.width,
    srcHeight: frame.height,
    scale,
    offsetX,
    offsetY,
    toCanvas: (x, y) => [offsetX + x * scale, offsetY + y * scale],
    poses: frame.poses,
    now: performance.now(),
    requestRedraw
  }
}

function Board({ subscribe, onTap, overlay, label }: BoardProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const boxRef = useRef<HTMLDivElement | null>(null)
  const frameRef = useRef<LoadedFrame | null>(null)
  const rafRef = useRef(0)
  const lastSeqRef = useRef(-1)
  const overlayRef = useRef(overlay)
  const scheduleRef = useRef<() => void>(() => undefined)

  useEffect(() => {
    overlayRef.current = overlay
    scheduleRef.current()
  })

  useEffect(() => {
    const canvas = canvasRef.current
    const box = boxRef.current
    if (!canvas || !box) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const draw = (): void => {
      rafRef.current = 0
      const cw = box.clientWidth
      const ch = box.clientHeight
      if (canvas.width !== cw) canvas.width = cw
      if (canvas.height !== ch) canvas.height = ch
      ctx.imageSmoothingEnabled = false
      ctx.fillStyle = palette.ink
      ctx.fillRect(0, 0, cw, ch)
      const frame = frameRef.current
      if (!frame) return
      const mapping = buildMapping(frame, cw, ch, () => scheduleRef.current())
      ctx.drawImage(
        frame.image,
        mapping.offsetX,
        mapping.offsetY,
        Math.round(frame.width * mapping.scale),
        Math.round(frame.height * mapping.scale)
      )
      overlayRef.current?.(ctx, mapping)
    }

    const schedule = (): void => {
      if (rafRef.current === 0) rafRef.current = requestAnimationFrame(draw)
    }
    scheduleRef.current = schedule

    const observer = new ResizeObserver(schedule)
    observer.observe(box)

    const off = subscribe((message) => {
      if (message.type !== 'frame') return
      if (message.seq < lastSeqRef.current) return
      lastSeqRef.current = message.seq
      const image = new Image()
      image.onload = (): void => {
        if (message.seq < lastSeqRef.current) return
        frameRef.current = {
          image,
          view: message.view,
          width: message.width,
          height: message.height,
          poses: message.poses
        }
        schedule()
      }
      image.src = `data:image/jpeg;base64,${message.jpg}`
    })

    schedule()

    return () => {
      off()
      observer.disconnect()
      if (rafRef.current !== 0) cancelAnimationFrame(rafRef.current)
      rafRef.current = 0
      scheduleRef.current = () => undefined
    }
  }, [subscribe])

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>): void => {
    const canvas = canvasRef.current
    const frame = frameRef.current
    if (!onTap || !canvas || !frame) return
    const rect = canvas.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    const cx = ((event.clientX - rect.left) * canvas.width) / rect.width
    const cy = ((event.clientY - rect.top) * canvas.height) / rect.height
    const mapping = buildMapping(frame, canvas.width, canvas.height, () => undefined)
    const x = (cx - mapping.offsetX) / mapping.scale
    const y = (cy - mapping.offsetY) / mapping.scale
    if (x < 0 || y < 0 || x > frame.width || y > frame.height) return
    onTap([x, y], mapping)
  }

  return (
    <div ref={boxRef} className="relative h-full w-full overflow-hidden bg-gabi-ink">
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        className="absolute left-0 top-0 block"
        style={{ imageRendering: 'pixelated', cursor: onTap ? 'crosshair' : 'default' }}
        onClick={handleClick}
      />
    </div>
  )
}

export default Board

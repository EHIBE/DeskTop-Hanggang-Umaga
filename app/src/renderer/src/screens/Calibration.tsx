import { useCallback, useEffect, useState } from 'react'
import Board, { type BoardMapping } from '../canvas/Board'
import Bilingual from '../components/Bilingual'
import { t } from '../lib/copy'
import { palette } from '../lib/palette'
import type { MessageHandler } from '../lib/socket'
import type { CameraInfo, ClientMessage, Point, StateMessage } from '../lib/types'

type CalibrationProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
}>

const MIN_CM = 30
const MAX_CM = 120
const EDGE_CM = 5
const HANDLE = 32

function clampCm(raw: string, fallback: number): number {
  const value = Number(raw)
  if (!Number.isFinite(value) || raw.trim() === '') return fallback
  return Math.min(MAX_CM, Math.max(MIN_CM, Math.round(value)))
}

function inRange(raw: string): boolean {
  const value = Number(raw)
  return raw.trim() !== '' && Number.isFinite(value) && value >= MIN_CM && value <= MAX_CM
}

function Calibration({ state, send, subscribe }: CalibrationProps): React.JSX.Element {
  const preview = state.calibration_preview
  const [cameras, setCameras] = useState<readonly CameraInfo[]>([])
  const [corners, setCorners] = useState<readonly Point[]>([])
  const [widthText, setWidthText] = useState(String(state.play_w_cm))
  const [heightText, setHeightText] = useState(String(state.play_h_cm))
  const [wasPreview, setWasPreview] = useState(preview)

  if (wasPreview !== preview) {
    setWasPreview(preview)
    if (!preview) setCorners([])
  }

  useEffect(() => {
    const off = subscribe((message) => {
      if (message.type === 'devices') setCameras(message.cameras)
    })
    send({ type: 'devices.list' })
    return off
  }, [subscribe, send])

  const playW = clampCm(widthText, state.play_w_cm)
  const playH = clampCm(heightText, state.play_h_cm)
  const dimsValid = inRange(widthText) && inRange(heightText)

  const handleTap = useCallback(
    (point: Point, mapping: BoardMapping): void => {
      if (preview || mapping.view !== 'raw' || corners.length >= 4 || !dimsValid) return
      const next = [...corners, point]
      setCorners(next)
      if (next.length === 4) {
        send({
          type: 'calibrate.corners',
          corners: [next[0], next[1], next[2], next[3]],
          play_w_cm: playW,
          play_h_cm: playH
        })
      }
    },
    [preview, corners, dimsValid, playW, playH, send]
  )

  const overlay = useCallback(
    (ctx: CanvasRenderingContext2D, mapping: BoardMapping): void => {
      if (mapping.view === 'raw') {
        ctx.strokeStyle = palette.lantern
        ctx.lineWidth = 2
        ctx.beginPath()
        corners.forEach((corner, index) => {
          const [x, y] = mapping.toCanvas(corner[0], corner[1])
          if (index === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        })
        if (corners.length === 4) ctx.closePath()
        ctx.stroke()
        ctx.font = '16px "Press Start 2P"'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        corners.forEach((corner, index) => {
          const [x, y] = mapping.toCanvas(corner[0], corner[1])
          const left = Math.round(x - HANDLE / 2)
          const top = Math.round(y - HANDLE / 2)
          ctx.fillStyle = palette.lantern
          ctx.fillRect(left, top, HANDLE, HANDLE)
          ctx.strokeStyle = palette.ink
          ctx.lineWidth = 2
          ctx.strokeRect(left, top, HANDLE, HANDLE)
          ctx.fillStyle = palette.ink
          ctx.fillText(String(index + 1), left + HANDLE / 2, top + HANDLE / 2 + 1)
        })
      } else {
        const inset = ((EDGE_CM * mapping.srcWidth) / state.play_w_cm) * mapping.scale
        const [x0, y0] = mapping.toCanvas(0, 0)
        const [x1, y1] = mapping.toCanvas(mapping.srcWidth, mapping.srcHeight)
        ctx.strokeStyle = palette.kawayan
        ctx.lineWidth = 4
        ctx.setLineDash([16, 8])
        ctx.strokeRect(
          Math.round(x0 + inset),
          Math.round(y0 + inset),
          Math.round(x1 - x0 - inset * 2),
          Math.round(y1 - y0 - inset * 2)
        )
        ctx.setLineDash([])
      }
    },
    [corners, state.play_w_cm]
  )

  const reset = (): void => {
    setCorners([])
    if (preview) send({ type: 'calibrate.restart' })
  }

  return (
    <main className="flex h-full w-full gap-8 p-8">
      <aside className="panel flex w-[512px] flex-col gap-6 overflow-y-auto p-6">
        <Bilingual copyKey="calib.aim" />
        {preview ? (
          <Bilingual copyKey="calib.remove" />
        ) : (
          <>
            <Bilingual copyKey="calib.place" />
            <Bilingual copyKey="calib.tap" />
          </>
        )}
        <section aria-label={t('calib.camera').en} className="flex flex-col gap-4">
          <Bilingual copyKey="calib.camera" />
          {cameras.length === 0 ? (
            <Bilingual copyKey="calib.no_camera" />
          ) : (
            [...cameras]
              .sort((a, b) => Number(b.has_picture) - Number(a.has_picture))
              .map((camera) => {
                const active = state.camera?.index === camera.index
                return (
                  <button
                    key={camera.index}
                    type="button"
                    className="btn text-left"
                    aria-pressed={active}
                    onClick={() => send({ type: 'camera.select', index: camera.index })}
                  >
                    {active ? '> ' : ''}
                    {camera.index + 1} ({camera.width}x{camera.height})
                    {camera.has_picture ? '' : ` X ${t('calib.no_picture').tl}`}
                  </button>
                )
              })
          )}
        </section>
        <section className="flex flex-col gap-4">
          <label htmlFor="play-w">
            <Bilingual copyKey="calib.width" />
          </label>
          <input
            id="play-w"
            type="number"
            min={MIN_CM}
            max={MAX_CM}
            className="field w-full"
            value={widthText}
            disabled={preview || corners.length > 0}
            aria-invalid={!inRange(widthText)}
            onChange={(event) => setWidthText(event.target.value)}
          />
          <label htmlFor="play-h">
            <Bilingual copyKey="calib.height" />
          </label>
          <input
            id="play-h"
            type="number"
            min={MIN_CM}
            max={MAX_CM}
            className="field w-full"
            value={heightText}
            disabled={preview || corners.length > 0}
            aria-invalid={!inRange(heightText)}
            onChange={(event) => setHeightText(event.target.value)}
          />
        </section>
        <div className="mt-auto flex flex-col gap-4">
          {preview && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => send({ type: 'calibrate.done' })}
            >
              {t('calib.confirm').tl}
            </button>
          )}
          <button
            type="button"
            className="btn"
            disabled={!preview && corners.length === 0}
            onClick={reset}
          >
            {t('calib.reset').tl}
            <span className="caption-en block">{t('calib.reset').en}</span>
          </button>
        </div>
      </aside>
      <div className="panel min-w-0 flex-1 p-2">
        <Board
          subscribe={subscribe}
          onTap={preview ? undefined : handleTap}
          overlay={overlay}
          label={t(preview ? 'calib.remove' : 'calib.tap').en}
        />
      </div>
    </main>
  )
}

export default Calibration

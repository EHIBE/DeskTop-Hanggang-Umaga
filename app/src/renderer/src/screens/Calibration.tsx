import { useCallback, useEffect, useRef, useState } from 'react'
import Board, { type BoardMapping } from '../canvas/Board'
import LangToggle from '../components/LangToggle'
import PixelIcon from '../components/PixelIcon'
import { say, type CopyKey } from '../lib/copy'
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

type CamProblemKey = 'cam.busy' | 'cam.black'

type CamProblem = Readonly<{ key: CamProblemKey; index: number | null }>

function isCamProblem(key: string): key is CamProblemKey {
  return key === 'cam.busy' || key === 'cam.black'
}

type StepState = 'todo' | 'active' | 'done'

function Step({
  n,
  state,
  copyKey,
  extra
}: Readonly<{ n: number; state: StepState; copyKey: CopyKey; extra?: string }>): React.JSX.Element {
  return (
    <li className="step" data-state={state} aria-current={state === 'active' ? 'step' : undefined}>
      <span className="step-num">{state === 'done' ? <PixelIcon name="check" size={3} /> : n}</span>
      <span className="flex-1">{say(copyKey)}</span>
      {extra !== undefined && <span className="text-gabi-lantern">{extra}</span>}
    </li>
  )
}

function Calibration({ state, send, subscribe }: CalibrationProps): React.JSX.Element {
  const preview = state.calibration_preview
  const [cameras, setCameras] = useState<readonly CameraInfo[]>([])
  const [scanning, setScanning] = useState(true)
  const [corners, setCorners] = useState<readonly Point[]>([])
  const [widthText, setWidthText] = useState(String(state.play_w_cm))
  const [heightText, setHeightText] = useState(String(state.play_h_cm))
  const [wasPreview, setWasPreview] = useState(preview)
  const [camProblem, setCamProblem] = useState<CamProblem | null>(null)

  if (wasPreview !== preview) {
    setWasPreview(preview)
    if (!preview) setCorners([])
  }

  const latestIndex = useRef<number | null>(null)
  useEffect(() => {
    latestIndex.current = state.camera?.index ?? null
  })

  useEffect(() => {
    const off = subscribe((message) => {
      if (message.type === 'devices') {
        setCameras(message.cameras)
        setScanning(false)
      } else if (message.type === 'notice' && isCamProblem(message.copy_key)) {
        setCamProblem({ key: message.copy_key, index: latestIndex.current })
      }
    })
    if (!send({ type: 'devices.list' })) queueMicrotask(() => setScanning(false))
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

  const tapped = corners.length
  const placeState: StepState = preview || tapped > 0 ? 'done' : 'active'
  const tapState: StepState = preview ? 'done' : 'active'
  const removeState: StepState = preview ? 'active' : 'todo'
  const rescan = (): void => {
    setCamProblem(null)
    if (send({ type: 'devices.list' })) setScanning(true)
  }
  const rescanButton = (
    <button type="button" className="btn self-start" disabled={scanning} onClick={rescan}>
      {say('calib.rescan')}
    </button>
  )
  const problem =
    camProblem !== null && camProblem.index === (state.camera?.index ?? null) ? camProblem : null
  const sortedCameras = [...cameras].sort((a, b) => Number(b.has_picture) - Number(a.has_picture))

  return (
    <main className="flex h-full w-full gap-6 p-6">
      <aside className="window flex w-[560px] shrink-0 flex-col gap-8 overflow-y-auto p-8">
        <div className="flex flex-col gap-3">
          <h1 className="text-[24px] leading-[32px] text-gabi-lantern">{say('calib.title')}</h1>
          <p className="text-gabi-mist">{say('calib.aim')}</p>
        </div>
        <ol className="flex flex-col gap-2">
          <Step n={1} state={placeState} copyKey="calib.step_place" />
          <Step
            n={2}
            state={tapState}
            copyKey="calib.step_tap"
            extra={preview ? undefined : `${tapped}/4`}
          />
          <Step n={3} state={removeState} copyKey="calib.step_remove" />
        </ol>
        <section aria-labelledby="camera-label" className="flex flex-col gap-3">
          <span id="camera-label" className="label flex items-center gap-3">
            <PixelIcon name="camera" size={2} />
            {say('calib.camera')}
          </span>
          {scanning && sortedCameras.length === 0 ? (
            <p role="status" className="text-gabi-mist">
              {say('calib.scanning')}
            </p>
          ) : sortedCameras.length === 0 ? (
            <div className="flex flex-col gap-3">
              <p className="text-gabi-bukang">{say('calib.no_camera')}</p>
              {rescanButton}
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sortedCameras.map((camera) => (
                <button
                  key={camera.index}
                  type="button"
                  className="btn"
                  aria-pressed={state.camera?.index === camera.index}
                  title={`${camera.width}x${camera.height}`}
                  onClick={() => send({ type: 'camera.select', index: camera.index })}
                >
                  {camera.index + 1}
                  {!camera.has_picture && (
                    <span className="flex items-center gap-2 text-gabi-bukang">
                      <PixelIcon name="cross" size={2} />
                      {say('calib.no_picture')}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
          {sortedCameras.length > 0 && rescanButton}
          {problem !== null && (
            <p role="alert" className="flex items-start gap-2 text-gabi-bukang">
              <PixelIcon name="cross" size={2} />
              {say(problem.key)}
            </p>
          )}
        </section>
        <section aria-labelledby="area-label" className="flex flex-col gap-3">
          <span id="area-label" className="label">
            {say('calib.area')}
          </span>
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-2">
              <span className="text-gabi-mist">{say('calib.width')}</span>
              <input
                type="number"
                min={MIN_CM}
                max={MAX_CM}
                className="field w-full"
                value={widthText}
                disabled={preview || tapped > 0}
                aria-invalid={!inRange(widthText)}
                onChange={(event) => setWidthText(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-gabi-mist">{say('calib.height')}</span>
              <input
                type="number"
                min={MIN_CM}
                max={MAX_CM}
                className="field w-full"
                value={heightText}
                disabled={preview || tapped > 0}
                aria-invalid={!inRange(heightText)}
                onChange={(event) => setHeightText(event.target.value)}
              />
            </label>
          </div>
        </section>
        <div className="mt-auto flex flex-col gap-4">
          {preview && (
            <button
              type="button"
              className="btn btn-primary btn-big text-[24px]"
              onClick={() => send({ type: 'calibrate.done' })}
            >
              <PixelIcon name="check" size={4} />
              {say('calib.confirm')}
            </button>
          )}
          <div className="flex items-center gap-4">
            <button
              type="button"
              className="btn flex-1"
              disabled={!preview && tapped === 0}
              onClick={reset}
            >
              {say('calib.reset')}
            </button>
            <LangToggle />
          </div>
          <button type="button" className="btn" onClick={() => send({ type: 'calibrate.back' })}>
            {say('nav.back')}
          </button>
        </div>
      </aside>
      <div className="window min-w-0 flex-1 p-3">
        <Board
          subscribe={subscribe}
          onTap={preview ? undefined : handleTap}
          overlay={overlay}
          label={say(preview ? 'calib.remove' : 'calib.tap')}
        />
      </div>
    </main>
  )
}

export default Calibration

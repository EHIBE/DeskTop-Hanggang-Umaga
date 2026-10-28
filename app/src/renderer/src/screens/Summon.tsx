import { useCallback, useEffect, useMemo, useState } from 'react'
import SpriteView from '../canvas/SpriteView'
import { drawSprite, useUnitImages } from '../canvas/sprites'
import Board, { type BoardMapping } from '../canvas/Board'
import Bilingual from '../components/Bilingual'
import { isCopyKey, t, type CopyKey } from '../lib/copy'
import { palette } from '../lib/palette'
import type { MessageHandler } from '../lib/socket'
import type { ClientMessage, Point, StateMessage, UnitSummary } from '../lib/types'
import UnitCard from './UnitCard'

type SummonProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
}>

const MAX_UNITS = 12
const NAME_MAX = 40
const EDGE_CM = 5
const MARKER = 32
const BUSY_TIMEOUT_MS = 15000

function Summon({ state, send, subscribe }: SummonProps): React.JSX.Element {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [cardUnit, setCardUnit] = useState<UnitSummary | null>(null)
  const [beginNote, setBeginNote] = useState<CopyKey | null>(null)

  const ordered = useMemo(
    () => [
      ...state.units.filter((unit) => unit.class === 'kubo'),
      ...state.units.filter((unit) => unit.class !== 'kubo')
    ],
    [state.units]
  )
  const images = useUnitImages(state.units)
  const hasKubo = ordered.length > 0 && ordered[0].class === 'kubo'
  const full = state.units.length >= MAX_UNITS
  const blocked = state.begin_block_key !== null
  const blockKey: CopyKey =
    state.begin_block_key !== null && isCopyKey(state.begin_block_key)
      ? state.begin_block_key
      : 'summon.kubo_first'
  const shownCard = cardUnit
    ? (state.units.find((unit) => unit.unit_id === cardUnit.unit_id) ?? cardUnit)
    : null

  useEffect(() => {
    return subscribe((message) => {
      if (message.type === 'card') {
        setBusy(false)
        setCardUnit(message.unit)
        setName('')
      } else if (message.type === 'notice') {
        setBusy(false)
      }
    })
  }, [subscribe])

  useEffect(() => {
    if (!busy) return
    const timer = setTimeout(() => setBusy(false), BUSY_TIMEOUT_MS)
    return () => clearTimeout(timer)
  }, [busy])

  const trimmed = name.trim()
  const canSend = trimmed !== '' && !busy && !state.awaiting_tap && !full

  const submit = (): void => {
    if (!canSend) return
    if (send({ type: 'summon.name', name: trimmed })) setBusy(true)
  }

  const handleTap = useCallback(
    (point: Point, mapping: BoardMapping): void => {
      if (!state.awaiting_tap || mapping.view !== 'warped') return
      if (send({ type: 'summon.tap', point })) setBusy(true)
    },
    [state.awaiting_tap, send]
  )

  const overlay = useCallback(
    (ctx: CanvasRenderingContext2D, mapping: BoardMapping): void => {
      if (mapping.view !== 'warped') return
      const pxPerCm = mapping.srcWidth / state.play_w_cm
      const inset = EDGE_CM * pxPerCm * mapping.scale
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
      ctx.font = '16px "Press Start 2P"'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ordered.forEach((unit, index) => {
        const [x, y] = mapping.toCanvas(unit.x_cm * pxPerCm, unit.y_cm * pxPerCm)
        const image = images.get(unit.unit_id)
        const badgeFill = unit.class === 'kubo' ? palette.lantern : palette.moon
        if (image) {
          const box = drawSprite(ctx, image, x, y, 2)
          const badge = 28
          ctx.fillStyle = badgeFill
          ctx.fillRect(box.left, box.top, badge, badge)
          ctx.strokeStyle = palette.ink
          ctx.lineWidth = 2
          ctx.strokeRect(box.left, box.top, badge, badge)
          ctx.fillStyle = palette.ink
          ctx.fillText(String(index + 1), box.left + badge / 2, box.top + badge / 2 + 1)
          return
        }
        const left = Math.round(x - MARKER / 2)
        const top = Math.round(y - MARKER / 2)
        ctx.fillStyle = badgeFill
        ctx.fillRect(left, top, MARKER, MARKER)
        ctx.strokeStyle = palette.ink
        ctx.lineWidth = 2
        ctx.strokeRect(left, top, MARKER, MARKER)
        ctx.fillStyle = palette.ink
        ctx.fillText(String(index + 1), left + MARKER / 2, top + MARKER / 2 + 1)
      })
    },
    [ordered, images, state.play_w_cm]
  )

  const begin = (): void => {
    setBeginNote(blocked ? blockKey : 'night.start')
  }

  return (
    <main className="relative flex h-full w-full gap-8 p-8">
      <aside className="panel flex w-[512px] shrink-0 flex-col gap-6 overflow-y-auto p-6">
        <Bilingual copyKey={state.awaiting_tap ? 'summon.which' : 'summon.prompt'} />
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <label htmlFor="unit-name">
            <Bilingual copyKey="summon.name_label" />
          </label>
          <div className="flex gap-4">
            <input
              id="unit-name"
              className="field min-w-0 flex-1"
              value={name}
              maxLength={NAME_MAX}
              disabled={busy || state.awaiting_tap}
              onChange={(event) => setName(event.target.value)}
            />
            <button type="submit" className="btn btn-primary" disabled={!canSend}>
              {t('summon.name_go').tl}
            </button>
          </div>
          {busy && (
            <p role="status" aria-live="polite" className="caption-en">
              {t('summon.busy').tl}
            </p>
          )}
          {full && <Bilingual copyKey="summon.full" />}
        </form>
        <section aria-label={t('summon.roster').en} className="flex flex-col gap-3">
          <div className="flex justify-between">
            <span>{t('summon.roster').tl}</span>
            <span>
              {state.units.length} / {MAX_UNITS}
            </span>
          </div>
          {!hasKubo && (
            <div className="border-2 border-dashed border-gabi-lantern p-3">
              <p className="text-gabi-lantern">1. {t('class.kubo').tl}</p>
              <p className="caption-en">{t('summon.kubo_first').en}</p>
            </div>
          )}
          {ordered.map((unit, index) => (
            <button
              key={unit.unit_id}
              type="button"
              className={`btn flex w-full items-center justify-between gap-2 text-left ${
                unit.class === 'kubo' ? 'border-gabi-lantern' : ''
              }`}
              onClick={() => setCardUnit(unit)}
            >
              <SpriteView
                unit={unit}
                scale={2}
                fallback={
                  <span className="text-gabi-lantern">
                    {t(`class.${unit.class}`).tl.slice(0, 2).toUpperCase()}
                  </span>
                }
              />
              <span className="min-w-0 flex-1 break-words">
                {index + 1}. {unit.name}
              </span>
              <span className="shrink-0">
                {t(`class.${unit.class}`).tl} {unit.hp}/{unit.hp_max}
              </span>
            </button>
          ))}
        </section>
        <div className="mt-auto flex flex-col gap-3">
          {beginNote !== null && (
            <div role="status" aria-live="polite">
              <Bilingual copyKey={beginNote} />
            </div>
          )}
          <button
            type="button"
            className="btn btn-primary aria-disabled:cursor-not-allowed aria-disabled:bg-gabi-slate"
            aria-disabled={blocked}
            onClick={begin}
          >
            {t('summon.begin').tl}
          </button>
        </div>
      </aside>
      <div className="panel min-w-0 flex-1 p-2">
        <Board
          subscribe={subscribe}
          onTap={state.awaiting_tap ? handleTap : undefined}
          overlay={overlay}
          label={t(state.awaiting_tap ? 'summon.which' : 'summon.prompt').en}
        />
      </div>
      {shownCard && <UnitCard unit={shownCard} send={send} onClose={() => setCardUnit(null)} />}
    </main>
  )
}

export default Summon

import { useCallback, useEffect, useRef, useState } from 'react'
import Board, { type BoardMapping } from '../canvas/Board'
import { drawIntentArrow } from '../canvas/arrows'
import { drawTag } from '../canvas/draw'
import { drawEnemy, useEnemyFrames } from '../canvas/enemies'
import { drawFloaters, floatersFromEvents, type Floater } from '../canvas/floaters'
import { drawMoveRing, drawStartGhost } from '../canvas/rings'
import { MIN_SCALE, drawSprite, useUnitImages } from '../canvas/sprites'
import Bilingual from '../components/Bilingual'
import Narration from '../hud/Narration'
import OrderChips from '../hud/OrderChips'
import TapMenu from '../hud/TapMenu'
import TopBar from '../hud/TopBar'
import UnitStrip from '../hud/UnitStrip'
import { actionTarget, enemyLabel } from '../hud/targets'
import { t } from '../lib/copy'
import { palette } from '../lib/palette'
import type { MessageHandler } from '../lib/socket'
import type {
  ClientMessage,
  IntentAction,
  NarrationMessage,
  Point,
  StateMessage
} from '../lib/types'

type NightProps = Readonly<{
  state: StateMessage
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
  narration: NarrationMessage | null
}>

type Selection = Readonly<{ turnKey: string; unitId: string; pending: IntentAction | null }>

type Spot = Readonly<{ x_cm: number; y_cm: number }>

const BOB_TICK_MS = 500
const HIT_PX = 56
const ARROW_PHASES: ReadonlySet<string> = new Set([
  'SPAWN_TELEGRAPH',
  'PLAYER_PHASE',
  'END_TURN_SNAPSHOT',
  'VALIDATE'
])

function Night({ state, send, subscribe, narration }: NightProps): React.JSX.Element {
  const night = state.night
  const [selection, setSelection] = useState<Selection | null>(null)
  const [hitCount, setHitCount] = useState(0)
  const [blockedHeard, setBlockedHeard] = useState(false)
  const [pulse, setPulse] = useState(0)
  const floatersRef = useRef<readonly Floater[]>([])
  const knownRef = useRef(new Map<string, Spot>())
  const latestRef = useRef(state)
  const unitImages = useUnitImages(state.units)
  const enemyFrames = useEnemyFrames(night ? night.enemies : [])

  useEffect(() => {
    latestRef.current = state
  })

  useEffect(() => {
    return subscribe((message) => {
      if (message.type === 'events') {
        const locate = (id: string | null): Spot | null => {
          if (id === null) return null
          const known = knownRef.current.get(id)
          if (known) return known
          const current = latestRef.current
          const enemy = current.night?.enemies.find((candidate) => candidate.id === id)
          if (enemy) return enemy
          return current.units.find((candidate) => candidate.id === id) ?? null
        }
        const made = floatersFromEvents(
          message.events,
          locate,
          performance.now(),
          t('enemy.dodge').tl
        )
        floatersRef.current = [...floatersRef.current, ...made]
        if (message.events.some((event) => event.type === 'kubo_hit')) {
          setHitCount((count) => count + 1)
        }
        setPulse((value) => value + 1)
      } else if (message.type === 'notice' && message.copy_key === 'endturn.blocked') {
        setBlockedHeard(true)
      }
    })
  }, [subscribe])

  const hasEnemies = night !== null && night.enemies.length > 0
  useEffect(() => {
    if (!hasEnemies) return
    const timer = setInterval(() => setPulse((value) => value + 1), BOB_TICK_MS)
    return () => clearInterval(timer)
  }, [hasEnemies])

  const phase = state.phase
  const playerPhase = phase === 'PLAYER_PHASE'
  const turnKey = night ? `${night.number}:${night.turn}` : ''
  const activeSelection =
    selection !== null && selection.turnKey === turnKey && playerPhase ? selection : null
  const selectedNight = night?.units.find((unit) => unit.id === activeSelection?.unitId)
  const selectedUnit = state.units.find((unit) => unit.id === activeSelection?.unitId)
  const selectionValid =
    activeSelection !== null &&
    selectedNight !== undefined &&
    selectedUnit !== undefined &&
    !selectedNight.is_down
  const pending = selectionValid ? activeSelection.pending : null
  const targetKind =
    pending !== null && selectedUnit ? actionTarget(pending, selectedUnit.power_id) : null

  const select = useCallback(
    (unitId: string): void => {
      setSelection({ turnKey, unitId, pending: null })
    },
    [turnKey]
  )

  const clear = useCallback((): void => setSelection(null), [])

  const pick = useCallback(
    (action: IntentAction): void => {
      if (!selectedUnit) return
      const kind = actionTarget(action, selectedUnit.power_id)
      if (kind === 'none') {
        send({ type: 'intent.tap', unit_id: selectedUnit.id, action, target_id: null })
        setSelection(null)
        return
      }
      setSelection({ turnKey, unitId: selectedUnit.id, pending: action })
    },
    [selectedUnit, send, turnKey]
  )

  const handleTap = useCallback(
    (point: Point, mapping: BoardMapping): void => {
      if (!night || !playerPhase || mapping.view !== 'warped') return
      const pxPerCm = mapping.srcWidth / state.play_w_cm
      const poseById = new Map(mapping.poses.map((pose) => [pose.id, pose]))
      const limit = HIT_PX / mapping.scale
      const nearest = (
        candidates: readonly Readonly<{ id: string; x: number; y: number }>[]
      ): string | null => {
        let best: string | null = null
        let bestDistance = limit
        candidates.forEach((candidate) => {
          const distance = Math.hypot(candidate.x - point[0], candidate.y - point[1])
          if (distance <= bestDistance) {
            best = candidate.id
            bestDistance = distance
          }
        })
        return best
      }
      const allies = night.units
        .filter((unit) => !unit.is_down)
        .map((unit) => {
          const summary = state.units.find((candidate) => candidate.id === unit.id)
          const pose = poseById.get(unit.id)
          const x = pose ? pose.x_cm : summary ? summary.x_cm : null
          const y = pose ? pose.y_cm : summary ? summary.y_cm : null
          return { id: unit.id, kubo: summary?.class === 'kubo', x, y }
        })
        .filter(
          (ally): ally is { id: string; kubo: boolean; x: number; y: number } =>
            ally.x !== null && ally.y !== null
        )
        .map((ally) => ({ ...ally, x: ally.x * pxPerCm, y: ally.y * pxPerCm }))
      if (pending !== null && selectionValid && targetKind !== null) {
        const pool =
          targetKind === 'enemy'
            ? night.enemies.map((enemy) => ({
                id: enemy.id,
                x: enemy.x_cm * pxPerCm,
                y: enemy.y_cm * pxPerCm
              }))
            : allies
        const hit = nearest(pool)
        if (hit !== null) {
          send({
            type: 'intent.tap',
            unit_id: activeSelection.unitId,
            action: pending,
            target_id: hit
          })
          setSelection(null)
        }
        return
      }
      const hit = nearest(allies.filter((ally) => !ally.kubo))
      if (hit === null) setSelection(null)
      else select(hit)
    },
    [
      night,
      playerPhase,
      state.play_w_cm,
      state.units,
      pending,
      selectionValid,
      targetKind,
      activeSelection,
      send,
      select
    ]
  )

  const overlay = useCallback(
    (ctx: CanvasRenderingContext2D, mapping: BoardMapping): void => {
      if (!night || mapping.view !== 'warped') return
      const pxPerCm = mapping.srcWidth / state.play_w_cm
      const [x0, y0] = mapping.toCanvas(0, 0)
      const [x1, y1] = mapping.toCanvas(mapping.srcWidth, mapping.srcHeight)
      ctx.globalAlpha = 0.6
      ctx.fillStyle = palette.ink
      ctx.fillRect(Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0))
      ctx.globalAlpha = 1
      const toCanvas = (xCm: number, yCm: number): Point =>
        mapping.toCanvas(xCm * pxPerCm, yCm * pxPerCm)
      const poseById = new Map(mapping.poses.map((pose) => [pose.id, pose]))
      const unitSpot = new Map<string, Spot>()
      state.units.forEach((unit) => {
        const pose = poseById.get(unit.id)
        unitSpot.set(unit.id, pose ?? unit)
      })
      unitSpot.forEach((spot, id) => knownRef.current.set(id, spot))
      night.enemies.forEach((enemy) => knownRef.current.set(enemy.id, enemy))
      const illegal = new Set(night.illegal_units)
      const nightById = new Map(night.units.map((unit) => [unit.id, unit]))

      if (playerPhase) {
        night.units.forEach((nu) => {
          const spot = unitSpot.get(nu.id)
          if (!spot) return
          const [ux, uy] = toCanvas(spot.x_cm, spot.y_cm)
          const [cx, cy] = toCanvas(nu.start_x_cm, nu.start_y_cm)
          const unit = state.units.find((candidate) => candidate.id === nu.id)
          drawMoveRing(ctx, {
            centerX: cx,
            centerY: cy,
            radiusPx: nu.move_cm * pxPerCm * mapping.scale,
            unitX: ux,
            unitY: uy,
            legal: nu.is_move_legal,
            down: nu.is_down
          })
          if (illegal.has(nu.id)) {
            drawStartGhost(
              ctx,
              unit ? (unitImages.get(unit.unit_id) ?? null) : null,
              cx,
              cy,
              MIN_SCALE
            )
          }
        })
      }

      if (ARROW_PHASES.has(phase)) {
        night.enemies.forEach((enemy) => {
          if (!enemy.intent || enemy.stunned) return
          const target = unitSpot.get(enemy.intent.target_id)
          if (!target) return
          const [ex, ey] = toCanvas(enemy.x_cm, enemy.y_cm)
          const [tx, ty] = toCanvas(target.x_cm, target.y_cm)
          drawIntentArrow(ctx, ex, ey, tx, ty, enemy.intent.dmg)
        })
      }

      night.enemies.forEach((enemy) => {
        const [ex, ey] = toCanvas(enemy.x_cm, enemy.y_cm)
        drawEnemy(
          ctx,
          enemy,
          enemyFrames.get(enemy.part === null ? enemy.type : `${enemy.type}_${enemy.part}`) ?? [],
          ex,
          ey,
          pxPerCm * mapping.scale,
          mapping.now
        )
        drawTag(ctx, enemyLabel(night.enemies, enemy), ex, ey + 40, palette.moon)
      })

      state.units.forEach((unit) => {
        const nu = nightById.get(unit.id)
        const spot = unitSpot.get(unit.id)
        if (!nu || !spot) return
        const [ux, uy] = toCanvas(spot.x_cm, spot.y_cm)
        const image = unitImages.get(unit.unit_id)
        let box = { left: Math.round(ux - 24), top: Math.round(uy - 24), width: 48, height: 48 }
        ctx.save()
        if (nu.is_down) {
          ctx.filter = 'grayscale(1)'
          ctx.globalAlpha = 0.6
        }
        if (image) {
          box = drawSprite(ctx, image, ux, uy, MIN_SCALE)
        } else {
          ctx.fillStyle = unit.class === 'kubo' ? palette.lantern : palette.moon
          ctx.fillRect(box.left, box.top, box.width, box.height)
        }
        ctx.restore()
        if (activeSelection?.unitId === unit.id) {
          ctx.strokeStyle = palette.lantern
          ctx.lineWidth = 4
          ctx.setLineDash([])
          ctx.strokeRect(box.left - 4, box.top - 4, box.width + 8, box.height + 8)
        }
        const label = nu.is_down ? `${unit.name} ${t('hud.down').tl}` : unit.name
        drawTag(ctx, label, ux, box.top + box.height + 4, nu.is_down ? palette.mist : palette.moon)
      })

      if (targetKind !== null && targetKind !== 'none') {
        ctx.strokeStyle = palette.lantern
        ctx.lineWidth = 4
        ctx.setLineDash([12, 8])
        const marks: Spot[] =
          targetKind === 'enemy'
            ? night.enemies.map((enemy) => enemy)
            : night.units
                .filter((nu) => !nu.is_down)
                .map((nu) => unitSpot.get(nu.id))
                .filter((spot): spot is Spot => spot !== undefined)
        marks.forEach((spot) => {
          const [mx, my] = toCanvas(spot.x_cm, spot.y_cm)
          ctx.strokeRect(Math.round(mx - 56), Math.round(my - 56), 112, 112)
        })
        ctx.setLineDash([])
      }

      const alive = drawFloaters(ctx, floatersRef.current, toCanvas, mapping.now)
      floatersRef.current = alive
      if (alive.length > 0) mapping.requestRedraw()
    },
    [
      night,
      phase,
      playerPhase,
      state.units,
      state.play_w_cm,
      unitImages,
      enemyFrames,
      activeSelection,
      targetKind
    ]
  )

  if (!night) {
    return (
      <main className="flex h-full w-full items-center justify-center" role="status">
        <Bilingual copyKey="restore" className="text-center" />
      </main>
    )
  }

  const checking = phase === 'END_TURN_SNAPSHOT' || phase === 'VALIDATE'
  const blocked = blockedHeard && night.illegal_units.length > 0 && playerPhase

  const nightNarration =
    narration !== null &&
    narration.night === night.number &&
    (narration.phase === 'night_start' || narration.phase === 'resolution_then_telegraph')
      ? narration
      : null

  return (
    <main className="flex h-full w-full flex-col" data-pulse={pulse}>
      <TopBar night={night} phase={phase} demoSafe={state.demo_safe} hitCount={hitCount} />
      <div className="relative flex min-h-0 flex-1 gap-4 p-4">
        <div className="panel relative min-w-0 flex-1 p-2">
          <Board
            subscribe={subscribe}
            onTap={playerPhase ? handleTap : undefined}
            overlay={overlay}
            label={t('hud.board').en}
          />
          {phase === 'PAUSED' && (
            <div className="absolute inset-0 flex items-center justify-center bg-gabi-ink/80">
              <div
                role="alertdialog"
                aria-label={t('cam.moved').en}
                className="banner flex w-[720px] flex-col items-center gap-6 p-8 text-center"
              >
                <Bilingual copyKey="cam.moved" />
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => send({ type: 'calibrate.restart' })}
                >
                  {t('hud.recalibrate').tl}
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="flex min-h-0 w-[440px] shrink-0 flex-col gap-4">
          {selectionValid && selectedUnit && selectedNight && (
            <TapMenu
              unit={selectedUnit}
              night={selectedNight}
              pending={pending}
              onPick={pick}
              onCancel={clear}
            />
          )}
          <UnitStrip
            units={state.units}
            nightUnits={night.units}
            selectedId={selectionValid ? activeSelection.unitId : null}
            interactive={playerPhase}
            onSelect={select}
          />
        </div>
      </div>
      <Narration narration={nightNarration} className="mx-4 mb-2" />
      <footer className="flex min-h-[104px] shrink-0 items-center gap-6 border-t-2 border-gabi-dusk bg-gabi-night px-8 py-2">
        <OrderChips
          chips={night.chips}
          units={state.units}
          enemies={night.enemies}
          interactive={playerPhase}
          onCancel={(chipId) => send({ type: 'chip.cancel', chip_id: chipId })}
        />
        {checking && (
          <div role="status" aria-live="polite" className="banner w-[520px] p-3">
            <Bilingual copyKey="endturn.checking" />
            {phase === 'END_TURN_SNAPSHOT' && <Bilingual copyKey="endturn.hands" />}
          </div>
        )}
        {blocked && (
          <div role="alert" className="banner banner-error w-[520px] p-3">
            <Bilingual copyKey="endturn.blocked" />
          </div>
        )}
        <button
          type="button"
          className="btn btn-primary h-[72px] w-[360px] shrink-0 text-[24px]"
          disabled={!playerPhase}
          onClick={() => send({ type: 'end_turn' })}
        >
          {t('hud.end_turn').tl}
        </button>
      </footer>
    </main>
  )
}

export default Night

import { currentLang } from '../lib/lang'
import { useEffect, useState } from 'react'
import CropView from '../canvas/CropView'
import SpriteView from '../canvas/SpriteView'
import PixelIcon from '../components/PixelIcon'
import UnitMarks from '../components/UnitMarks'
import { useAssets } from '../lib/assets'
import { isCopyKey, pick, say, t, type CopyKey } from '../lib/copy'
import type { ClientMessage, UnitSummary } from '../lib/types'

type UnitCardProps = Readonly<{
  unit: UnitSummary
  send: (message: ClientMessage) => boolean
  locked?: boolean
  docked?: boolean
  onClose: () => void
}>

const NAME_MAX = 40
const SPRITE = 48
const SPRITE_SCALE = 4
const CROP_SIZE = 256

function classKey(unit: UnitSummary): CopyKey {
  return `class.${unit.class}`
}

function initials(unit: UnitSummary): string {
  return say(classKey(unit)).slice(0, 2).toUpperCase()
}

function UnitCard({
  unit,
  send,
  locked = false,
  docked = false,
  onClose
}: UnitCardProps): React.JSX.Element {
  const [renaming, setRenaming] = useState(false)
  const [draft, setDraft] = useState(unit.name)
  const [showReal, setShowReal] = useState(true)
  const crop = useAssets().crops?.[unit.unit_id] ?? null
  const real = crop !== null && showReal
  const artSize = real ? CROP_SIZE : SPRITE * SPRITE_SCALE

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const powerKey = `power.${unit.power_id}`
  const powerCopy = isCopyKey(powerKey) ? t(powerKey) : null
  const powerName = unit.power_name_tl.trim() !== '' ? unit.power_name_tl : (powerCopy?.tl ?? '')
  const cardText = currentLang() === 'en' ? unit.card_text_en : unit.card_text_tl
  const powerText = cardText.trim() !== '' ? cardText : (powerCopy?.en ?? '')
  const cls = t(classKey(unit))
  const trimmed = draft.trim()

  const saveName = (): void => {
    if (trimmed === '' || trimmed.length > NAME_MAX) return
    send({ type: 'unit.rename', unit_id: unit.unit_id, name: trimmed })
    setRenaming(false)
  }

  return (
    <div
      className={
        docked
          ? 'pointer-events-none absolute inset-0 z-20 flex items-start justify-end p-8'
          : 'absolute inset-0 z-20 flex items-center justify-center bg-gabi-ink/80'
      }
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal={!docked}
        aria-label={unit.name}
        className={`panel pointer-events-auto flex flex-col gap-6 p-8 ${
          docked ? 'w-[760px]' : 'w-[1200px]'
        }`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex gap-8">
          <div className="flex shrink-0 flex-col gap-3">
            <div
              className="relative border-2 border-gabi-ink bg-gabi-dusk"
              style={{ width: artSize, height: artSize }}
              aria-hidden="true"
            >
              {real ? (
                <CropView png={crop} size={CROP_SIZE} />
              ) : (
                <>
                  <SpriteView
                    unit={unit}
                    scale={SPRITE_SCALE}
                    fallback={<span className="text-gabi-lantern">{initials(unit)}</span>}
                  />
                  {unit.sprite_png === null && (
                    <div className="lantern absolute bottom-2 right-2" />
                  )}
                </>
              )}
            </div>
            {crop !== null && (
              <button
                type="button"
                className="btn"
                aria-pressed={showReal}
                onClick={() => setShowReal(!showReal)}
              >
                <PixelIcon name={showReal ? 'check' : 'cross'} size={3} />
                {say('card.real')}
              </button>
            )}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-4">
            {renaming ? (
              <form
                className="flex gap-4"
                onSubmit={(event) => {
                  event.preventDefault()
                  saveName()
                }}
              >
                <input
                  className="field min-w-0 flex-1"
                  value={draft}
                  maxLength={NAME_MAX}
                  autoFocus
                  aria-label={say('summon.rename')}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={trimmed === ''}>
                  {say('summon.rename_save')}
                </button>
              </form>
            ) : (
              <div className="flex flex-wrap items-center gap-4">
                <h2 className="break-words text-gabi-lantern">{unit.name}</h2>
                <UnitMarks badges={unit.badges} scars={unit.scars} size={3} />
                {unit.returning && (
                  <span
                    role="status"
                    className="inline-flex items-center gap-2 border-2 border-gabi-dahon px-3 text-gabi-dahon"
                  >
                    <PixelIcon name="arrow" size={3} />
                    {say('unit.returning')}
                  </span>
                )}
              </div>
            )}
            <p>
              {say('card.class')}: {pick(cls)}
            </p>
            <p>
              HP {unit.hp}/{unit.hp_max} &nbsp; ATK {unit.atk}
            </p>
            <p>
              {say('card.move')}: {say(`move.${unit.move}`)} &nbsp; {say('card.range')}:{' '}
              {say(`range.${unit.range}`)}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <p>
            {say('card.power')}: {powerName === '' ? say('power.none') : powerName}
            {powerText !== '' && `: ${powerText}`}
          </p>
          <p>
            {say('card.owner')}: {say('card.owner_none')}
          </p>
        </div>
        <div className="flex gap-4">
          <button
            type="button"
            className="btn"
            disabled={locked || unit.returning || unit.rerolls_left <= 0}
            onClick={() => send({ type: 'unit.reroll', unit_id: unit.unit_id })}
          >
            {say('summon.reroll')} ({unit.rerolls_left})
          </button>
          <button
            type="button"
            className="btn"
            aria-pressed={renaming}
            onClick={() => {
              setDraft(unit.name)
              setRenaming(!renaming)
            }}
          >
            {say('summon.rename')}
          </button>
          <button type="button" className="btn ml-auto" onClick={onClose}>
            {say('summon.close')}
          </button>
        </div>
      </section>
    </div>
  )
}

export default UnitCard

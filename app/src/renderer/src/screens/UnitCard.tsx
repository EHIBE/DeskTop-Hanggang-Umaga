import { useEffect, useState } from 'react'
import SpriteView from '../canvas/SpriteView'
import { isCopyKey, t, type CopyKey } from '../lib/copy'
import type { ClientMessage, UnitSummary } from '../lib/types'

type UnitCardProps = Readonly<{
  unit: UnitSummary
  send: (message: ClientMessage) => boolean
  locked?: boolean
  onClose: () => void
}>

const NAME_MAX = 40
const SPRITE = 48
const SPRITE_SCALE = 4

function classKey(unit: UnitSummary): CopyKey {
  return `class.${unit.class}`
}

function initials(unit: UnitSummary): string {
  return t(classKey(unit)).tl.slice(0, 2).toUpperCase()
}

function UnitCard({ unit, send, locked = false, onClose }: UnitCardProps): React.JSX.Element {
  const [renaming, setRenaming] = useState(false)
  const [draft, setDraft] = useState(unit.name)

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
  const powerText = unit.card_text_tl.trim() !== '' ? unit.card_text_tl : (powerCopy?.en ?? '')
  const cls = t(classKey(unit))
  const trimmed = draft.trim()

  const saveName = (): void => {
    if (trimmed === '' || trimmed.length > NAME_MAX) return
    send({ type: 'unit.rename', unit_id: unit.unit_id, name: trimmed })
    setRenaming(false)
  }

  return (
    <div
      className="absolute inset-0 z-20 flex items-center justify-center bg-gabi-ink/80"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={unit.name}
        className="panel flex w-[1200px] flex-col gap-6 p-8"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex gap-8">
          <div
            className="relative shrink-0 border-2 border-gabi-ink bg-gabi-dusk"
            style={{ width: SPRITE * SPRITE_SCALE, height: SPRITE * SPRITE_SCALE }}
            aria-hidden="true"
          >
            <SpriteView
              unit={unit}
              scale={SPRITE_SCALE}
              fallback={<span className="text-gabi-lantern">{initials(unit)}</span>}
            />
            {unit.sprite_png === null && <div className="lantern absolute bottom-2 right-2" />}
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
                  aria-label={t('summon.rename').en}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={trimmed === ''}>
                  {t('summon.rename_save').tl}
                </button>
              </form>
            ) : (
              <h2 className="break-words text-gabi-lantern">{unit.name}</h2>
            )}
            <p>
              {t('card.class').tl}: {cls.tl}
              <span className="caption-en block">{cls.en}</span>
            </p>
            <p>
              HP {unit.hp}/{unit.hp_max} &nbsp; ATK {unit.atk}
            </p>
            <p>
              {t('card.move').tl}: {t(`move.${unit.move}`).tl} &nbsp; {t('card.range').tl}:{' '}
              {t(`range.${unit.range}`).tl}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <p>
            {t('card.power').tl}: {powerName === '' ? t('power.none').tl : powerName}
            {powerText !== '' && `: ${powerText}`}
          </p>
          {unit.card_text_en.trim() !== '' && <p className="caption-en">EN: {unit.card_text_en}</p>}
          <p>
            {t('card.owner').en}: {t('card.owner_none').tl}
          </p>
        </div>
        <div className="flex gap-4">
          <button
            type="button"
            className="btn"
            disabled={locked || unit.rerolls_left <= 0}
            onClick={() => send({ type: 'unit.reroll', unit_id: unit.unit_id })}
          >
            {t('summon.reroll').tl} ({unit.rerolls_left})
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
            {t('summon.rename').tl}
          </button>
          <button type="button" className="btn ml-auto" onClick={onClose}>
            {t('summon.close').tl}
          </button>
        </div>
      </section>
    </div>
  )
}

export default UnitCard

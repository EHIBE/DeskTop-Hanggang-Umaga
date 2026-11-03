import SpeakerChip from '../components/SpeakerChip'
import { pick, say, t } from '../lib/copy'
import { speakerSlot } from '../lib/speaker'
import type { Chip, EnemySummary, UnitSummary } from '../lib/types'
import { targetLabel } from './targets'

type OrderChipsProps = Readonly<{
  chips: readonly Chip[]
  players: readonly string[]
  units: readonly UnitSummary[]
  enemies: readonly EnemySummary[]
  interactive: boolean
  onCancel: (chipId: string) => void
}>

function actionWord(
  chip: Chip,
  unit: UnitSummary | undefined
): Readonly<{ tl: string; en: string }> {
  if (chip.action === 'attack') return t('act.attack')
  if (chip.action === 'heal') return t('act.heal')
  const name = unit && unit.power_name_tl !== '' ? unit.power_name_tl : say('card.power')
  return { tl: name, en: name }
}

function OrderChips({
  chips,
  players,
  units,
  enemies,
  interactive,
  onCancel
}: OrderChipsProps): React.JSX.Element {
  return (
    <section
      aria-label={say('hud.orders')}
      className="flex min-w-0 flex-1 flex-wrap items-center gap-3"
    >
      {chips.length === 0 && <p className="caption-en">{say('hud.no_orders')}</p>}
      {chips.map((chip) => {
        const unit = units.find((candidate) => candidate.id === chip.unit_id)
        const unitName = unit ? unit.name : chip.unit_id
        const action = actionWord(chip, unit)
        const params: Record<string, string> = { unit: unitName, action: pick(action) }
        if (chip.target_id !== null) {
          params.target = targetLabel(chip.target_id, units, enemies)
        }
        const text = t(chip.target_id === null ? 'chip.self' : 'chip.text', params)
        return (
          <div
            key={chip.chip_id}
            className="flex items-center border-2 border-gabi-ink bg-gabi-dusk"
          >
            {chip.source === 'voice' && chip.speaker && (
              <SpeakerChip slot={speakerSlot(chip.speaker, players)} className="ml-2" />
            )}
            {chip.source === 'voice' && (
              <span
                className="ml-2 border-2 border-gabi-lantern px-2 text-gabi-lantern"
                title={say('voice.chip_mic')}
              >
                <span aria-hidden="true">{'♪ '}</span>
                {say('voice.chip_mic')}
              </span>
            )}
            <span className="px-3">{pick(text)}</span>
            <button
              type="button"
              className="btn h-[48px] w-[48px] px-0"
              aria-label={`${say('hud.chip_cancel')}: ${pick(text)}`}
              title={say('hud.chip_cancel')}
              disabled={!interactive}
              onClick={() => onCancel(chip.chip_id)}
            >
              X
            </button>
          </div>
        )
      })}
    </section>
  )
}

export default OrderChips

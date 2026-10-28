import { t } from '../lib/copy'
import type { Chip, EnemySummary, UnitSummary } from '../lib/types'
import { targetLabel } from './targets'

type OrderChipsProps = Readonly<{
  chips: readonly Chip[]
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
  const name = unit && unit.power_name_tl !== '' ? unit.power_name_tl : t('card.power').tl
  return { tl: name, en: name }
}

function OrderChips({
  chips,
  units,
  enemies,
  interactive,
  onCancel
}: OrderChipsProps): React.JSX.Element {
  return (
    <section
      aria-label={t('hud.orders').en}
      className="flex min-w-0 flex-1 flex-wrap items-center gap-3"
    >
      {chips.length === 0 && <p className="caption-en">{t('hud.no_orders').tl}</p>}
      {chips.map((chip) => {
        const unit = units.find((candidate) => candidate.id === chip.unit_id)
        const unitName = unit ? unit.name : chip.unit_id
        const action = actionWord(chip, unit)
        const params: Record<string, string> = { unit: unitName, action: action.tl }
        if (chip.target_id !== null) {
          params.target = targetLabel(chip.target_id, units, enemies)
        }
        const text = t(chip.target_id === null ? 'chip.self' : 'chip.text', params)
        return (
          <div
            key={chip.chip_id}
            className="flex items-center border-2 border-gabi-ink bg-gabi-dusk"
          >
            <span className="px-3">{text.tl}</span>
            <button
              type="button"
              className="btn h-[48px] w-[48px] px-0"
              aria-label={`${t('hud.chip_cancel').en}: ${text.en}`}
              title={t('hud.chip_cancel').tl}
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

import Bilingual from '../components/Bilingual'
import { t } from '../lib/copy'
import type { IntentAction, NightUnit, UnitSummary } from '../lib/types'
import { actionTarget, powerTarget } from './targets'

type TapMenuProps = Readonly<{
  unit: UnitSummary
  night: NightUnit
  pending: IntentAction | null
  onPick: (action: IntentAction) => void
  onCancel: () => void
}>

function TapMenu({ unit, night, pending, onPick, onCancel }: TapMenuProps): React.JSX.Element {
  const canAttack = unit.class !== 'kubo' && unit.atk > 0
  const isHeal = unit.power_id === 'P01'
  const hasPower = !isHeal && unit.power_id !== 'none' && powerTarget(unit.power_id) !== 'passive'
  const onCooldown = night.cooldown > 0
  const target = pending === null ? null : actionTarget(pending, unit.power_id)

  return (
    <div className="panel flex flex-col gap-3 p-4" role="group" aria-label={unit.name}>
      {pending === null ? (
        <p>{t('tap.pick_action', { unit: unit.name }).tl}</p>
      ) : (
        target !== 'none' && <Bilingual copyKey="tap.pick_target" params={{ unit: unit.name }} />
      )}
      <div className="flex flex-wrap gap-3">
        {pending === null && (
          <>
            <button
              type="button"
              className="btn"
              disabled={!canAttack}
              onClick={() => onPick('attack')}
            >
              {t('tap.attack').tl}
            </button>
            {hasPower && (
              <button
                type="button"
                className="btn"
                disabled={onCooldown}
                onClick={() => onPick('power')}
              >
                {unit.power_name_tl}
              </button>
            )}
            {isHeal && (
              <button
                type="button"
                className="btn"
                disabled={onCooldown}
                onClick={() => onPick('heal')}
              >
                {t('tap.heal').tl}
              </button>
            )}
          </>
        )}
        <button type="button" className="btn" onClick={onCancel}>
          {t('tap.cancel').tl}
        </button>
      </div>
      {!canAttack && pending === null && unit.class !== 'kubo' && (
        <p className="caption-en">{t('cmd.no_atk', { unit: unit.name }).tl}</p>
      )}
    </div>
  )
}

export default TapMenu

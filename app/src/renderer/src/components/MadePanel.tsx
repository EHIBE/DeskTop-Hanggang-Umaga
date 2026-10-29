import SpriteView from '../canvas/SpriteView'
import { t, type CopyKey } from '../lib/copy'
import type { SummonSource, UnitSummary } from '../lib/types'

type MadePanelProps = Readonly<{
  unit: UnitSummary
  source: SummonSource
  visible: boolean
}>

type StepProps = Readonly<{
  index: number
  nameKey: CopyKey
  stepKey: CopyKey
  dim?: boolean
  children?: React.ReactNode
}>

const SPRITE_SCALE = 4

function Step({ index, nameKey, stepKey, dim = false, children }: StepProps): React.JSX.Element {
  return (
    <li className={`panel flex min-w-0 flex-1 flex-col gap-3 p-4 ${dim ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-gabi-lantern text-gabi-lantern">
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[24px] leading-[32px] text-gabi-lantern">{t(nameKey).tl}</p>
          <p className="caption-tl">{t(stepKey).tl}</p>
          <p className="caption-en">{t(stepKey).en}</p>
        </div>
      </div>
      {children}
    </li>
  )
}

function MadePanel({ unit, source, visible }: MadePanelProps): React.JSX.Element {
  const fallback = source === 'fallback'
  const drawn = unit.sprite_png !== null && unit.sprite_png !== ''
  const size = 48 * SPRITE_SCALE
  return (
    <section
      aria-label={t('made.title').en}
      aria-hidden={!visible}
      className={`absolute bottom-8 left-[576px] right-8 z-30 transition-[opacity,visibility] duration-500 motion-reduce:transition-none ${
        visible ? 'opacity-100' : 'invisible opacity-0'
      }`}
    >
      <ol className="flex gap-4">
        <Step
          index={1}
          nameKey={fallback ? 'made.fallback_name' : 'model.spark'}
          stepKey={fallback ? 'made.fallback_step' : 'made.spark_step'}
          dim={fallback}
        />
        <Step index={2} nameKey="model.sam" stepKey="made.sam_step" />
        <Step index={3} nameKey="model.image" stepKey="made.image_step">
          {drawn ? (
            <div
              className="shrink-0 border-2 border-gabi-ink bg-gabi-dusk"
              style={{ width: size, height: size }}
            >
              <SpriteView unit={unit} scale={SPRITE_SCALE} fallback={null} />
            </div>
          ) : (
            <div
              role="status"
              className="flex shrink-0 items-center justify-center border-2 border-dashed border-gabi-lantern bg-gabi-dusk text-center text-gabi-lantern"
              style={{ width: size, height: size }}
            >
              {t('made.drawing').tl}
            </div>
          )}
        </Step>
      </ol>
    </section>
  )
}

export default MadePanel

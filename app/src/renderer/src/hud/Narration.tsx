import { currentLang } from '../lib/lang'
import { pick, say, t } from '../lib/copy'
import type { NarrationMessage } from '../lib/types'
import { MOOD_BORDER, MOOD_KEY, MOOD_TEXT } from './mood'

type NarrationProps = Readonly<{
  narration: NarrationMessage | null
  className?: string
}>

function Narration({ narration, className = '' }: NarrationProps): React.JSX.Element | null {
  if (narration === null) return null
  const mood = t(MOOD_KEY[narration.mood])
  const hint = t('narration.hint')
  const hasHint = narration.hint_tl.trim() !== ''

  return (
    <section
      role="status"
      aria-live="polite"
      aria-label={narration.narration_en}
      className={`flex shrink-0 items-start gap-6 border-2 bg-gabi-night px-6 py-2 ${MOOD_BORDER[narration.mood]} ${className}`}
    >
      <span
        className={`w-[128px] shrink-0 border-2 px-2 text-center ${MOOD_BORDER[narration.mood]} ${MOOD_TEXT[narration.mood]}`}
        title={pick(mood)}
      >
        {pick(mood)}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="caption-tl text-[24px] leading-[32px]">
          {currentLang() === 'en' ? narration.narration_en : narration.narration_tl}
        </p>
        {narration.source === 'spark' && (
          <span className="text-gabi-mist leading-[24px]">{say('model.spark')}</span>
        )}
        {hasHint && (
          <p className="text-gabi-lantern leading-[24px]">
            {pick(hint)}: {narration.hint_tl}
          </p>
        )}
      </div>
      {narration.callouts.length > 0 && (
        <ul className="flex w-[360px] shrink-0 flex-col gap-1">
          {narration.callouts.map((callout, index) => (
            <li key={`${callout.entity_id}:${index}`} className="panel px-2 leading-[24px]">
              {callout.text_tl}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default Narration

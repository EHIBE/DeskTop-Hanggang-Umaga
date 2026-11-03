import { currentLang } from '../lib/lang'
import { pick, t } from '../lib/copy'
import type { MomentMessage } from '../lib/types'
import { MOOD_BORDER, MOOD_KEY, MOOD_TEXT } from './mood'

type MomentLineProps = Readonly<{
  moment: MomentMessage | null
  className?: string
}>

function MomentLine({ moment, className = '' }: MomentLineProps): React.JSX.Element | null {
  if (moment === null) return null
  const mood = t(MOOD_KEY[moment.mood])

  return (
    <section
      role="status"
      aria-live="polite"
      aria-label={moment.text_en}
      className={`flex items-start gap-4 border-2 bg-gabi-night px-4 py-2 ${MOOD_BORDER[moment.mood]} ${className}`}
    >
      <span
        className={`w-[128px] shrink-0 border-2 px-2 text-center ${MOOD_BORDER[moment.mood]} ${MOOD_TEXT[moment.mood]}`}
      >
        {pick(mood)}
      </span>
      <p className="caption-tl min-w-0 flex-1 text-[24px] leading-[32px]">
        {currentLang() === 'en' ? moment.text_en : moment.text_tl}
      </p>
    </section>
  )
}

export default MomentLine

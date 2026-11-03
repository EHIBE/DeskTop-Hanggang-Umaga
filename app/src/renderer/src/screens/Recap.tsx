import Dialog from '../components/Dialog'
import PixelIcon from '../components/PixelIcon'
import { MOOD_BORDER, MOOD_TEXT } from '../hud/mood'
import { currentLang } from '../lib/lang'
import { say } from '../lib/copy'
import type { RecapPayload } from '../lib/types'

type RecapProps = Readonly<{
  recap: RecapPayload
  onContinue: () => void
}>

const TITLE_ID = 'recap-title'

function sourceLabel(source: RecapPayload['source']): string | null {
  if (source === 'glimmer') return say('model.glimmer')
  if (source === 'spark') return say('model.spark')
  return null
}

function Recap({ recap, onContinue }: RecapProps): React.JSX.Element {
  const tag = sourceLabel(recap.source)

  return (
    <Dialog
      titleId={TITLE_ID}
      onEscape={onContinue}
      className="flex w-[1100px] flex-col gap-8 p-12"
    >
      <div className="flex items-baseline justify-between gap-6">
        <h2 id={TITLE_ID} className="title-mark text-[56px] leading-[64px]">
          {say('recap.title')}
        </h2>
        <span className="text-gabi-mist">{say('recap.night', { n: recap.night })}</span>
      </div>
      <p
        role="status"
        className={`caption-tl border-l-4 pl-6 text-[24px] leading-[40px] ${MOOD_BORDER[recap.mood]} ${MOOD_TEXT[recap.mood]}`}
      >
        <span className="text-gabi-moon">
          {currentLang() === 'en' ? recap.text_en : recap.text_tl}
        </span>
      </p>
      <div className="flex items-center justify-between gap-6">
        <span className="text-gabi-mist">{tag}</span>
        <button type="button" className="btn btn-primary btn-big text-[24px]" onClick={onContinue}>
          <PixelIcon name="play" size={4} />
          {say('recap.continue')}
        </button>
      </div>
    </Dialog>
  )
}

export default Recap

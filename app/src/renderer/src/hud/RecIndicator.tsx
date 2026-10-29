import { t } from '../lib/copy'

function RecIndicator(): React.JSX.Element {
  const text = t('rec.on')
  return (
    <span role="status" aria-label={text.en} className="flex items-center gap-2 text-[16px]">
      <span className="rec-dot" aria-hidden="true" />
      <span aria-hidden="true">REC</span>
      <span>{text.tl}</span>
    </span>
  )
}

export default RecIndicator

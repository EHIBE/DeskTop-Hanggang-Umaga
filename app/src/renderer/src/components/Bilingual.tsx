import { t, type CopyKey } from '../lib/copy'
import type { CopyParams } from '../lib/types'

type BilingualProps = Readonly<{
  copyKey: CopyKey
  params?: CopyParams
  className?: string
}>

function Bilingual({ copyKey, params, className }: BilingualProps): React.JSX.Element {
  const text = t(copyKey, params)
  return (
    <div className={className}>
      <p className="caption-tl">{text.tl}</p>
      {text.en !== text.tl && <p className="caption-en">{text.en}</p>}
    </div>
  )
}

export default Bilingual

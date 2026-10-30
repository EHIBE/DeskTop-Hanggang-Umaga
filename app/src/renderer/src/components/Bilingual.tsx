import { say, type CopyKey } from '../lib/copy'
import type { CopyParams } from '../lib/types'

type BilingualProps = Readonly<{
  copyKey: CopyKey
  params?: CopyParams
  className?: string
}>

function Bilingual({ copyKey, params, className }: BilingualProps): React.JSX.Element {
  return (
    <div className={className}>
      <p className="caption-tl">{say(copyKey, params)}</p>
    </div>
  )
}

export default Bilingual

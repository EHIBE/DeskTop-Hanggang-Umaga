import { palette } from '../lib/palette'
import type { StatusEntry } from './status'

type StatusBadgeProps = Readonly<{ entry: StatusEntry }>

const COLORS = { out: palette.ember, stolen: palette.sindak, lost: palette.mist } as const

function Shape({ kind }: Readonly<{ kind: StatusEntry['kind'] }>): React.JSX.Element {
  const color = COLORS[kind]
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
      {kind === 'out' && <polygon points="1,2 15,2 8,15" fill={color} />}
      {kind === 'stolen' && (
        <path d="M2 2L14 14M14 2L2 14" stroke={color} strokeWidth="3" fill="none" />
      )}
      {kind === 'lost' && (
        <>
          <circle cx="8" cy="8" r="6" stroke={color} strokeWidth="2" fill="none" />
          <path d="M3 13L13 3" stroke={color} strokeWidth="2" />
        </>
      )}
    </svg>
  )
}

function StatusBadge({ entry }: StatusBadgeProps): React.JSX.Element {
  return (
    <span className="inline-flex items-center gap-1">
      <Shape kind={entry.kind} />
      <span>{entry.text}</span>
    </span>
  )
}

export default StatusBadge

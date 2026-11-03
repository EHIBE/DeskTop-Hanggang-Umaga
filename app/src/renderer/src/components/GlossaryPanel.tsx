import { useEffect, useRef } from 'react'
import { say, type CopyKey } from '../lib/copy'
import PixelIcon from './PixelIcon'

type GlossaryTerm = Readonly<{ name: CopyKey; text: CopyKey }>

type GlossaryPanelProps = Readonly<{ onClose: () => void }>

const TITLE_ID = 'glossary-title'

const TERMS: readonly GlossaryTerm[] = [
  { name: 'gloss.name_aswang', text: 'gloss.aswang' },
  { name: 'gloss.name_tikbalang', text: 'gloss.tikbalang' },
  { name: 'gloss.name_kapre', text: 'gloss.kapre' },
  { name: 'gloss.name_manananggal', text: 'gloss.manananggal' },
  { name: 'gloss.name_duwende', text: 'gloss.duwende' },
  { name: 'gloss.name_usok', text: 'gloss.usok' },
  { name: 'gloss.name_liwanag', text: 'gloss.liwanag' },
  { name: 'gloss.name_albularyo', text: 'gloss.albularyo' },
  { name: 'gloss.name_anting', text: 'gloss.anting' },
  { name: 'gloss.name_kubo', text: 'gloss.kubo' }
]

function focusables(root: HTMLElement): readonly HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>('[tabindex="0"], button:not(:disabled)'))
}

function trapTab(event: React.KeyboardEvent<HTMLElement>): void {
  const items = focusables(event.currentTarget)
  if (items.length === 0) return
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || !event.currentTarget.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (active === last || !event.currentTarget.contains(active))) {
    event.preventDefault()
    first.focus()
  }
}

function GlossaryPanel({ onClose }: GlossaryPanelProps): React.JSX.Element {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const opener = document.activeElement
    const dialog = dialogRef.current
    if (dialog) focusables(dialog)[0]?.focus()
    return () => {
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>): void => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onClose()
    } else if (event.key === 'Tab') {
      trapTab(event)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gabi-ink/80">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={TITLE_ID}
        tabIndex={-1}
        className="window flex max-h-[800px] w-[960px] flex-col gap-6 p-8"
        onKeyDown={onKeyDown}
      >
        <h2 id={TITLE_ID} className="label">
          {say('gloss.title')}
        </h2>
        <ul className="-mx-4 flex min-h-0 flex-col overflow-y-auto px-4">
          {TERMS.map((term) => (
            <li key={term.name} tabIndex={0} className="menu-row glossary-row">
              <span className="text-[24px] leading-[32px] text-gabi-lantern">{say(term.name)}</span>
              <span className="text-gabi-moon">{say(term.text)}</span>
            </li>
          ))}
        </ul>
        <button type="button" className="btn shrink-0 self-end" onClick={onClose}>
          <PixelIcon name="cross" size={3} />
          {say('gloss.close')}
        </button>
      </div>
    </div>
  )
}

export default GlossaryPanel

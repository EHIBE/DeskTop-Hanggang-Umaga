import { useEffect, useRef } from 'react'

type DialogProps = Readonly<{
  titleId: string
  onEscape: () => void
  className?: string
  children: React.ReactNode
}>

const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), [tabindex="0"]'

function focusables(root: HTMLElement): readonly HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
}

function trapTab(event: React.KeyboardEvent<HTMLElement>): void {
  const items = focusables(event.currentTarget)
  if (items.length === 0) {
    event.preventDefault()
    return
  }
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

function Dialog({ titleId, onEscape, className = '', children }: DialogProps): React.JSX.Element {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const opener = document.activeElement
    const dialog = dialogRef.current
    if (dialog) {
      const preferred = dialog.querySelector<HTMLElement>('[data-autofocus]')
      ;(preferred ?? focusables(dialog)[0])?.focus()
    }
    return () => {
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>): void => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onEscape()
    } else if (event.key === 'Tab') {
      trapTab(event)
    }
  }

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-gabi-ink/80">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`window ${className}`}
        onKeyDown={onKeyDown}
      >
        {children}
      </div>
    </div>
  )
}

export default Dialog

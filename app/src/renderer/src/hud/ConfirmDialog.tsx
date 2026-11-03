import { useEffect, useState } from 'react'
import Dialog from '../components/Dialog'
import { currentLang } from '../lib/lang'
import { say } from '../lib/copy'
import type { PendingConfirm } from '../lib/types'

type ConfirmDialogProps = Readonly<{
  confirm: PendingConfirm
  onAccept: (confirmId: string) => void
  onCancel: (confirmId: string) => void
}>

const TITLE_ID = 'confirm-title'

function ConfirmDialog({ confirm, onAccept, onCancel }: ConfirmDialogProps): React.JSX.Element {
  const confirmId = confirm.confirm_id
  const [deadline] = useState(() => Date.now() + confirm.seconds_left * 1000)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [])

  const seconds = Math.max(0, Math.ceil((deadline - now) / 1000))

  return (
    <Dialog
      titleId={TITLE_ID}
      onEscape={() => onCancel(confirmId)}
      className="flex w-[880px] flex-col gap-6 p-10"
    >
      <h2 id={TITLE_ID} className="text-[24px] leading-[32px] text-gabi-lantern">
        {say('confirm.title')}
      </h2>
      <p className="caption-tl text-[24px] leading-[40px]">
        {currentLang() === 'en' ? confirm.text_en : confirm.text_tl}
      </p>
      <p role="timer" className={seconds <= 5 ? 'text-gabi-lantern' : 'caption-en'}>
        {seconds <= 5 ? '! ' : ''}
        {say('confirm.seconds', { seconds })}
      </p>
      <div className="flex justify-end gap-4">
        <button
          type="button"
          className="btn btn-big"
          data-autofocus
          onClick={() => onCancel(confirmId)}
        >
          {say('confirm.no')}
        </button>
        <button
          type="button"
          className="btn btn-primary btn-big"
          onClick={() => onAccept(confirmId)}
        >
          {say('confirm.yes')}
        </button>
      </div>
    </Dialog>
  )
}

export default ConfirmDialog

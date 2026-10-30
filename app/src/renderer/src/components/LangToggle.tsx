import { say } from '../lib/copy'
import { currentLang, setLang, type Lang } from '../lib/lang'

const OPTIONS: readonly Readonly<{ lang: Lang; label: string }>[] = [
  { lang: 'tl', label: 'FIL' },
  { lang: 'en', label: 'ENG' }
]

function LangToggle({ className = '' }: Readonly<{ className?: string }>): React.JSX.Element {
  const active = currentLang()
  return (
    <div role="radiogroup" aria-label={say('lang.title')} className={`lang-toggle ${className}`}>
      {OPTIONS.map((option) => (
        <button
          key={option.lang}
          type="button"
          role="radio"
          aria-checked={option.lang === active}
          aria-label={say(option.lang === 'tl' ? 'lang.tl' : 'lang.en')}
          onClick={() => setLang(option.lang)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default LangToggle

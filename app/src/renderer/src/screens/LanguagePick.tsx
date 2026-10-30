import NightScene from '../components/NightScene'
import TitleMark from '../components/TitleMark'
import { setLang, type Lang } from '../lib/lang'

const CHOICES: readonly Readonly<{ lang: Lang; label: string; hint: string }>[] = [
  { lang: 'tl', label: 'Filipino', hint: 'Tara, laro!' },
  { lang: 'en', label: 'English', hint: "Let's play!" }
]

function LanguagePick(): React.JSX.Element {
  return (
    <main className="relative h-full w-full">
      <NightScene />
      <div className="relative flex h-full flex-col justify-center gap-24 pl-[160px]">
        <div className="rise-in">
          <TitleMark />
        </div>
        <section className="rise-in flex flex-col gap-8" style={{ animationDelay: '160ms' }}>
          <p className="text-[24px] leading-[32px] text-gabi-mist">Wika / Language</p>
          <div className="flex gap-8">
            {CHOICES.map((choice, index) => (
              <button
                key={choice.lang}
                type="button"
                autoFocus={index === 0}
                className="btn btn-big w-[400px] flex-col items-start gap-3"
                onClick={() => setLang(choice.lang)}
              >
                <span className="text-[32px] leading-[40px]">{choice.label}</span>
                <span className="text-[16px] text-gabi-mist">{choice.hint}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}

export default LanguagePick

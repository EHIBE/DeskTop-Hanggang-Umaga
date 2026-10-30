import { say } from '../lib/copy'

function TitleMark({ size = 'large' }: Readonly<{ size?: 'large' | 'small' }>): React.JSX.Element {
  const large = size === 'large'
  return (
    <div className="flex flex-col gap-4">
      <h1
        className={`title-mark ${large ? 'text-[88px] leading-[88px]' : 'text-[48px] leading-[48px]'}`}
      >
        DeskTop
      </h1>
      <p
        className={`title-sub ${large ? 'text-[32px] leading-[40px]' : 'text-[16px] leading-[24px]'}`}
      >
        {say('title.sub')}
      </p>
    </div>
  )
}

export default TitleMark

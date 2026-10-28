import { useEffect, useState } from 'react'

const STAGE_W = 1920
const STAGE_H = 1080

function fitScale(): number {
  return Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H)
}

function Stage({ children }: Readonly<{ children: React.ReactNode }>): React.JSX.Element {
  const [scale, setScale] = useState(fitScale)

  useEffect(() => {
    const onResize = (): void => setScale(fitScale())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <div className="fixed inset-0 overflow-hidden bg-gabi-ink">
      <div
        className="absolute overflow-hidden bg-gabi-ink"
        style={{
          width: STAGE_W,
          height: STAGE_H,
          left: '50%',
          top: '50%',
          transform: `translate(-50%, -50%) scale(${scale})`
        }}
      >
        {children}
      </div>
    </div>
  )
}

export default Stage

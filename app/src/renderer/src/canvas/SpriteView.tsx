import { useEffect, useRef, useState } from 'react'
import { MIN_SCALE, SPRITE_SIZE, drawSprite, loadUnitImage } from './sprites'
import type { UnitSummary } from '../lib/types'

type SpriteViewProps = Readonly<{
  unit: UnitSummary
  scale?: number
  fallback: React.ReactNode
}>

function SpriteView({ unit, scale = MIN_SCALE, fallback }: SpriteViewProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [drawn, setDrawn] = useState(false)
  const size = SPRITE_SIZE * scale

  useEffect(() => {
    let active = true
    void loadUnitImage(unit).then((bitmap) => {
      const ctx = canvasRef.current?.getContext('2d')
      if (!active || !ctx) return
      ctx.clearRect(0, 0, size, size)
      if (bitmap) drawSprite(ctx, bitmap, size / 2, size / 2, scale)
      setDrawn(bitmap !== null)
    })
    return () => {
      active = false
    }
  }, [unit, scale, size])

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} aria-hidden="true">
      {!drawn && (
        <div className="absolute inset-0 flex items-center justify-center">{fallback}</div>
      )}
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        className="absolute inset-0"
        style={{ imageRendering: 'pixelated' }}
      />
    </div>
  )
}

export default SpriteView

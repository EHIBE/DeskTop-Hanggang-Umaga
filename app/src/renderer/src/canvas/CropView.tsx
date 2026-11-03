import { useEffect, useRef } from 'react'
import { useBitmap } from './sprites'

type CropViewProps = Readonly<{ png: string; size: number }>

function CropView({ png, size }: CropViewProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const bitmap = useBitmap(png)

  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, size, size)
    if (!bitmap) return
    const fit = size / Math.max(bitmap.width, bitmap.height)
    const factor = fit >= 1 ? Math.floor(fit) : fit
    const width = Math.round(bitmap.width * factor)
    const height = Math.round(bitmap.height * factor)
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(
      bitmap,
      Math.round((size - width) / 2),
      Math.round((size - height) / 2),
      width,
      height
    )
  }, [bitmap, size])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className="absolute inset-0"
      style={{ imageRendering: 'pixelated' }}
    />
  )
}

export default CropView

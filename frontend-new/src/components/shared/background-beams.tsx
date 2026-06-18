import { useEffect, useRef } from "react"

export function BackgroundBeams() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let animationId: number
    let time = 0

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }

    interface Beam {
      x: number
      y: number
      length: number
      speed: number
      angle: number
      width: number
      opacity: number
      color: string
    }

    const beams: Beam[] = Array.from({ length: 8 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      length: Math.random() * 200 + 100,
      speed: Math.random() * 2 + 1,
      angle: Math.random() * Math.PI * 2,
      width: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.15 + 0.05,
      color: ["#3b82f6", "#06b6d4", "#a855f7"][Math.floor(Math.random() * 3)],
    }))

    const drawBeams = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      beams.forEach((beam) => {
        const endX = beam.x + Math.cos(beam.angle) * beam.length
        const endY = beam.y + Math.sin(beam.angle) * beam.length

        const gradient = ctx.createLinearGradient(beam.x, beam.y, endX, endY)
        gradient.addColorStop(0, "transparent")
        gradient.addColorStop(0.5, beam.color + Math.floor(beam.opacity * 255).toString(16).padStart(2, "0"))
        gradient.addColorStop(1, "transparent")

        ctx.beginPath()
        ctx.moveTo(beam.x, beam.y)
        ctx.lineTo(endX, endY)
        ctx.strokeStyle = gradient
        ctx.lineWidth = beam.width
        ctx.lineCap = "round"
        ctx.stroke()

        // Glow effect
        ctx.shadowColor = beam.color
        ctx.shadowBlur = 10
        ctx.stroke()
        ctx.shadowBlur = 0

        // Move beam
        beam.x += Math.cos(beam.angle) * beam.speed
        beam.y += Math.sin(beam.angle) * beam.speed

        // Wrap around
        if (beam.x < -beam.length) beam.x = canvas.width + beam.length
        if (beam.x > canvas.width + beam.length) beam.x = -beam.length
        if (beam.y < -beam.length) beam.y = canvas.height + beam.length
        if (beam.y > canvas.height + beam.length) beam.y = -beam.length
      })
    }

    const animate = () => {
      time++
      drawBeams()
      animationId = requestAnimationFrame(animate)
    }

    resize()
    animate()

    window.addEventListener("resize", resize)

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener("resize", resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.6 }}
    />
  )
}

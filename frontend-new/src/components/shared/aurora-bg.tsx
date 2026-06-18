import { useEffect, useRef } from "react"

export function AuroraBg() {
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

    const drawAurora = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const layers = [
        {
          color1: "rgba(59, 130, 246, 0.08)",
          color2: "rgba(6, 182, 212, 0.04)",
          speed: 0.0005,
          amplitude: 100,
          frequency: 0.002,
        },
        {
          color1: "rgba(168, 85, 247, 0.06)",
          color2: "rgba(59, 130, 246, 0.03)",
          speed: 0.0003,
          amplitude: 80,
          frequency: 0.003,
        },
        {
          color1: "rgba(6, 182, 212, 0.05)",
          color2: "rgba(34, 197, 94, 0.02)",
          speed: 0.0004,
          amplitude: 120,
          frequency: 0.0015,
        },
      ]

      layers.forEach((layer) => {
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
        gradient.addColorStop(0, layer.color1)
        gradient.addColorStop(0.5, layer.color2)
        gradient.addColorStop(1, layer.color1)

        ctx.beginPath()
        ctx.moveTo(0, canvas.height * 0.3)

        for (let x = 0; x <= canvas.width; x += 5) {
          const y =
            canvas.height * 0.3 +
            Math.sin(x * layer.frequency + time * layer.speed) * layer.amplitude +
            Math.sin(x * layer.frequency * 2 + time * layer.speed * 1.5) * (layer.amplitude * 0.5)
          ctx.lineTo(x, y)
        }

        ctx.lineTo(canvas.width, canvas.height)
        ctx.lineTo(0, canvas.height)
        ctx.closePath()

        ctx.fillStyle = gradient
        ctx.fill()
      })
    }

    const animate = () => {
      time++
      drawAurora()
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
    />
  )
}

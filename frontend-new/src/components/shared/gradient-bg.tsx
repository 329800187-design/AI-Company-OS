import { useEffect, useRef } from "react"

export function GradientBg() {
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

    const drawGradient = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Multiple gradient orbs
      const orbs = [
        {
          x: canvas.width * 0.3 + Math.sin(time * 0.001) * 100,
          y: canvas.height * 0.3 + Math.cos(time * 0.0015) * 80,
          radius: 300,
          color: "rgba(59, 130, 246, 0.08)",
        },
        {
          x: canvas.width * 0.7 + Math.cos(time * 0.0012) * 120,
          y: canvas.height * 0.6 + Math.sin(time * 0.001) * 100,
          radius: 250,
          color: "rgba(6, 182, 212, 0.06)",
        },
        {
          x: canvas.width * 0.5 + Math.sin(time * 0.0008) * 80,
          y: canvas.height * 0.8 + Math.cos(time * 0.0013) * 60,
          radius: 200,
          color: "rgba(168, 85, 247, 0.05)",
        },
      ]

      orbs.forEach((orb) => {
        const gradient = ctx.createRadialGradient(
          orb.x,
          orb.y,
          0,
          orb.x,
          orb.y,
          orb.radius
        )
        gradient.addColorStop(0, orb.color)
        gradient.addColorStop(1, "transparent")

        ctx.fillStyle = gradient
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      })
    }

    const animate = () => {
      time++
      drawGradient()
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

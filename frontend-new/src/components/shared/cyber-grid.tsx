import { useEffect, useRef } from "react"

export function CyberGrid() {
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

    const drawGrid = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const gridSize = 40
      const opacity = 0.03 + Math.sin(time * 0.001) * 0.01

      // Vertical lines
      for (let x = 0; x < canvas.width; x += gridSize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, canvas.height)
        ctx.strokeStyle = `rgba(59, 130, 246, ${opacity})`
        ctx.lineWidth = 0.5
        ctx.stroke()
      }

      // Horizontal lines
      for (let y = 0; y < canvas.height; y += gridSize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(canvas.width, y)
        ctx.strokeStyle = `rgba(59, 130, 246, ${opacity})`
        ctx.lineWidth = 0.5
        ctx.stroke()
      }

      // Scan line effect
      const scanY = (time * 0.5) % canvas.height
      const gradient = ctx.createLinearGradient(0, scanY - 100, 0, scanY + 100)
      gradient.addColorStop(0, "rgba(59, 130, 246, 0)")
      gradient.addColorStop(0.5, "rgba(59, 130, 246, 0.05)")
      gradient.addColorStop(1, "rgba(59, 130, 246, 0)")

      ctx.fillStyle = gradient
      ctx.fillRect(0, scanY - 100, canvas.width, 200)
    }

    const animate = () => {
      time++
      drawGrid()
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
      style={{ opacity: 0.8 }}
    />
  )
}

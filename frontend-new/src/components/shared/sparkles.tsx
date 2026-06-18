import { useEffect, useState, useRef } from "react"
import { motion } from "framer-motion"

interface Sparkle {
  id: number
  x: number
  y: number
  size: number
  color: string
  delay: number
}

interface SparklesProps {
  children: React.ReactNode
  className?: string
  count?: number
  color?: "blue" | "cyan" | "purple" | "mixed"
}

export function Sparkles({
  children,
  className,
  count = 20,
  color = "mixed",
}: SparklesProps) {
  const [sparkles, setSparkles] = useState<Sparkle[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  const colors = {
    blue: ["#3b82f6", "#60a5fa", "#93c5fd"],
    cyan: ["#06b6d4", "#22d3ee", "#67e8f9"],
    purple: ["#a855f7", "#c084fc", "#d8b4fe"],
    mixed: ["#3b82f6", "#06b6d4", "#a855f7", "#22c55e"],
  }

  useEffect(() => {
    const generateSparkle = (): Sparkle => ({
      id: Math.random(),
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 4 + 2,
      color: colors[color][Math.floor(Math.random() * colors[color].length)],
      delay: Math.random() * 2,
    })

    setSparkles(Array.from({ length: count }, generateSparkle))

    const interval = setInterval(() => {
      setSparkles((prev) => {
        const newSparkles = [...prev]
        const indexToReplace = Math.floor(Math.random() * newSparkles.length)
        newSparkles[indexToReplace] = generateSparkle()
        return newSparkles
      })
    }, 300)

    return () => clearInterval(interval)
  }, [count, color])

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      {sparkles.map((sparkle) => (
        <motion.div
          key={sparkle.id}
          initial={{ opacity: 0, scale: 0 }}
          animate={{
            opacity: [0, 1, 0],
            scale: [0, 1, 0],
            rotate: [0, 180],
          }}
          transition={{
            duration: 1.5,
            delay: sparkle.delay,
            repeat: Infinity,
            repeatDelay: Math.random() * 2,
          }}
          className="absolute pointer-events-none"
          style={{
            left: `${sparkle.x}%`,
            top: `${sparkle.y}%`,
            width: sparkle.size,
            height: sparkle.size,
          }}
        >
          <svg
            width={sparkle.size}
            height={sparkle.size}
            viewBox="0 0 20 20"
            fill="none"
          >
            <path
              d="M10 0L12.2451 7.75492L20 10L12.2451 12.2451L10 20L7.75492 12.2451L0 10L7.75492 7.75492L10 0Z"
              fill={sparkle.color}
            />
          </svg>
          <div
            className="absolute inset-0"
            style={{
              background: `radial-gradient(circle, ${sparkle.color}80, transparent)`,
              filter: "blur(2px)",
            }}
          />
        </motion.div>
      ))}
      {children}
    </div>
  )
}

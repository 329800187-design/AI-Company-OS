import { useState, useRef } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface GlareCardProps {
  children: React.ReactNode
  className?: string
  glareColor?: "blue" | "cyan" | "purple" | "white"
  onClick?: () => void
}

export function GlareCard({
  children,
  className,
  glareColor = "white",
  onClick,
}: GlareCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [glarePosition, setGlarePosition] = useState({ x: 50, y: 50 })
  const [isHovered, setIsHovered] = useState(false)

  const glareColors = {
    blue: "rgba(59, 130, 246, 0.3)",
    cyan: "rgba(6, 182, 212, 0.3)",
    purple: "rgba(168, 85, 247, 0.3)",
    white: "rgba(255, 255, 255, 0.2)",
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return

    const rect = ref.current.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100

    setGlarePosition({ x, y })
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
      whileHover={{ scale: 1.01 }}
      whileTap={onClick ? { scale: 0.99 } : undefined}
      className={cn(
        "relative rounded-xl border border-border bg-card overflow-hidden transition-all duration-300",
        onClick && "cursor-pointer",
        className
      )}
    >
      {/* Glare effect */}
      {isHovered && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(circle at ${glarePosition.x}% ${glarePosition.y}%, ${glareColors[glareColor]}, transparent 60%)`,
          }}
        />
      )}

      {/* Border glow on hover */}
      {isHovered && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 pointer-events-none rounded-xl"
          style={{
            boxShadow:
              glareColor === "blue"
                ? "0 0 20px rgba(59, 130, 246, 0.2), inset 0 0 20px rgba(59, 130, 246, 0.1)"
                : glareColor === "cyan"
                ? "0 0 20px rgba(6, 182, 212, 0.2), inset 0 0 20px rgba(6, 182, 212, 0.1)"
                : glareColor === "purple"
                ? "0 0 20px rgba(168, 85, 247, 0.2), inset 0 0 20px rgba(168, 85, 247, 0.1)"
                : "0 0 20px rgba(255, 255, 255, 0.1), inset 0 0 20px rgba(255, 255, 255, 0.05)",
          }}
        />
      )}

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </motion.div>
  )
}

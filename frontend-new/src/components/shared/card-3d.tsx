import { useState, useRef } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface Card3DProps {
  children: React.ReactNode
  className?: string
  glowColor?: "blue" | "cyan" | "purple"
  onClick?: () => void
}

export function Card3D({
  children,
  className,
  glowColor = "blue",
  onClick,
}: Card3DProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [rotateX, setRotateX] = useState(0)
  const [rotateY, setRotateY] = useState(0)
  const [isHovered, setIsHovered] = useState(false)

  const glowColors = {
    blue: "rgba(59, 130, 246, 0.3)",
    cyan: "rgba(6, 182, 212, 0.3)",
    purple: "rgba(168, 85, 247, 0.3)",
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return

    const rect = ref.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    const mouseX = e.clientX - centerX
    const mouseY = e.clientY - centerY

    const rotateXValue = (mouseY / (rect.height / 2)) * -10
    const rotateYValue = (mouseX / (rect.width / 2)) * 10

    setRotateX(rotateXValue)
    setRotateY(rotateYValue)
  }

  const handleMouseLeave = () => {
    setRotateX(0)
    setRotateY(0)
    setIsHovered(false)
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      animate={{
        rotateX,
        rotateY,
        scale: isHovered ? 1.02 : 1,
      }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      style={{ perspective: 1000 }}
      className={cn(
        "relative rounded-xl border border-border bg-card p-6 transition-all duration-300",
        onClick && "cursor-pointer",
        className
      )}
    >
      {/* Glow effect */}
      {isHovered && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 rounded-xl"
          style={{
            boxShadow: `0 0 40px ${glowColors[glowColor]}, 0 0 80px ${glowColors[glowColor]}`,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Gradient border on hover */}
      {isHovered && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{
            background: `linear-gradient(135deg, ${glowColors[glowColor]}, transparent, ${glowColors[glowColor]})`,
            mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
            WebkitMaskComposite: "xor",
            maskComposite: "exclude",
            padding: "1px",
          }}
        />
      )}

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </motion.div>
  )
}

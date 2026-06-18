import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface NeonButtonProps {
  children: React.ReactNode
  className?: string
  color?: "blue" | "cyan" | "purple" | "green"
  onClick?: () => void
  disabled?: boolean
}

export function NeonButton({
  children,
  className,
  color = "blue",
  onClick,
  disabled = false,
}: NeonButtonProps) {
  const colors = {
    blue: {
      bg: "from-blue-500 to-cyan-500",
      glow: "rgba(59, 130, 246, 0.5)",
      border: "#3b82f6",
    },
    cyan: {
      bg: "from-cyan-500 to-teal-500",
      glow: "rgba(6, 182, 212, 0.5)",
      border: "#06b6d4",
    },
    purple: {
      bg: "from-purple-500 to-pink-500",
      glow: "rgba(168, 85, 247, 0.5)",
      border: "#a855f7",
    },
    green: {
      bg: "from-green-500 to-emerald-500",
      glow: "rgba(34, 197, 94, 0.5)",
      border: "#22c55e",
    },
  }

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "relative px-6 py-3 rounded-lg font-medium text-white overflow-hidden transition-all duration-300",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
      style={{
        boxShadow: `0 0 20px ${colors[color].glow}, 0 0 40px ${colors[color].glow}`,
      }}
    >
      {/* Background gradient */}
      <div className={cn("absolute inset-0 bg-gradient-to-r", colors[color].bg)} />

      {/* Animated border */}
      <div
        className="absolute inset-0 rounded-lg"
        style={{
          border: `1px solid ${colors[color].border}`,
          boxShadow: `inset 0 0 20px ${colors[color].glow}`,
        }}
      />

      {/* Shine effect */}
      <motion.div
        className="absolute inset-0"
        animate={{
          background: [
            "linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)",
            "linear-gradient(90deg, transparent, transparent, transparent)",
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{ transform: "translateX(-100%)" }}
      />

      {/* Content */}
      <span className="relative z-10 flex items-center justify-center gap-2">
        {children}
      </span>
    </motion.button>
  )
}

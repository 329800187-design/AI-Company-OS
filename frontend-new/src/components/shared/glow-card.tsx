import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface GlowCardProps {
  children: React.ReactNode
  className?: string
  glowColor?: "blue" | "cyan" | "purple"
  variant?: "default" | "glass"
  hover?: boolean
  onClick?: () => void
}

export function GlowCard({
  children,
  className,
  glowColor = "blue",
  variant = "default",
  hover = true,
  onClick,
}: GlowCardProps) {
  const glowColors = {
    blue: "hover:shadow-[0_0_30px_rgba(59,130,246,0.15),0_0_60px_rgba(59,130,246,0.05)]",
    cyan: "hover:shadow-[0_0_30px_rgba(6,182,212,0.15),0_0_60px_rgba(6,182,212,0.05)]",
    purple: "hover:shadow-[0_0_30px_rgba(168,85,247,0.15),0_0_60px_rgba(168,85,247,0.05)]",
  }

  const borderColors = {
    blue: "hover:border-primary/30",
    cyan: "hover:border-cyan/30",
    purple: "hover:border-purple/30",
  }

  return (
    <motion.div
      whileHover={hover ? { y: -2 } : undefined}
      whileTap={onClick ? { scale: 0.98 } : undefined}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className={cn(
        "rounded-xl border border-border p-6 transition-all duration-300",
        variant === "glass" ? "glass" : "bg-card",
        hover && glowColors[glowColor],
        hover && borderColors[glowColor],
        onClick && "cursor-pointer",
        className
      )}
    >
      {children}
    </motion.div>
  )
}

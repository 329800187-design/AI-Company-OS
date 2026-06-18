import { cn } from "@/lib/utils"

interface NeonTextProps {
  children: React.ReactNode
  className?: string
  color?: "blue" | "cyan" | "purple" | "green"
  intensity?: "low" | "medium" | "high"
  animate?: boolean
}

export function NeonText({
  children,
  className,
  color = "blue",
  intensity = "medium",
  animate = false,
}: NeonTextProps) {
  const colors = {
    blue: {
      text: "#3b82f6",
      glow: "rgba(59, 130, 246, 0.8)",
      glowWide: "rgba(59, 130, 246, 0.4)",
    },
    cyan: {
      text: "#06b6d4",
      glow: "rgba(6, 182, 212, 0.8)",
      glowWide: "rgba(6, 182, 212, 0.4)",
    },
    purple: {
      text: "#a855f7",
      glow: "rgba(168, 85, 247, 0.8)",
      glowWide: "rgba(168, 85, 247, 0.4)",
    },
    green: {
      text: "#22c55e",
      glow: "rgba(34, 197, 94, 0.8)",
      glowWide: "rgba(34, 197, 94, 0.4)",
    },
  }

  const intensityMap = {
    low: `0 0 5px ${colors[color].glow}, 0 0 10px ${colors[color].glowWide}`,
    medium: `0 0 10px ${colors[color].glow}, 0 0 20px ${colors[color].glowWide}, 0 0 40px ${colors[color].glowWide}`,
    high: `0 0 10px ${colors[color].glow}, 0 0 20px ${colors[color].glow}, 0 0 40px ${colors[color].glowWide}, 0 0 80px ${colors[color].glowWide}`,
  }

  return (
    <span
      className={cn(
        "font-bold",
        animate && "animate-pulse",
        className
      )}
      style={{
        color: colors[color].text,
        textShadow: intensityMap[intensity],
      }}
    >
      {children}
    </span>
  )
}

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface MovingBorderProps {
  children: React.ReactNode
  className?: string
  duration?: number
  rx?: string
  ry?: string
  color?: "blue" | "cyan" | "purple"
}

export function MovingBorder({
  children,
  className,
  duration = 2000,
  rx = "12px",
  ry = "12px",
  color = "blue",
}: MovingBorderProps) {
  const colors = {
    blue: ["#3b82f6", "#06b6d4", "#a855f7", "#3b82f6"],
    cyan: ["#06b6d4", "#22c55e", "#3b82f6", "#06b6d4"],
    purple: ["#a855f7", "#3b82f6", "#06b6d4", "#a855f7"],
  }

  return (
    <div className={cn("relative", className)}>
      {/* Animated border */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        style={{
          borderRadius: `${rx} ${ry}`,
        }}
      >
        <svg
          className="absolute inset-0 w-full h-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="100%" y2="100%">
              {colors[color].map((c, i) => (
                <motion.stop
                  key={i}
                  offset={`${(i / (colors[color].length - 1)) * 100}%`}
                  stopColor={c}
                  animate={{
                    offset: [
                      `${(i / (colors[color].length - 1)) * 100}%`,
                      `${((i + 1) / (colors[color].length - 1)) * 100}%`,
                      `${(i / (colors[color].length - 1)) * 100}%`,
                    ],
                  }}
                  transition={{
                    duration: duration / 1000,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
              ))}
            </linearGradient>
          </defs>
          <motion.rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            rx={rx}
            ry={ry}
            fill="none"
            stroke={`url(#gradient-${color})`}
            strokeWidth="2"
            strokeDasharray="10 20"
            animate={{
              strokeDashoffset: [0, -100],
            }}
            transition={{
              duration: duration / 1000,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        </svg>
      </motion.div>

      {/* Glow effect */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        style={{
          borderRadius: `${rx} ${ry}`,
          boxShadow:
            color === "blue"
              ? "0 0 15px rgba(59, 130, 246, 0.2), inset 0 0 15px rgba(59, 130, 246, 0.1)"
              : color === "cyan"
              ? "0 0 15px rgba(6, 182, 212, 0.2), inset 0 0 15px rgba(6, 182, 212, 0.1)"
              : "0 0 15px rgba(168, 85, 247, 0.2), inset 0 0 15px rgba(168, 85, 247, 0.1)",
        }}
        animate={{
          opacity: [0.5, 1, 0.5],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
        }}
      />

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </div>
  )
}

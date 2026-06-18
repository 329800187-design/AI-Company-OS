import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"

interface FloatingDockItem {
  id: string
  label: string
  icon: React.ElementType
}

interface FloatingDockProps {
  items: FloatingDockItem[]
  activeId: string
  onSelect: (id: string) => void
  className?: string
}

export function FloatingDock({
  items,
  activeId,
  onSelect,
  className,
}: FloatingDockProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  return (
    <motion.div
      className={cn(
        "flex items-center gap-2 p-2 rounded-2xl bg-card/80 backdrop-blur-xl border border-border",
        className
      )}
      style={{
        boxShadow: "0 0 30px rgba(0, 0, 0, 0.3), 0 0 15px rgba(59, 130, 246, 0.1)",
      }}
    >
      {items.map((item) => {
        const isActive = activeId === item.id
        const isHovered = hoveredId === item.id

        return (
          <motion.button
            key={item.id}
            onClick={() => onSelect(item.id)}
            onMouseEnter={() => setHoveredId(item.id)}
            onMouseLeave={() => setHoveredId(null)}
            animate={{
              scale: isHovered ? 1.2 : isActive ? 1.1 : 1,
              y: isHovered ? -8 : 0,
            }}
            transition={{ type: "spring", stiffness: 400, damping: 15 }}
            className={cn(
              "relative flex flex-col items-center gap-1 p-2 rounded-xl transition-colors",
              isActive
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {/* Active indicator */}
            {isActive && (
              <motion.div
                layoutId="dockActive"
                className="absolute inset-0 rounded-xl bg-primary/10"
                style={{
                  boxShadow: "0 0 15px rgba(59, 130, 246, 0.3)",
                }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              />
            )}

            {/* Icon */}
            <item.icon className="w-5 h-5 relative z-10" />

            {/* Label on hover */}
            <AnimatePresence>
              {isHovered && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 5 }}
                  className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-card border border-border text-xs whitespace-nowrap"
                  style={{
                    boxShadow: "0 0 10px rgba(0, 0, 0, 0.3)",
                  }}
                >
                  {item.label}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.button>
        )
      })}
    </motion.div>
  )
}

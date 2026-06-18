import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"

export function LoadingScreen({ onComplete }: { onComplete: () => void }) {
  const [progress, setProgress] = useState(0)
  const [phase, setPhase] = useState(0) // 0: init, 1: loading, 2: complete
  const [showContent, setShowContent] = useState(true)

  useEffect(() => {
    // Simulate loading progress
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setPhase(2)
          setTimeout(() => {
            setShowContent(false)
            setTimeout(onComplete, 500)
          }, 800)
          return 100
        }
        return prev + Math.random() * 15 + 5
      })
    }, 100)

    setPhase(1)

    return () => clearInterval(interval)
  }, [onComplete])

  return (
    <AnimatePresence>
      {showContent && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-[9999] flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, #0a0a1a 0%, #0f172a 50%, #0a0a1a 100%)",
          }}
        >
          {/* Animated grid background */}
          <div className="absolute inset-0 overflow-hidden">
            {/* Grid lines */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.1 }}
              transition={{ duration: 1 }}
              className="absolute inset-0"
              style={{
                backgroundImage: `
                  linear-gradient(rgba(59, 130, 246, 0.3) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(59, 130, 246, 0.3) 1px, transparent 1px)
                `,
                backgroundSize: "50px 50px",
              }}
            />

            {/* Animated scan line */}
            <motion.div
              animate={{
                y: ["-100%", "100vh"],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "linear",
              }}
              className="absolute left-0 right-0 h-[2px]"
              style={{
                background: "linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.8), transparent)",
                boxShadow: "0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)",
              }}
            />

            {/* Floating particles */}
            {Array.from({ length: 30 }).map((_, i) => (
              <motion.div
                key={i}
                initial={{
                  x: Math.random() * window.innerWidth,
                  y: Math.random() * window.innerHeight,
                  opacity: 0,
                }}
                animate={{
                  y: [null, Math.random() * -200 - 100],
                  opacity: [0, 0.8, 0],
                }}
                transition={{
                  duration: Math.random() * 3 + 2,
                  repeat: Infinity,
                  delay: Math.random() * 2,
                }}
                className="absolute w-1 h-1 rounded-full bg-primary"
                style={{
                  boxShadow: "0 0 10px rgba(59, 130, 246, 0.8)",
                }}
              />
            ))}

            {/* Gradient orbs */}
            <motion.div
              animate={{
                x: [0, 100, 0],
                y: [0, -50, 0],
                scale: [1, 1.2, 1],
              }}
              transition={{ duration: 8, repeat: Infinity }}
              className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full"
              style={{
                background: "radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, transparent 70%)",
                filter: "blur(40px)",
              }}
            />
            <motion.div
              animate={{
                x: [0, -80, 0],
                y: [0, 60, 0],
                scale: [1, 1.3, 1],
              }}
              transition={{ duration: 10, repeat: Infinity }}
              className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full"
              style={{
                background: "radial-gradient(circle, rgba(6, 182, 212, 0.1) 0%, transparent 70%)",
                filter: "blur(40px)",
              }}
            />
          </div>

          {/* Center content */}
          <div className="relative z-10 flex flex-col items-center">
            {/* Logo animation */}
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
              className="relative mb-8"
            >
              {/* Outer ring */}
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 w-24 h-24 rounded-full border-2 border-transparent"
                style={{
                  borderTopColor: "#3b82f6",
                  borderRightColor: "#06b6d4",
                  filter: "drop-shadow(0 0 10px rgba(59, 130, 246, 0.5))",
                }}
              />

              {/* Inner ring */}
              <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
                className="absolute inset-2 w-20 h-20 rounded-full border-2 border-transparent"
                style={{
                  borderBottomColor: "#a855f7",
                  borderLeftColor: "#06b6d4",
                  filter: "drop-shadow(0 0 10px rgba(168, 85, 247, 0.5))",
                }}
              />

              {/* Center icon */}
              <motion.div
                animate={{
                  boxShadow: [
                    "0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)",
                    "0 0 30px rgba(59, 130, 246, 0.8), 0 0 60px rgba(59, 130, 246, 0.5)",
                    "0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)",
                  ],
                }}
                transition={{ duration: 2, repeat: Infinity }}
                className="relative w-24 h-24 rounded-full bg-gradient-to-br from-primary to-cyan flex items-center justify-center"
              >
                <motion.div
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  <svg
                    width="40"
                    height="40"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="white"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                  </svg>
                </motion.div>
              </motion.div>
            </motion.div>

            {/* Title */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-4xl font-bold mb-2"
              style={{
                background: "linear-gradient(135deg, #3b82f6, #06b6d4, #a855f7)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                textShadow: "none",
              }}
            >
              AI Company OS
            </motion.h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="text-muted-foreground mb-8"
            >
              多智能体协作操作系统
            </motion.p>

            {/* Progress bar */}
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 300 }}
              transition={{ delay: 0.6 }}
              className="relative"
            >
              {/* Background */}
              <div className="h-2 rounded-full bg-secondary/50 overflow-hidden">
                {/* Fill */}
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(progress, 100)}%` }}
                  transition={{ duration: 0.3 }}
                  className="h-full rounded-full"
                  style={{
                    background: "linear-gradient(90deg, #3b82f6, #06b6d4, #a855f7)",
                    boxShadow: "0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)",
                  }}
                />
              </div>

              {/* Glow effect on the edge */}
              <motion.div
                animate={{
                  x: [0, 280, 0],
                  opacity: [0, 1, 0],
                }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute top-0 w-4 h-2"
                style={{
                  background: "radial-gradient(circle, rgba(255, 255, 255, 0.8), transparent)",
                  filter: "blur(4px)",
                }}
              />
            </motion.div>

            {/* Progress text */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
              className="mt-4 flex items-center gap-2"
            >
              <motion.div
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="w-2 h-2 rounded-full bg-primary"
                style={{
                  boxShadow: "0 0 10px rgba(59, 130, 246, 0.8)",
                }}
              />
              <span className="text-sm text-muted-foreground">
                {phase === 0 && "初始化中..."}
                {phase === 1 && `加载中... ${Math.floor(Math.min(progress, 100))}%`}
                {phase === 2 && "准备就绪"}
              </span>
            </motion.div>

            {/* Loading items */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
              className="mt-8 flex gap-6"
            >
              {["AI 引擎", "Agent 网络", "技能系统"].map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1.2 + i * 0.2 }}
                  className="flex items-center gap-2"
                >
                  <motion.div
                    animate={{
                      scale: progress > (i + 1) * 30 ? [1, 1.2, 1] : 1,
                      backgroundColor:
                        progress > (i + 1) * 30 ? "#22c55e" : "#334155",
                    }}
                    transition={{ duration: 0.3 }}
                    className="w-3 h-3 rounded-full"
                    style={{
                      boxShadow:
                        progress > (i + 1) * 30
                          ? "0 0 10px rgba(34, 197, 94, 0.5)"
                          : "none",
                    }}
                  />
                  <span className="text-xs text-muted-foreground">{item}</span>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

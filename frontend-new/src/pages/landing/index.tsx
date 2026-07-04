import { useState, useCallback, useRef, useEffect } from "react"
import { motion, AnimatePresence, useMotionValue, useTransform, useSpring } from "framer-motion"
import { ArrowRight } from "lucide-react"

const MODULES = [
  { name: "Boss", label: "指挥台", icon: "◆" },
  { name: "Agents", label: "智能体", icon: "◇" },
  { name: "Data", label: "数据", icon: "○" },
  { name: "Reports", label: "报告", icon: "□" },
  { name: "Memory", label: "记忆", icon: "△" },
  { name: "Workflow", label: "工作流", icon: "⬡" },
]

interface LandingPageProps {
  onEnter: () => void
}

export function LandingPage({ onEnter }: LandingPageProps) {
  const [exiting, setExiting] = useState(false)
  const [skipped, setSkipped] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  // Magnetic button effect
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const buttonX = useSpring(useTransform(mouseX, [-1, 1], [-4, 4]), { stiffness: 300, damping: 30 })
  const buttonY = useSpring(useTransform(mouseY, [-1, 1], [-3, 3]), { stiffness: 300, damping: 30 })

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    const distX = (e.clientX - centerX) / (rect.width / 2)
    const distY = (e.clientY - centerY) / (rect.height / 2)
    mouseX.set(distX)
    mouseY.set(distY)
  }, [mouseX, mouseY])

  const handleMouseLeave = useCallback(() => {
    mouseX.set(0)
    mouseY.set(0)
  }, [mouseX, mouseY])

  const handleEnter = useCallback(() => {
    setExiting(true)
    // Wait for exit animation to complete
    setTimeout(onEnter, 700)
  }, [onEnter])

  const handleSkip = useCallback(() => {
    setSkipped(true)
    setTimeout(onEnter, 50)
  }, [onEnter])

  // Keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleSkip()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [handleSkip])

  if (skipped) return null

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden"
          style={{ background: "#0A0A0A" }}
        >
          {/* Subtle grain texture */}
          <div
            className="absolute inset-0 opacity-[0.025] pointer-events-none"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
              backgroundSize: "128px 128px",
            }}
          />

          {/* Ambient breathing glow */}
          <motion.div
            className="absolute inset-0 pointer-events-none"
            animate={{
              background: [
                "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(255,255,255,0.015) 0%, transparent 70%)",
                "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(255,255,255,0.025) 0%, transparent 70%)",
                "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(255,255,255,0.015) 0%, transparent 70%)",
              ],
            }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          />

          {/* Skip button */}
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            onClick={handleSkip}
            className="absolute top-8 right-8 z-20 px-4 py-2 text-xs text-[#555555] tracking-[0.15em] uppercase cursor-pointer hover:text-[#8A8A8A] transition-colors duration-300"
          >
            跳过 · Skip
          </motion.button>

          {/* ─── Central Stage Card ─── */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="relative z-10 w-[min(90vw,720px)] rounded-3xl border border-[#1E1E1E] bg-[#111111] px-10 py-14 sm:px-16 sm:py-20"
            style={{
              boxShadow:
                "0 0 80px rgba(255,255,255,0.015), 0 0 200px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)",
            }}
          >
            {/* Top edge highlight */}
            <div
              className="absolute top-0 left-1/2 -translate-x-1/2 w-2/3 h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent)",
              }}
            />

            <div className="flex flex-col items-center text-center">
              {/* Status tag */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="mb-8"
              >
                <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#252525] bg-[#161616] text-[11px] text-[#666666] tracking-[0.18em] uppercase">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#4A4A4A] animate-pulse" />
                  Multi-Agent Operating System
                </span>
              </motion.div>

              {/* Main title */}
              <motion.h1
                initial={{ opacity: 0, y: 28 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 1.0, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[0.92]"
                style={{ color: "#FFFFFF" }}
              >
                AI Company
                <br />
                <span className="text-[#888888]">OS</span>
              </motion.h1>

              {/* Subtitle */}
              <motion.p
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="mt-6 text-sm sm:text-base max-w-sm leading-relaxed text-[#5A5A5A]"
              >
                你的 AI 公司操作系统
                <br />
                输入目标，AI 自动拆解、执行、验证
              </motion.p>

              {/* Module dots — staggered entry with icons */}
              <motion.div
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: {},
                  visible: {
                    transition: { staggerChildren: 0.1, delayChildren: 1.1 },
                  },
                }}
                className="mt-10 flex flex-wrap justify-center gap-2.5"
              >
                {MODULES.map((mod) => (
                  <motion.div
                    key={mod.name}
                    variants={{
                      hidden: { opacity: 0, y: 12, scale: 0.85 },
                      visible: {
                        opacity: 1,
                        y: 0,
                        scale: 1,
                        transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
                      },
                    }}
                    className="group flex items-center gap-2 px-3.5 py-2 rounded-xl border border-[#222222] bg-[#161616] hover:border-[#333333] hover:bg-[#1A1A1A] transition-all duration-300 cursor-default"
                  >
                    <span className="text-[10px] text-[#555555] group-hover:text-[#777777] transition-colors">
                      {mod.icon}
                    </span>
                    <span className="text-xs text-[#888888] tracking-wider group-hover:text-[#AAAAAA] transition-colors">
                      {mod.name}
                    </span>
                    <span className="text-[10px] text-[#444444] group-hover:text-[#555555] transition-colors">
                      {mod.label}
                    </span>
                  </motion.div>
                ))}
              </motion.div>

              {/* Enter Button — magnetic hover */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 1.6, ease: [0.16, 1, 0.3, 1] }}
                className="mt-12"
              >
                <motion.button
                  ref={buttonRef}
                  style={{ x: buttonX, y: buttonY }}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                  onClick={handleEnter}
                  className="group relative px-10 py-4 rounded-2xl cursor-pointer overflow-hidden transition-all duration-200 active:scale-[0.97]"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                >
                  {/* Button background with gradient */}
                  <div
                    className="absolute inset-0 rounded-2xl transition-all duration-300"
                    style={{
                      background: "#FFFFFF",
                    }}
                  />
                  {/* Hover highlight */}
                  <div
                    className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                    style={{
                      background:
                        "linear-gradient(135deg, rgba(255,255,255,1) 0%, rgba(240,240,240,1) 100%)",
                    }}
                  />
                  <div className="relative flex items-center gap-3">
                    <span className="font-medium text-base tracking-wider text-[#0A0A0A]">
                      进入系统
                    </span>
                    <ArrowRight className="w-4 h-4 text-[#0A0A0A] group-hover:translate-x-1.5 transition-transform duration-300" />
                  </div>
                </motion.button>
              </motion.div>
            </div>
          </motion.div>

          {/* Bottom hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.0 }}
            className="absolute bottom-8 left-1/2 -translate-x-1/2 text-xs tracking-wider text-[#333333]"
          >
            按 Enter 或点击进入 · 按 Esc 跳过
          </motion.p>

          {/* Exit animation — clip-path reveal with warm background */}
          {exiting && (
            <motion.div
              initial={{ clipPath: "circle(0% at 50% 50%)" }}
              animate={{ clipPath: "circle(150% at 50% 50%)" }}
              transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
              className="fixed inset-0 z-[60]"
              style={{ background: "#F4F3EF" }}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

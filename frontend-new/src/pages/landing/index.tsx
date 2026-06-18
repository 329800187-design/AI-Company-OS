import { useState, useEffect, useRef, useCallback, memo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Zap } from "lucide-react"

// ============ CONSTANTS ============
const AGENTS = [
  { name: "GPT-4o", color: "#10b981", icon: "🧠" },
  { name: "Claude", color: "#8b5cf6", icon: "🤖" },
  { name: "DeepSeek", color: "#3b82f6", icon: "🔍" },
  { name: "Gemini", color: "#f59e0b", icon: "✨" },
  { name: "DALL-E", color: "#ec4899", icon: "🎨" },
  { name: "Copilot", color: "#06b6d4", icon: "👨‍💻" },
  { name: "Cursor", color: "#22c55e", icon: "⚡" },
  { name: "Llama", color: "#f97316", icon: "🦙" },
  { name: "Mistral", color: "#a855f7", icon: "🌊" },
  { name: "Qwen", color: "#ef4444", icon: "🔮" },
  { name: "SD", color: "#14b8a6", icon: "🖼️" },
  { name: "MJ", color: "#6366f1", icon: "🎯" },
]

const CODE_SNIPPETS = [
  `class AgentOrchestrator:
    async def execute(self, goal):
        plan = await self.decompose(goal)
        results = await asyncio.gather(*[
            agent.run(task) for task in plan
        ])
        return self.synthesize(results)`,
  `const pipeline = new AIChain()
  .pipe(decompose)
  .parallel(execute)
  .pipe(verify)
  .pipe(synthesize)
  .build()

const result = await pipeline.run(goal)`,
  `fn orchestrate(goal: Goal) -> Output {
    let agents = discover_agents();
    let plan = decompose(goal);
    let results = execute_parallel(plan, agents);
    synthesize(results)
}`,
]

// ============ GALAXY BACKGROUND (OPTIMIZED) ============
const GalaxyCanvas = memo(function GalaxyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d", { alpha: false })!
    let w = 0
    let h = 0

    const STAR_COUNT = 300
    const stars: Array<{ x: number; y: number; z: number; s: number }> = []
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push({
        x: (Math.random() - 0.5) * 1500,
        y: (Math.random() - 0.5) * 1500,
        z: Math.random() * 800 + 200,
        s: Math.random() * 1.5 + 0.3,
      })
    }

    const resize = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener("resize", resize)

    let animId: number
    const render = () => {
      const cx = w * 0.5
      const cy = h * 0.5

      // Background
      ctx.fillStyle = "#050510"
      ctx.fillRect(0, 0, w, h)

      // Subtle nebula
      const nebula = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.5)
      nebula.addColorStop(0, "rgba(15, 15, 35, 1)")
      nebula.addColorStop(1, "rgba(5, 5, 16, 1)")
      ctx.fillStyle = nebula
      ctx.fillRect(0, 0, w, h)

      // Stars
      for (let i = 0; i < STAR_COUNT; i++) {
        const star = stars[i]
        star.z -= 1.2
        if (star.z <= 0) {
          star.x = (Math.random() - 0.5) * 1500
          star.y = (Math.random() - 0.5) * 1500
          star.z = 800
        }

        const f = 300 / star.z
        const sx = cx + star.x * f
        const sy = cy + star.y * f
        if (sx < 0 || sx > w || sy < 0 || sy > h) continue

        const size = star.s * f
        const alpha = Math.min(1, f * 0.6)

        ctx.globalAlpha = alpha
        ctx.fillStyle = "#fff"
        ctx.beginPath()
        ctx.arc(sx, sy, Math.max(0.5, size), 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1

      animId = requestAnimationFrame(render)
    }

    render()
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener("resize", resize)
    }
  }, [])

  return <canvas ref={canvasRef} className="fixed inset-0 z-0" />
})

// ============ AI CORE (ENHANCED) ============
const AICore = memo(function AICore() {
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 80, damping: 20, delay: 0.5 }}
      className="relative w-32 h-32"
    >
      {/* Outer glow */}
      <div
        className="absolute -inset-16 rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(59, 130, 246, 0.08), transparent 70%)",
          animation: "glow-pulse 4s ease-in-out infinite",
        }}
      />

      {/* Pulse rings */}
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="absolute inset-0 rounded-full"
          style={{
            border: "1px solid rgba(59, 130, 246, 0.15)",
            animation: `pulse-ring 3s ease-out ${i}s infinite`,
          }}
        />
      ))}

      {/* Rotating rings */}
      <div
        className="absolute -inset-4 rounded-full border border-blue-500/10 border-dashed"
        style={{ animation: "spin 20s linear infinite" }}
      />
      <div
        className="absolute -inset-8 rounded-full border border-cyan-500/8 border-dotted"
        style={{ animation: "spin 15s linear infinite reverse" }}
      />
      <div
        className="absolute -inset-12 rounded-full border border-purple-500/5"
        style={{ animation: "spin 25s linear infinite" }}
      />

      {/* Core sphere */}
      <div
        className="absolute inset-0 rounded-full overflow-hidden"
        style={{
          background: "linear-gradient(135deg, #0f172a, #1e1b4b)",
          boxShadow: "0 0 60px rgba(59, 130, 246, 0.3), 0 0 120px rgba(59, 130, 246, 0.1), inset 0 0 30px rgba(59, 130, 246, 0.2)",
        }}
      >
        {/* Animated gradient overlay */}
        <div
          className="absolute inset-0"
          style={{
            background: "conic-gradient(from 0deg, transparent, rgba(59, 130, 246, 0.15), transparent, rgba(6, 182, 212, 0.1), transparent)",
            animation: "spin 8s linear infinite",
          }}
        />

        {/* Inner light */}
        <div
          className="absolute inset-4 rounded-full"
          style={{
            background: "radial-gradient(circle at 35% 35%, rgba(59, 130, 246, 0.3), transparent 60%)",
          }}
        />
      </div>

      {/* Center icon */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative">
          <span className="text-3xl relative z-10">⚡</span>
          <div
            className="absolute inset-0 -m-2 rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(59, 130, 246, 0.4), transparent)",
              filter: "blur(8px)",
            }}
          />
        </div>
      </div>
    </motion.div>
  )
})

// ============ AGENT RING ============
function AgentRing() {
  const [hovered, setHovered] = useState<string | null>(null)
  const radius = 170

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.8, duration: 1 }}
      className="absolute inset-0"
    >
      {/* Orbit tracks */}
      <div
        className="absolute rounded-full border border-white/[0.03]"
        style={{
          width: radius * 2,
          height: radius * 2,
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
          boxShadow: "0 0 40px rgba(59, 130, 246, 0.03) inset",
        }}
      />
      <div
        className="absolute rounded-full border border-white/[0.02]"
        style={{
          width: radius * 2 + 40,
          height: radius * 2 + 40,
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
        }}
      />

      {/* Agents */}
      {AGENTS.map((agent, i) => {
        const angle = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2
        const x = Math.cos(angle) * radius
        const y = Math.sin(angle) * radius
        const isHov = hovered === agent.name

        return (
          <motion.div
            key={agent.name}
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1 + i * 0.06, type: "spring", stiffness: 200 }}
            className="absolute"
            style={{
              left: `calc(50% + ${x}px)`,
              top: `calc(50% + ${y}px)`,
              transform: "translate(-50%, -50%)",
            }}
            onMouseEnter={() => setHovered(agent.name)}
            onMouseLeave={() => setHovered(null)}
          >
            <motion.div
              animate={{
                y: [0, -5, 0],
                scale: isHov ? 1.3 : 1,
              }}
              transition={{
                y: { duration: 3, repeat: Infinity, delay: i * 0.2 },
                scale: { type: "spring", stiffness: 300 },
              }}
              className="relative cursor-pointer"
            >
              {/* Hover glow */}
              {isHov && (
                <div
                  className="absolute -inset-4 rounded-xl"
                  style={{
                    background: `radial-gradient(circle, ${agent.color}40, transparent)`,
                    filter: "blur(12px)",
                  }}
                />
              )}

              {/* Icon */}
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center text-lg transition-all relative z-10"
                style={{
                  background: `linear-gradient(135deg, ${agent.color}15, ${agent.color}08)`,
                  border: `1px solid ${agent.color}${isHov ? "60" : "20"}`,
                  boxShadow: isHov ? `0 0 25px ${agent.color}40, 0 0 50px ${agent.color}20` : "none",
                  backdropFilter: "blur(10px)",
                }}
              >
                {agent.icon}
              </div>

              {/* Label */}
              {isHov && (
                <motion.div
                  initial={{ opacity: 0, y: 5, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-3 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap"
                  style={{
                    background: `linear-gradient(135deg, ${agent.color}25, ${agent.color}15)`,
                    color: agent.color,
                    border: `1px solid ${agent.color}30`,
                    boxShadow: `0 4px 12px ${agent.color}20`,
                    backdropFilter: "blur(10px)",
                  }}
                >
                  {agent.name}
                </motion.div>
              )}
            </motion.div>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

// ============ CODE STREAM ============
function CodeStream() {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setCurrent((p) => (p + 1) % CODE_SNIPPETS.length), 5000)
    return () => clearInterval(timer)
  }, [])

  const getLineColor = (line: string): string => {
    const t = line.trim()
    if (t.startsWith("//") || t.startsWith("#")) return "#6b7280"
    if (t.startsWith("class ") || t.startsWith("fn ") || t.startsWith("const ")) return "#c084fc"
    if (t.includes('"') || t.includes("'")) return "#86efac"
    if (t.includes("async") || t.includes("await") || t.includes("return")) return "#f472b6"
    return "#94a3b8"
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.5 }}
      className="w-full max-w-lg mx-auto mt-10"
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={current}
          initial={{ opacity: 0, x: 15 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -15 }}
          transition={{ duration: 0.3 }}
          className="rounded-xl overflow-hidden relative"
          style={{
            background: "linear-gradient(135deg, rgba(10, 10, 25, 0.8), rgba(15, 15, 35, 0.6))",
            border: "1px solid rgba(59, 130, 246, 0.1)",
            boxShadow: "0 0 30px rgba(59, 130, 246, 0.05), 0 20px 40px rgba(0, 0, 0, 0.3)",
            backdropFilter: "blur(20px)",
          }}
        >
          {/* Glow effect */}
          <div
            className="absolute -inset-1 rounded-xl"
            style={{
              background: "linear-gradient(135deg, rgba(59, 130, 246, 0.1), transparent, rgba(6, 182, 212, 0.05))",
              filter: "blur(20px)",
            }}
          />

          <div className="relative">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.04]">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
                </div>
                <span className="text-[10px] text-white/20 ml-2 font-mono">agent.py</span>
              </div>
              <div className="flex gap-1">
                {CODE_SNIPPETS.map((_, i) => (
                  <div
                    key={i}
                    className="w-1 h-1 rounded-full transition-all"
                    style={{
                      background: i === current ? "#3b82f6" : "rgba(255,255,255,0.1)",
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Code */}
            <pre className="p-4 text-[11px] font-mono leading-relaxed overflow-x-auto">
              <code>
                {CODE_SNIPPETS[current].split("\n").map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="flex"
                  >
                    <span className="w-5 text-right mr-3 text-white/10 select-none text-[10px]">
                      {i + 1}
                    </span>
                    <span style={{ color: getLineColor(line) }}>{line}</span>
                  </motion.div>
                ))}
              </code>
            </pre>

            {/* Bottom gradient bar */}
            <div
              className="h-0.5"
              style={{
                background: "linear-gradient(90deg, #3b82f6, #06b6d4, #a855f7, #3b82f6)",
                backgroundSize: "200% 100%",
                animation: "shimmer 3s linear infinite",
              }}
            />
          </div>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  )
}

// ============ MAIN LANDING ============
interface LandingPageProps {
  onEnter: () => void
}

export function LandingPage({ onEnter }: LandingPageProps) {
  const [exiting, setExiting] = useState(false)

  const handleEnter = useCallback(() => {
    setExiting(true)
    setTimeout(onEnter, 500)
  }, [onEnter])

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden"
        >
          <GalaxyCanvas />

          {/* Vignette overlay */}
          <div
            className="fixed inset-0 z-[1] pointer-events-none"
            style={{
              background: "radial-gradient(ellipse at center, transparent 40%, rgba(5, 5, 16, 0.8) 100%)",
            }}
          />

          <div className="relative z-10 flex flex-col items-center px-4">
            {/* Title */}
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-center mb-10"
            >
              <h1 className="text-6xl md:text-7xl font-bold tracking-tight">
                <span
                  style={{
                    background: "linear-gradient(135deg, #60a5fa 0%, #22d3ee 50%, #a78bfa 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    filter: "drop-shadow(0 0 30px rgba(59, 130, 246, 0.3))",
                  }}
                >
                  AI Company
                </span>
              </h1>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="text-white/25 text-base mt-3 tracking-[0.3em] uppercase"
              >
                Multi-Agent Operating System
              </motion.p>
            </motion.div>

            {/* AI Core + Agents */}
            <div className="relative w-[400px] h-[400px] flex items-center justify-center mb-8">
              <AgentRing />
              <AICore />
            </div>

            {/* Code Stream */}
            <CodeStream />

            {/* Enter Button */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 2, duration: 0.6 }}
              className="mt-10"
            >
              <button
                onClick={handleEnter}
                className="group relative px-10 py-4 rounded-2xl cursor-pointer overflow-hidden transition-all duration-300 hover:scale-105 hover:-translate-y-0.5 active:scale-95"
                style={{
                  background: "linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(6, 182, 212, 0.08))",
                  border: "1px solid rgba(59, 130, 246, 0.2)",
                  boxShadow: "0 0 30px rgba(59, 130, 246, 0.1), 0 10px 30px rgba(0, 0, 0, 0.3)",
                  backdropFilter: "blur(20px)",
                }}
              >
                {/* Hover gradient */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                  style={{
                    background: "linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(6, 182, 212, 0.15))",
                  }}
                />

                {/* Shine animation */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100"
                  style={{
                    animation: "btn-shine 2s ease-in-out infinite",
                    background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent)",
                    backgroundSize: "50% 100%",
                  }}
                />

                {/* Glow on hover */}
                <div
                  className="absolute -inset-1 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                  style={{
                    background: "linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(6, 182, 212, 0.1))",
                    filter: "blur(15px)",
                  }}
                />

                <div className="relative flex items-center gap-3">
                  <Zap className="w-5 h-5 text-blue-400" />
                  <span className="text-white/90 font-medium text-lg tracking-wider">
                    你好
                  </span>
                  <ArrowRight className="w-5 h-5 text-white/40 group-hover:translate-x-1 group-hover:text-white/60 transition-all" />
                </div>
              </button>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 2.5 }}
                className="text-center text-white/15 text-xs mt-4 tracking-wider"
              >
                点击进入 · Click to enter
              </motion.p>
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Brain,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"

interface Step {
  name: string
  status: "pending" | "running" | "completed" | "failed"
  result?: string
}

export default function CommanderPage() {
  const [goal, setGoal] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [steps, setSteps] = useState<Step[]>([])
  const [finalResult, setFinalResult] = useState<string | null>(null)
  const [, setSessionId] = useState<string | null>(null)

  const handleRun = async () => {
    if (!goal.trim() || isRunning) return

    setIsRunning(true)
    setSteps([])
    setFinalResult(null)

    try {
      const result = await api.runCommander(goal)
      setSessionId(result.session_id)

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getCommanderStatus(result.session_id)

          setSteps(
            (status.steps || []).map((s) => ({
              name: s.name,
              status: s.status as Step["status"],
              result: s.result,
            }))
          )

          if (status.status === "completed") {
            setFinalResult(status.final_result || "任务完成")
            setIsRunning(false)
            clearInterval(pollInterval)
          } else if (status.status === "failed") {
            setIsRunning(false)
            clearInterval(pollInterval)
          }
        } catch (error) {
          console.error("Polling error:", error)
        }
      }, 1000)

      // Cleanup on unmount
      return () => clearInterval(pollInterval)
    } catch (error) {
      setIsRunning(false)
      console.error("Commander error:", error)
    }
  }

  const statusIcon = (status: Step["status"]) => {
    switch (status) {
      case "pending":
        return <div className="w-4 h-4 rounded-full border-2 border-border" />
      case "running":
        return <Loader2 className="w-4 h-4 text-primary animate-spin" />
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-green" />
      case "failed":
        return <XCircle className="w-4 h-4 text-destructive" />
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple to-primary flex items-center justify-center">
          <Brain className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">智能任务</h1>
          <p className="text-muted-foreground">
            输入复杂目标，AI 自动拆解成多个步骤执行
          </p>
        </div>
      </div>

      {/* Input */}
      <GlowCard>
        <div className="flex gap-3">
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="描述你的目标，比如：帮我分析竞品，然后写一份调研报告..."
            className="min-h-[100px] text-base"
          />
          <Button
            onClick={handleRun}
            disabled={!goal.trim() || isRunning}
            size="lg"
            variant="glow"
            className="self-end px-6"
          >
            {isRunning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            开始执行
          </Button>
        </div>
      </GlowCard>

      {/* Pipeline */}
      {(steps.length > 0 || isRunning) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Steps */}
          <div className="space-y-3">
            {steps.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <GlowCard
                  className={cn(
                    "transition-all duration-300",
                    step.status === "running" && "border-primary/50 glow"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="mt-1">{statusIcon(step.status)}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium">{step.name}</h4>
                        <Badge
                          variant={
                            step.status === "completed"
                              ? "success"
                              : step.status === "failed"
                              ? "destructive"
                              : step.status === "running"
                              ? "info"
                              : "secondary"
                          }
                        >
                          {step.status === "pending"
                            ? "等待中"
                            : step.status === "running"
                            ? "执行中"
                            : step.status === "completed"
                            ? "已完成"
                            : "失败"}
                        </Badge>
                      </div>
                      {step.result && (
                        <p className="text-sm text-muted-foreground mt-2">
                          {step.result}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </GlowCard>
              </motion.div>
            ))}
          </div>

          {/* Running indicator */}
          {isRunning && steps.length === 0 && (
            <GlowCard className="border-primary/50 glow">
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
                <div>
                  <h4 className="font-medium">正在分析目标...</h4>
                  <p className="text-sm text-muted-foreground">
                    AI 正在拆解你的任务
                  </p>
                </div>
              </div>
            </GlowCard>
          )}

          {/* Final Result */}
          <AnimatePresence>
            {finalResult && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <GlowCard className="border-green/50">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-green/20 flex items-center justify-center">
                      <Sparkles className="w-5 h-5 text-green" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-green mb-2">
                        任务完成
                      </h4>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {finalResult}
                      </p>
                    </div>
                  </div>
                </GlowCard>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  )
}

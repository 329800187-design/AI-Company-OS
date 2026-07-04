import { useState } from "react"
import { motion } from "framer-motion"
import {
  Brain,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileText,
  ChevronDown,
  HelpCircle,
  XCircle,
  Sparkles,
  Clock,
  ArrowDown,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { cn } from "@/lib/utils"

interface GovernanceResult {
  run_id: string
  status: string
  artifact_path?: string
  json_path?: string
  task_id?: string
  mode?: string
  summary?: string
  plan?: Record<string, unknown>
  classification?: Record<string, unknown>
  result?: Record<string, unknown>
  collaboration_plan?: CollaborationPlan
}

interface ArtifactContent {
  run_id: string
  artifact_path: string
  content: string
}

const examples = [
  { goal: "帮我为手工耳环生成文案和产品图", label: "文案+图片" },
  { goal: "帮我调研手工耳环市场并生成种草文案", label: "调研+文案" },
  { goal: "帮我搭建一个全自动赚钱公司系统", label: "自动赚钱系统拦截" },
]

const stepStatusConfig: Record<string, { text: string; variant: "success" | "destructive" | "warning" | "outline"; icon: typeof CheckCircle2 }> = {
  succeeded: { text: "成功", variant: "success", icon: CheckCircle2 },
  failed: { text: "失败", variant: "destructive", icon: XCircle },
  running: { text: "执行中", variant: "warning", icon: Clock },
  assigned: { text: "已分配", variant: "warning", icon: Clock },
  pending: { text: "等待中", variant: "outline", icon: Clock },
  unassigned: { text: "未分配", variant: "outline", icon: AlertCircle },
}

interface CollaborationStep {
  id: string
  name: string
  task_type: string
  required_capability: string
  input_from?: string
  status: string
  assigned_agent_id?: string
  result?: {
    ok: boolean
    output?: Record<string, unknown>
    error?: string
    artifacts?: string[]
  }
}

interface CollaborationPlan {
  plan_id: string
  goal: string
  status: string
  steps: CollaborationStep[]
}

function CollaborationSteps({ plan }: { plan: CollaborationPlan }) {
  const steps = plan.steps ?? []
  return (
    <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white space-y-3">
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-medium">协同执行计划</h4>
        <Badge variant={plan.status === "succeeded" ? "success" : plan.status === "failed" ? "destructive" : "outline"}>
          {plan.status}
        </Badge>
      </div>

      <div className="text-xs text-[#8A8A8A] mb-2">
        {steps.length} 个步骤 · {plan.plan_id}
      </div>

      {steps.map((step, idx) => {
        const sc = stepStatusConfig[step.status] ?? stepStatusConfig.pending
        return (
          <div key={step.id}>
            {/* Connector */}
            {idx > 0 && (
              <div className="flex justify-center py-1">
                <ArrowDown className="w-4 h-4 text-[#D5D5D5]" />
              </div>
            )}

            {/* Step card */}
            <div className="p-4 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA]">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-[#8A8A8A]">{step.id}</span>
                  <span className="text-sm font-medium">{step.name}</span>
                </div>
                <Badge variant={sc.variant} className="gap-1">
                  <sc.icon className="w-3 h-3" />
                  {sc.text}
                </Badge>
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-[#666]">
                <span className="px-2 py-0.5 rounded bg-[#F4F3EF] border border-[#E5E5E5]">
                  {step.task_type}
                </span>
                <span className="px-2 py-0.5 rounded bg-[#F4F3EF] border border-[#E5E5E5]">
                  {step.required_capability}
                </span>
                {step.input_from && (
                  <span className="px-2 py-0.5 rounded bg-blue/5 border border-blue/20 text-blue">
                    ← {step.input_from}
                  </span>
                )}
              </div>

              {step.assigned_agent_id && (
                <div className="mt-2 text-xs text-[#8A8A8A]">
                  Agent: <span className="font-mono">{step.assigned_agent_id}</span>
                </div>
              )}

              {/* Step result */}
              {step.result && (
                <div className="mt-3 p-3 rounded-lg bg-white border border-[#E5E5E5]">
                  <div className="flex items-center gap-2 mb-1">
                    {step.result.ok ? (
                      <CheckCircle2 className="w-3 h-3 text-green" />
                    ) : (
                      <XCircle className="w-3 h-3 text-red" />
                    )}
                    <span className="text-xs font-medium">
                      {step.result.ok ? "执行成功" : "执行失败"}
                    </span>
                  </div>

                  {step.result.error && (
                    <p className="text-xs text-red mt-1">{step.result.error}</p>
                  )}

                  {step.result.output && (
                    <div className="mt-2 text-xs text-[#666] max-h-[120px] overflow-auto">
                      <pre className="whitespace-pre-wrap font-sans">
                        {JSON.stringify(step.result.output, null, 2).slice(0, 500)}
                        {JSON.stringify(step.result.output, null, 2).length > 500 ? "\n..." : ""}
                      </pre>
                    </div>
                  )}

                  {step.result.artifacts && step.result.artifacts.length > 0 && (
                    <div className="mt-2 text-xs text-[#8A8A8A]">
                      产物: {step.result.artifacts.join(", ")}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function CommanderPage() {
  const [goal, setGoal] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<GovernanceResult | null>(null)
  const [artifact, setArtifact] = useState<ArtifactContent | null>(null)
  const [artifactLoading, setArtifactLoading] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  const [showResult, setShowResult] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    if (!goal.trim()) return
    setIsLoading(true)
    setResult(null)
    setArtifact(null)
    setError(null)

    try {
      const response = await api.governanceRun(goal, "", true)
      setResult(response)

      // Auto-fetch artifact on success
      if (response.status === "succeeded" && response.run_id) {
        setArtifactLoading(true)
        try {
          const art = await api.governanceArtifact(response.run_id)
          setArtifact(art)
        } catch {
          // artifact fetch failed, not critical
        } finally {
          setArtifactLoading(false)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败")
    } finally {
      setIsLoading(false)
    }
  }

  const statusLabel = (status: string) => {
    switch (status) {
      case "succeeded":
        return { text: "执行成功", variant: "success" as const, icon: CheckCircle2 }
      case "rejected":
        return { text: "已拒绝", variant: "warning" as const, icon: XCircle }
      case "needs_clarification":
        return { text: "需要澄清", variant: "warning" as const, icon: HelpCircle }
      case "failed":
        return { text: "执行失败", variant: "destructive" as const, icon: AlertCircle }
      default:
        return { text: status, variant: "outline" as const, icon: AlertCircle }
    }
  }

  const classification = result?.classification as Record<string, unknown> | undefined
  const isBlocked = result?.status === "rejected" || result?.status === "needs_clarification"
  const collaborationPlan = result?.collaboration_plan as CollaborationPlan | undefined
  const isCollaboration = !!collaborationPlan

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple to-primary flex items-center justify-center">
          <Brain className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">智能任务</h1>
          <p className="text-[#8A8A8A]">
            受控主脑入口 — 输入任务，AI 自动分类、规划、执行
          </p>
        </div>
      </div>

      {/* Input form */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-4">
        <h3 className="font-semibold">任务描述</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="描述你的任务，比如：帮我为手工耳环生成小红书种草文案..."
          className="min-h-[100px] text-base"
        />

        <div className="flex items-center gap-3">
          <Button
            onClick={handleRun}
            disabled={!goal.trim() || isLoading}
            size="lg"
            variant="default"
            className="gap-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {isLoading ? "执行中..." : "执行任务"}
          </Button>
        </div>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-[#8A8A8A]">示例:</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setGoal(ex.goal)}
              className="px-3 py-1.5 text-xs rounded-full border border-[#E5E5E5] text-[#8A8A8A] hover:text-[#0B0B0B] hover:border-[#B5B5B5] bg-white transition-colors"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl border border-red/20 bg-red/5 flex items-center gap-3"
        >
          <AlertCircle className="w-5 h-5 text-red flex-shrink-0" />
          <span className="text-sm text-red">{error}</span>
        </motion.div>
      )}

      {/* Result */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Status bar */}
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white flex flex-wrap items-center gap-3">
            {(() => {
              const s = statusLabel(result.status)
              return (
                <Badge variant={s.variant} className="gap-1">
                  <s.icon className="w-3 h-3" />
                  {s.text}
                </Badge>
              )
            })()}
            {result.mode && (
              <Badge variant="outline">模式: {result.mode}</Badge>
            )}
            {result.task_id && (
              <Badge variant="outline">任务: {result.task_id.slice(0, 12)}...</Badge>
            )}
          </div>

          {/* Summary */}
          {result.summary && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">执行摘要</h4>
              <p className="text-sm text-[#333]">{result.summary}</p>
            </div>
          )}

          {/* Collaboration Steps */}
          {!isBlocked && isCollaboration && collaborationPlan && (
            <CollaborationSteps plan={collaborationPlan} />
          )}

          {/* Blocked / needs_clarification */}
          {isBlocked && classification && (
            <div className="p-5 rounded-xl border border-yellow/30 bg-yellow/5 space-y-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-yellow" />
                <h4 className="font-medium text-yellow">
                  {result.status === "needs_clarification" ? "需要澄清" : "任务被拒绝"}
                </h4>
              </div>

              {classification.reason != null && (
                <p className="text-sm text-[#666]">
                  原因: {String(classification.reason)}
                </p>
              )}

              {classification.needs_clarification === true &&
                Array.isArray(classification.clarification_questions) && (
                  <div className="p-3 rounded-lg bg-white border border-yellow/20">
                    <p className="text-xs font-medium text-yellow mb-2">
                      请补充以下信息：
                    </p>
                    <ul className="text-sm text-[#666] space-y-1">
                      {(classification.clarification_questions as string[]).map(
                        (q, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-yellow mt-0.5">•</span>
                            {q}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}
            </div>
          )}

          {/* Classification info (non-blocking) */}
          {result.classification && !isBlocked && (() => {
            const cls = result.classification as Record<string, unknown>
            return (
              <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium">分类结果</h4>
                  <Badge variant={cls.ok ? "success" : "warning"}>
                    {cls.ok ? "通过" : "未通过"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-[#666]">
                  {cls.capability_id != null && (
                    <div>能力: {String(cls.capability_id)}</div>
                  )}
                  {typeof cls.confidence === "number" && (
                    <div>置信度: {Math.round((cls.confidence as number) * 100)}%</div>
                  )}
                </div>
              </div>
            )
          })()}

          {/* Plan (collapsible) */}
          {result.plan && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setShowPlan(!showPlan)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">执行计划</span>
                <ChevronDown
                  className={cn(
                    "w-4 h-4 transition-transform",
                    showPlan && "rotate-180"
                  )}
                />
              </button>
              {showPlan && (
                <div className="px-4 pb-4">
                  <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
                    {JSON.stringify(result.plan ?? null, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Artifact (hidden for collaboration tasks) */}
          {!isCollaboration && (artifact || artifactLoading) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4" />
                <h4 className="text-sm font-medium">产物内容</h4>
                {artifactLoading && (
                  <Loader2 className="w-3 h-3 animate-spin text-[#8A8A8A]" />
                )}
              </div>
              {artifact && (
                <>
                  <div className="text-xs text-[#8A8A8A] mb-2">
                    路径: {artifact.artifact_path}
                  </div>
                  <div className="p-4 rounded-lg bg-[#F4F3EF] border border-border max-h-[500px] overflow-auto">
                    <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
                      {artifact.content}
                    </pre>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Result details (collapsible) */}
          {result.result && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setShowResult(!showResult)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">完整结果</span>
                <ChevronDown
                  className={cn(
                    "w-4 h-4 transition-transform",
                    showResult && "rotate-180"
                  )}
                />
              </button>
              {showResult && (
                <div className="px-4 pb-4">
                  <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
                    {JSON.stringify(result.result ?? null, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}

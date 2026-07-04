import { useState } from "react"
import { motion } from "framer-motion"
import { Shield, Loader2, Sparkles, AlertCircle, CheckCircle2, FileText, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { CollaborationSteps, extractCollaboration } from "@/components/features/collaboration-steps"

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
}

interface ArtifactContent {
  run_id: string
  artifact_path: string
  content: string
}

const platforms = [
  { id: "xiaohongshu", label: "小红书" },
  { id: "douyin", label: "抖音" },
]

const examples = [
  { goal: "帮我为手工耳环生成小红书种草文案", platform: "xiaohongshu", label: "小红书手工耳环文案" },
  { goal: "帮我为手工耳环生成抖音种草脚本", platform: "douyin", label: "抖音手工耳环脚本" },
  { goal: "帮我搭建一个全自动赚钱公司系统", platform: "xiaohongshu", label: "自动赚钱系统拦截测试" },
]

export default function GovernancePage() {
  const [goal, setGoal] = useState("")
  const [platform, setPlatform] = useState("xiaohongshu")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<GovernanceResult | null>(null)
  const [artifact, setArtifact] = useState<ArtifactContent | null>(null)
  const [artifactLoading, setArtifactLoading] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  const [showResult, setShowResult] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const handleRun = async () => {
    if (!goal.trim()) return
    setIsLoading(true)
    setResult(null)
    setArtifact(null)
    setError(null)

    try {
      const response = await api.governanceRun(goal, platform, true)
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

  const handleApprove = async (stepId: string, comment?: string) => {
    const collab = extractCollaboration(result as unknown as Record<string, unknown>)
    if (!collab?.planId) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepApprove(collab.planId, stepId, comment)
      setResult((prev) => prev ? { ...prev, collaboration_plan: updated } : prev)
    } catch (err) {
      setError(err instanceof Error ? err.message : "批准失败")
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (stepId: string, comment?: string) => {
    const collab = extractCollaboration(result as unknown as Record<string, unknown>)
    if (!collab?.planId) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepReject(collab.planId, stepId, comment)
      setResult((prev) => prev ? { ...prev, collaboration_plan: updated } : prev)
    } catch (err) {
      setError(err instanceof Error ? err.message : "拒绝失败")
    } finally {
      setActionLoading(false)
    }
  }

  const handleRetry = async (stepId: string) => {
    const collab = extractCollaboration(result as unknown as Record<string, unknown>)
    if (!collab?.planId) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepRetry(collab.planId, stepId)
      setResult((prev) => prev ? { ...prev, collaboration_plan: updated } : prev)
    } catch (err) {
      setError(err instanceof Error ? err.message : "重试失败")
    } finally {
      setActionLoading(false)
    }
  }

  const statusLabel = (status: string) => {
    switch (status) {
      case "succeeded": return { text: "执行成功", variant: "success" as const, icon: CheckCircle2 }
      case "rejected": return { text: "已拒绝", variant: "warning" as const, icon: AlertCircle }
      case "needs_clarification": return { text: "需要澄清", variant: "warning" as const, icon: AlertCircle }
      case "failed": return { text: "执行失败", variant: "destructive" as const, icon: AlertCircle }
      default: return { text: status, variant: "outline" as const, icon: AlertCircle }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Governance 主入口</h1>
          <p className="text-[#8A8A8A]">分类 → 计划 → 执行 → 产物交付，一站式闭环</p>
        </div>
      </div>

      {/* Input form */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-4">
        <h3 className="font-semibold">目标描述</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="例如：帮我为手工耳环生成小红书种草文案"
          className="min-h-[80px]"
        />

        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">平台</label>
            <div className="flex gap-2">
              {platforms.map((p) => (
                <Button
                  key={p.id}
                  variant={platform === p.id ? "default" : "outline"}
                  size="sm"
                  onClick={() => setPlatform(p.id)}
                >
                  {p.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="ml-auto pt-5">
            <Button
              onClick={handleRun}
              disabled={!goal.trim() || isLoading}
              className="gap-2"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {isLoading ? "执行中..." : "执行"}
            </Button>
          </div>
        </div>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-[#8A8A8A]">示例:</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => {
                setGoal(ex.goal)
                setPlatform(ex.platform)
              }}
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
            {result.run_id && (
              <span className="text-xs text-[#8A8A8A] ml-auto">Run ID: {result.run_id}</span>
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
          {(() => {
            const collab = extractCollaboration(result as unknown as Record<string, unknown>)
            if (!collab?.steps) return null
            return (
              <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
                <CollaborationSteps
                  planId={collab.planId}
                  status={collab.status}
                  steps={collab.steps}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onRetry={handleRetry}
                  actionLoading={actionLoading}
                />
              </div>
            )
          })()}

          {/* Classification info */}
          {result.classification && (() => {
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
                {cls.needs_clarification === true && Array.isArray(cls.clarification_questions) && (
                  <div className="mt-3 p-3 rounded-lg bg-yellow/5 border border-yellow/20">
                    <p className="text-xs font-medium text-yellow mb-1">需要澄清：</p>
                    <ul className="text-xs text-[#666] space-y-1">
                      {(cls.clarification_questions as string[]).map((q, i) => (
                        <li key={i}>• {q}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {cls.reason != null && (
                  <p className="mt-2 text-xs text-[#8A8A8A]">原因: {String(cls.reason)}</p>
                )}
              </div>
            )
          })()}

          {/* Plan (collapsible) */}
          {result.plan && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                onClick={() => setShowPlan(!showPlan)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">执行计划</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showPlan ? "rotate-180" : ""}`} />
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

          {/* Artifact */}
          {(artifact || artifactLoading) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4" />
                <h4 className="text-sm font-medium">产物内容</h4>
                {artifactLoading && <Loader2 className="w-3 h-3 animate-spin text-[#8A8A8A]" />}
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
                onClick={() => setShowResult(!showResult)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">完整结果</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showResult ? "rotate-180" : ""}`} />
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

import { CheckCircle2, XCircle, Clock, AlertTriangle, SkipForward, Loader2, Check, X, RotateCw } from "lucide-react"
import { useState } from "react"
import type { CollaborationStepView } from "@/types"

interface CollaborationStepsProps {
  planId?: string
  status?: string
  steps?: CollaborationStepView[]
  /** When true, show a compact header with the plan id */
  showHeader?: boolean
  /** Callback when approve button is clicked */
  onApprove?: (stepId: string, comment?: string) => void | Promise<void>
  /** Callback when reject button is clicked */
  onReject?: (stepId: string, comment?: string) => void | Promise<void>
  /** Callback when retry button is clicked */
  onRetry?: (stepId: string) => void | Promise<void>
  /** Whether approve/reject actions are loading */
  actionLoading?: boolean
}

const stepStatusConfig: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  succeeded: { label: "成功", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: CheckCircle2 },
  failed: { label: "失败", color: "bg-red-500/10 text-red-400 border-red-500/20", icon: XCircle },
  running: { label: "运行中", color: "bg-blue-500/10 text-blue-400 border-blue-500/20", icon: Loader2 },
  waiting_human: { label: "等待人工", color: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: AlertTriangle },
  skipped: { label: "已跳过", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20", icon: SkipForward },
  assigned: { label: "已分配", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20", icon: Clock },
  pending: { label: "待执行", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20", icon: Clock },
}

function getStepId(step: CollaborationStepView, index: number): string {
  return step.step_id || step.id || `step-${index}`
}

function getStepName(step: CollaborationStepView, index: number): string {
  return step.name || `步骤 ${index + 1}`
}

function truncateJson(obj: unknown, maxLen = 300): string {
  const str = JSON.stringify(obj, null, 2)
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen) + "..."
}

function getReviewDecision(step: CollaborationStepView): { action?: string; comment?: string } | null {
  const decision = step.result?.output?._review_decision
  if (!decision || typeof decision !== "object") return null
  return decision as { action?: string; comment?: string }
}

function getRiskDecision(step: CollaborationStepView): {
  allowed?: boolean
  requires_confirmation?: boolean
  risk_level?: string
  reasons?: string[]
  recommended_action?: string
} | null {
  const decision = step.result?.output?._risk_decision
  if (!decision || typeof decision !== "object") return null
  return decision as { allowed?: boolean; requires_confirmation?: boolean; risk_level?: string; reasons?: string[]; recommended_action?: string }
}

const riskLevelConfig: Record<string, { label: string; color: string }> = {
  high: { label: "高风险", color: "bg-red-500/10 text-red-400 border-red-500/20" },
  medium: { label: "中风险", color: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  low: { label: "低风险", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
}

function StepRow({
  step,
  index,
  onApprove,
  onReject,
  onRetry,
  actionLoading,
}: {
  step: CollaborationStepView
  index: number
  onApprove?: (stepId: string, comment?: string) => void | Promise<void>
  onReject?: (stepId: string, comment?: string) => void | Promise<void>
  onRetry?: (stepId: string) => void | Promise<void>
  actionLoading?: boolean
}) {
  const status = step.status || "pending"
  const config = stepStatusConfig[status] || stepStatusConfig.pending
  const Icon = config.icon
  const stepId = getStepId(step, index)
  const reviewDecision = getReviewDecision(step)
  const riskDecision = getRiskDecision(step)
  const [comment, setComment] = useState("")
  const [showComment, setShowComment] = useState(false)

  return (
    <div className="p-3 bg-white/5 border border-white/10 rounded-lg">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${status === "running" ? "animate-spin" : ""}`} />
        <span className="text-sm font-medium text-white">{getStepName(step, index)}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${config.color}`}>
          {config.label}
        </span>
        {step.assigned_agent_id && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            {step.assigned_agent_id}
          </span>
        )}
        {step.review_required && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
            需审核
          </span>
        )}
      </div>

      {/* Details row */}
      <div className="text-[10px] text-[#666] flex flex-wrap gap-x-3 gap-y-0.5">
        {step.task_type && <span>类型: {step.task_type}</span>}
        {step.required_capability && <span>能力: {step.required_capability}</span>}
        {step.matched_capability && step.matched_capability !== step.required_capability && (
          <span className="text-emerald-400">匹配: {step.matched_capability}</span>
        )}
        {step.depends_on && step.depends_on.length > 0 && (
          <span>依赖: {step.depends_on.join(", ")}</span>
        )}
      </div>

      {/* Routing reason */}
      {step.routing_reason && (
        <div className="mt-1 text-[10px] text-[#8A8A8A] italic">
          路由: {step.routing_reason}
        </div>
      )}

      {/* Risk decision */}
      {riskDecision && (
        <div className="mt-1 text-[10px] px-2 py-1 rounded bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 flex-wrap">
            {riskDecision.risk_level && (
              <span className={`px-1.5 py-0.5 rounded-full border ${(riskLevelConfig[riskDecision.risk_level] || riskLevelConfig.low).color}`}>
                {(riskLevelConfig[riskDecision.risk_level] || riskLevelConfig.low).label}
              </span>
            )}
            {riskDecision.recommended_action && (
              <span className="text-[#8A8A8A]">
                建议: {riskDecision.recommended_action === "block" ? "阻止"
                  : riskDecision.recommended_action === "confirm" ? "需确认"
                  : riskDecision.recommended_action === "sandbox_required" ? "需沙箱执行"
                  : "允许"}
              </span>
            )}
          </div>
          {riskDecision.reasons && riskDecision.reasons.length > 0 && (
            <div className="mt-0.5 text-[#666]">
              原因: {riskDecision.reasons.join("; ")}
            </div>
          )}
        </div>
      )}

      {/* Sandbox note (when waiting_human due to sandbox_required) */}
      {status === "waiting_human" && riskDecision?.recommended_action === "sandbox_required" && (
        <div className="mt-1 text-[10px] px-2 py-1 rounded bg-orange-500/5 border border-orange-500/10 text-orange-400">
          沙箱执行尚未实现 — 批准后将尝试沙箱执行，v0 阶段会返回失败
        </div>
      )}

      {/* Expected output */}
      {step.expected_output && (
        <div className="mt-1 text-[10px] text-[#8A8A8A]">
          预期输出: {step.expected_output}
        </div>
      )}

      {/* Review decision (if exists) */}
      {reviewDecision && (
        <div className="mt-1 text-[10px] px-2 py-1 rounded bg-amber-500/5 border border-amber-500/10">
          <span className="text-amber-400">
            审核: {reviewDecision.action === "approve" ? "已批准" : "已拒绝"}
          </span>
          {reviewDecision.comment && (
            <span className="text-[#8A8A8A] ml-2">
              — {String(reviewDecision.comment)}
            </span>
          )}
        </div>
      )}

      {/* Approve / Reject buttons for waiting_human */}
      {status === "waiting_human" && onApprove && onReject && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {!showComment ? (
            <>
              <button
                onClick={() => onApprove(stepId)}
                disabled={actionLoading}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md
                  bg-emerald-500/10 text-emerald-400 border border-emerald-500/20
                  hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
              >
                <Check className="w-3 h-3" />
                批准继续
              </button>
              <button
                onClick={() => setShowComment(true)}
                disabled={actionLoading}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md
                  bg-red-500/10 text-red-400 border border-red-500/20
                  hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                <X className="w-3 h-3" />
                拒绝
              </button>
            </>
          ) : (
            <div className="flex items-center gap-1.5 w-full">
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="拒绝原因（可选）"
                className="flex-1 px-2 py-1 text-[11px] bg-white/5 border border-white/10 rounded
                  text-white placeholder-[#666] outline-none focus:border-red-500/30"
                autoFocus
              />
              <button
                onClick={() => {
                  onReject(stepId, comment || undefined)
                  setComment("")
                  setShowComment(false)
                }}
                disabled={actionLoading}
                className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md
                  bg-red-500/10 text-red-400 border border-red-500/20
                  hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                确认拒绝
              </button>
              <button
                onClick={() => {
                  setShowComment(false)
                  setComment("")
                }}
                className="px-2 py-1 text-[11px] text-[#666] hover:text-white transition-colors"
              >
                取消
              </button>
            </div>
          )}
        </div>
      )}

      {/* Retry button for failed/skipped steps */}
      {(status === "failed" || status === "skipped") && onRetry && (
        <div className="mt-2">
          <button
            onClick={() => onRetry(stepId)}
            disabled={actionLoading}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md
              bg-amber-500/10 text-amber-400 border border-amber-500/20
              hover:bg-amber-500/20 transition-colors disabled:opacity-50"
          >
            <RotateCw className="w-3 h-3" />
            重试
          </button>
        </div>
      )}

      {/* Result */}
      {step.result && (
        <div className="mt-2 p-2 bg-white/5 rounded-md">
          {step.result.ok ? (
            <div className="text-[10px]">
              <span className="text-emerald-400">✓ 完成</span>
              {step.result.output && (
                <pre className="mt-1 text-[#8A8A8A] whitespace-pre-wrap max-h-[120px] overflow-auto">
                  {truncateJson(step.result.output)}
                </pre>
              )}
              {step.result.artifacts && step.result.artifacts.length > 0 && (
                <div className="mt-1 text-[#666]">
                  产物: {step.result.artifacts.length} 个
                </div>
              )}
            </div>
          ) : (
            <div className="text-[10px] text-red-400">
              ✗ {step.result.error || step.error || "未知错误"}
            </div>
          )}
        </div>
      )}

      {/* Error without result */}
      {!step.result && step.error && (
        <div className="mt-2 p-2 bg-red-500/5 border border-red-500/10 rounded-md text-[10px] text-red-400">
          {step.error}
        </div>
      )}
    </div>
  )
}

export function CollaborationSteps({
  planId,
  status,
  steps,
  showHeader = true,
  onApprove,
  onReject,
  onRetry,
  actionLoading,
}: CollaborationStepsProps) {
  if (!steps || steps.length === 0) return null

  const planStatus = status || "pending"
  const statusConfig = stepStatusConfig[planStatus] || stepStatusConfig.pending

  return (
    <div className="space-y-3">
      {showHeader && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-blue-400">
            协同步骤 ({steps.length} 步)
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${statusConfig.color}`}>
            {statusConfig.label}
          </span>
          {planId && (
            <span className="text-[10px] text-[#666]">
              Plan: {planId.slice(0, 12)}...
            </span>
          )}
        </div>
      )}
      <div className="space-y-2">
        {steps.map((step, i) => (
          <StepRow
            key={getStepId(step, i)}
            step={step}
            index={i}
            onApprove={onApprove}
            onReject={onReject}
            onRetry={onRetry}
            actionLoading={actionLoading}
          />
        ))}
      </div>
    </div>
  )
}

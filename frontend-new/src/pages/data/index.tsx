import { useState } from "react"
import { motion } from "framer-motion"
import {
  BarChart3, Sparkles, Loader2, FileText, CheckCircle2, AlertCircle,
  ChevronDown, RotateCcw, Copy, Check,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { SaveToDeliveryButton } from "@/components/features/save-to-delivery-button"

/* eslint-disable @typescript-eslint/no-explicit-any */

// ── Agent 执行结果 ──────────────────────────────────────────────────────────

interface AgentRunResult {
  ok: boolean
  mode?: string
  agent_id: string
  task_type?: string
  summary?: string
  structured_output?: Record<string, any>
  output: Record<string, any>
  artifacts: string[]
  warnings?: string[]
  errors?: string[]
  error?: string
  next_actions?: string[]
  risk_decision?: {
    risk_level?: string
    recommended_action?: string
  }
  timeline_events?: Array<Record<string, any>>
  metadata?: Record<string, any>
}

// ── Governance fallback 结果 ─────────────────────────────────────────────────

interface GovernanceRunResult {
  run_id: string
  status: string
  artifact_path?: string
  json_path?: string
  task_id?: string
  mode?: string
  summary?: string
  plan?: Record<string, any>
  classification?: Record<string, any>
  result?: {
    ok: boolean
    checks?: Record<string, any>
    spec?: Record<string, any>
    [key: string]: any
  }
}

interface ArtifactContent {
  run_id: string
  artifact_path: string
  content: string
}

// ── 判断 Agent 是否因不可用而失败 ──────────────────────────────────────────

function isAgentUnavailable(result: AgentRunResult): boolean {
  if (result.ok) return false
  const err = (result.error || "").toLowerCase()
  return (
    err.includes("not enabled") ||
    err.includes("not found") ||
    err.includes("api key") ||
    err.includes("unexpected")
  )
}

// ── 结构化字段展示组件 ──────────────────────────────────────────────────────

function DataStructuredOutput({ output }: { output: Record<string, any> }) {
  const sections: { label: string; value: any; isList?: boolean; isKV?: boolean }[] = []

  // 分析类型
  if (output.type) sections.push({ label: "分析类型", value: output.type === "analysis_framework" ? "数据分析框架" : "文件数据分析" })

  // 分析目标
  if (output.goal) sections.push({ label: "分析目标", value: output.goal })

  // 关键发现
  if (Array.isArray(output.key_findings) && output.key_findings.length > 0) {
    sections.push({ label: "🔍 关键发现", value: output.key_findings, isList: true })
  }

  // 检测到的列
  if (Array.isArray(output.detected_columns) && output.detected_columns.length > 0) {
    sections.push({ label: "📊 检测到的数据列", value: output.detected_columns, isList: true })
  }

  // 指标
  if (output.metrics && typeof output.metrics === "object") {
    sections.push({ label: "📈 分析指标", value: output.metrics, isKV: true })
  }

  // 建议
  if (Array.isArray(output.recommendations) && output.recommendations.length > 0) {
    sections.push({ label: "💡 建议", value: output.recommendations, isList: true })
  }

  // 数据预览
  if (Array.isArray(output.preview) && output.preview.length > 0) {
    sections.push({ label: "数据预览（前5行）", value: output.preview })
  }

  // 描述统计
  if (output.describe && typeof output.describe === "object" && Object.keys(output.describe).length > 0) {
    sections.push({ label: "描述统计", value: output.describe, isKV: true })
  }

  // 列类型
  if (output.dtypes && typeof output.dtypes === "object") {
    sections.push({ label: "列类型", value: output.dtypes, isKV: true })
  }

  if (sections.length === 0) {
    return (
      <div className="space-y-3">
        {Object.entries(output).map(([k, v]) => (
          <div key={k}>
            <span className="text-xs font-medium text-[#8A8A8A]">{k}</span>
            <div className="mt-1 text-sm text-[#333]">
              {typeof v === "object" ? (
                <pre className="whitespace-pre-wrap text-xs bg-[#F4F3EF] rounded p-2 max-h-[200px] overflow-auto">
                  {JSON.stringify(v, null, 2)}
                </pre>
              ) : (
                <p className="leading-relaxed">{String(v)}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {sections.map(({ label, value, isList, isKV }) => (
        <div key={label}>
          <h4 className="text-xs font-medium text-[#8A8A8A] mb-1">{label}</h4>
          {isList ? (
            <ul className="text-sm text-[#333] space-y-1.5">
              {(value as any[]).map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-[#8A8A8A] mt-0.5">•</span>
                  <span className="leading-relaxed">{String(item)}</span>
                </li>
              ))}
            </ul>
          ) : isKV ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(value as Record<string, any>).map(([k, v]) => (
                <div key={k} className="p-2 rounded-lg bg-[#F4F3EF] border border-[#E5E5E5]">
                  <span className="text-[10px] text-[#8A8A8A] block">{k}</span>
                  <span className="text-xs text-[#333] font-medium">
                    {Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          ) : typeof value === "string" && value.includes("\n") ? (
            <div className="text-sm text-[#333] leading-relaxed whitespace-pre-wrap bg-[#F4F3EF] rounded-lg p-3">
              {value}
            </div>
          ) : typeof value === "object" && !Array.isArray(value) ? (
            <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded p-2 overflow-auto max-h-[200px] whitespace-pre-wrap">
              {JSON.stringify(value, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-[#333] leading-relaxed">{String(value)}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ── 主页面 ──────────────────────────────────────────────────────────────────

export default function DataPage() {
  const [goal, setGoal] = useState("")

  // Agent 执行状态
  const [isLoading, setIsLoading] = useState(false)
  const [agentResult, setAgentResult] = useState<AgentRunResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Governance fallback 状态
  const [fallbackResult, setFallbackResult] = useState<GovernanceRunResult | null>(null)
  const [fallbackArtifact, setFallbackArtifact] = useState<ArtifactContent | null>(null)
  const [fallbackLoading, setFallbackLoading] = useState(false)

  // UI 状态
  const [copied, setCopied] = useState(false)
  const [showDetails, setShowDetails] = useState(false)

  const examples = [
    "帮我分析这个月销售数据，生成一份数据分析报告",
    "分析手工耳环的销售趋势和用户画像",
    "帮我做一份电商运营数据分析简报",
  ]

  // ── Agent 优先执行 ──────────────────────────────────────────────────────

  const handleGenerate = async () => {
    if (!goal.trim()) return

    setIsLoading(true)
    setAgentResult(null)
    setFallbackResult(null)
    setFallbackArtifact(null)
    setError(null)

    try {
      const result = await api.executeAgent("data", {
        goal,
        task_type: "data_analyze",
        context: {},
        input: { goal },
      })
      setAgentResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 执行失败")
    } finally {
      setIsLoading(false)
    }
  }

  // ── Governance fallback 手动触发 ────────────────────────────────────────

  const handleFallback = async () => {
    setFallbackLoading(true)
    setFallbackResult(null)
    setFallbackArtifact(null)

    try {
      const response = await api.governanceRun(goal, "", true)
      setFallbackResult(response)

      if (response.status === "succeeded" && response.run_id) {
        try {
          const art = await api.governanceArtifact(response.run_id)
          setFallbackArtifact(art)
        } catch {
          // artifact fetch failed, not critical
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Governance fallback 失败")
    } finally {
      setFallbackLoading(false)
    }
  }

  const handleCopy = (text: string) => {
    if (text) {
      navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const getCopyText = (): string => {
    const output = agentResult?.structured_output || agentResult?.output
    if (agentResult?.ok && output) {
      const o = output
      const parts: string[] = []
      if (o.summary) parts.push(String(o.summary))
      if (Array.isArray(o.key_findings)) parts.push("关键发现:\n" + o.key_findings.join("\n"))
      if (Array.isArray(o.recommendations)) parts.push("建议:\n" + o.recommendations.join("\n"))
      if (o.metrics) parts.push("指标:\n" + JSON.stringify(o.metrics, null, 2))
      return parts.join("\n\n")
    }
    if (fallbackArtifact?.content) return fallbackArtifact.content
    return ""
  }

  const agentUnavailable = agentResult ? isAgentUnavailable(agentResult) : false

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
          <BarChart3 className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">看数据</h1>
          <p className="text-[#8A8A8A]">数据分析报告框架/简报</p>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 rounded-xl border border-blue-500/20 bg-blue-500/5">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
          <div className="text-sm">
            <p className="text-blue-400 font-medium">数据分析说明</p>
            <p className="text-[#8A8A8A] mt-1">
              当前生成<strong>数据分析报告框架/简报</strong>，不是直接读取真实文件。
              <br />
              报告包含：分析目标、数据范围假设、核心指标、趋势观察、异常点检查、业务解释、行动建议、后续需要补充的数据。
            </p>
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-3">数据分析目标</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="描述你想分析的数据，比如：帮我分析这个月销售数据，生成一份数据分析报告"
          className="min-h-[100px] text-base bg-[#F4F3EF] border-[#E5E5E5] rounded-xl"
        />

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2 mt-3">
          {examples.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setGoal(ex)}
              className="px-3 py-1.5 text-xs rounded-full border border-[#E5E5E5] text-[#8A8A8A] hover:text-[#0B0B0B] hover:border-[#B5B5B5] bg-white transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>

        <Button
          onClick={handleGenerate}
          disabled={!goal.trim() || isLoading}
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "Agent 正在分析..." : "生成数据分析报告"}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="p-6 rounded-2xl border border-red-500/50 bg-white">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-500 font-medium">生成失败</p>
                <p className="text-sm text-[#8A8A8A] mt-1">{error}</p>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Agent 结构化结果 ─────────────────────────────────────────────── */}
      {agentResult && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* 状态栏 */}
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white flex flex-wrap items-center gap-3">
            {agentResult.ok ? (
              <Badge variant="success" className="gap-1">
                <CheckCircle2 className="w-3 h-3" />
                Agent 分析成功
              </Badge>
            ) : (
              <Badge variant="destructive" className="gap-1">
                <AlertCircle className="w-3 h-3" />
                Agent 执行失败
              </Badge>
            )}
            {!!agentResult.metadata?.task_id && (
              <Badge variant="outline">任务: {String(agentResult.metadata!.task_id).slice(0, 12)}...</Badge>
            )}
            {!!agentResult.mode && (
              <Badge variant="outline">模式: {agentResult.mode}</Badge>
            )}
            {!!agentResult.metadata?.source && (
              <Badge variant="outline">来源: {String(agentResult.metadata.source)}</Badge>
            )}
            {agentResult.ok && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCopy(getCopyText())}
                className="ml-auto gap-2"
              >
                {copied ? <Check className="w-4 h-4 text-green" /> : <Copy className="w-4 h-4" />}
                {copied ? "已复制" : "复制结果"}
              </Button>
            )}
            {agentResult.ok && (
              <SaveToDeliveryButton
                goal={goal}
                agentId={agentResult.agent_id || "data"}
                agentResult={agentResult as unknown as Record<string, unknown>}
                sourcePage="data"
              />
            )}
          </div>

          {/* 执行摘要 */}
          {agentResult.summary && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-xs font-medium text-[#8A8A8A] mb-1">执行摘要</h4>
              <p className="text-sm text-[#333] leading-relaxed">{agentResult.summary}</p>
            </div>
          )}

          {/* 警告信息 */}
          {agentResult.warnings && agentResult.warnings.length > 0 && (
            <div className="p-4 rounded-xl border border-amber-200 bg-amber-50">
              <h4 className="text-xs font-medium text-amber-800 mb-2">⚠️ 警告</h4>
              <ul className="text-sm text-amber-700 space-y-1">
                {agentResult.warnings.map((warning, i) => (
                  <li key={i}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 错误信息 */}
          {agentResult.errors && agentResult.errors.length > 0 && (
            <div className="p-4 rounded-xl border border-red-200 bg-red-50">
              <h4 className="text-xs font-medium text-red-800 mb-2">❌ 错误</h4>
              <ul className="text-sm text-red-700 space-y-1">
                {agentResult.errors.map((err, i) => (
                  <li key={i}>• {err}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 建议的下一步操作 */}
          {agentResult.next_actions && agentResult.next_actions.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-xs font-medium text-[#8A8A8A] mb-2">💡 建议的下一步</h4>
              <ul className="text-sm text-[#333] space-y-1">
                {agentResult.next_actions.map((action, i) => (
                  <li key={i}>• {action}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Agent 成功 → 结构化展示 */}
          {agentResult.ok && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-emerald-500" />
                <h4 className="text-sm font-medium">数据分析结果</h4>
              </div>
              <DataStructuredOutput output={agentResult.structured_output || agentResult.output} />
            </div>
          )}

          {/* Agent 失败 → 显示错误 + fallback 按钮 */}
          {!agentResult.ok && (
            <div className="p-5 rounded-xl border border-amber-200 bg-amber-50 space-y-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <h4 className="text-sm font-medium text-amber-800">
                  {agentUnavailable
                    ? "Data Agent 未启用或执行失败"
                    : "Agent 执行未成功"}
                </h4>
              </div>
              <p className="text-xs text-amber-700">{agentResult.error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleFallback}
                disabled={fallbackLoading}
                className="gap-2"
              >
                {fallbackLoading ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <RotateCcw className="w-3 h-3" />
                )}
                {fallbackLoading ? "正在使用基础模板生成..." : "使用基础模板生成"}
              </Button>
            </div>
          )}

          {/* 原始 JSON 折叠区 */}
          {(agentResult.structured_output || agentResult.output) &&
           Object.keys(agentResult.structured_output || agentResult.output).length > 0 && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setShowDetails(!showDetails)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">原始 JSON</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showDetails ? "rotate-180" : ""}`} />
              </button>
              {showDetails && (
                <div className="px-4 pb-4">
                  <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
                    {JSON.stringify(agentResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}

      {/* ── Governance fallback 结果 ──────────────────────────────────────── */}
      {fallbackResult && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white flex flex-wrap items-center gap-3">
            {fallbackResult.status === "succeeded" ? (
              <Badge variant="success" className="gap-1">
                <CheckCircle2 className="w-3 h-3" />
                模板生成成功
              </Badge>
            ) : (
              <Badge variant="destructive" className="gap-1">
                <AlertCircle className="w-3 h-3" />
                模板生成失败
              </Badge>
            )}
            {fallbackResult.mode && (
              <Badge variant="outline">模式: {fallbackResult.mode}</Badge>
            )}
            {fallbackResult.status === "succeeded" && fallbackArtifact && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCopy(fallbackArtifact.content)}
                className="ml-auto gap-2"
              >
                {copied ? <Check className="w-4 h-4 text-green" /> : <Copy className="w-4 h-4" />}
                {copied ? "已复制" : "复制结果"}
              </Button>
            )}
          </div>

          {fallbackResult.summary && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">执行摘要</h4>
              <p className="text-sm text-[#333]">{fallbackResult.summary}</p>
            </div>
          )}

          {fallbackArtifact && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4" />
                <h4 className="text-sm font-medium">模板生成结果</h4>
              </div>
              <div className="p-4 rounded-lg bg-[#F4F3EF] border border-border max-h-[500px] overflow-auto">
                <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
                  {fallbackArtifact.content}
                </pre>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Empty State */}
      {!agentResult && !fallbackResult && !isLoading && (
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white/80 backdrop-blur-sm text-center py-12">
          <FileText className="w-12 h-12 mx-auto text-[#8A8A8A] mb-4" />
          <p className="text-[#8A8A8A]">输入数据分析目标，生成数据分析报告框架</p>
        </div>
      )}
    </div>
  )
}

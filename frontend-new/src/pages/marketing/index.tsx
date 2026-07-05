import { useState } from "react"
import { motion } from "framer-motion"
import {
  FileText, Sparkles, Loader2, Copy, Check, AlertCircle, CheckCircle2, ChevronDown, RotateCcw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { SaveToDeliveryButton } from "@/components/features/save-to-delivery-button"

const marketingModes = [
  { id: "copywriting", label: "通用文案", emoji: "✍️", taskType: "copywriting" },
  { id: "xiaohongshu", label: "小红书", emoji: "📕", taskType: "social_media", platform: "xiaohongshu" },
  { id: "douyin", label: "抖音", emoji: "🎵", taskType: "social_media", platform: "douyin" },
  { id: "seo_article", label: "SEO 长文", emoji: "🔎", taskType: "seo_article" },
  { id: "email_campaign", label: "邮件营销", emoji: "✉️", taskType: "email_campaign" },
  { id: "brand_strategy", label: "品牌策略", emoji: "🎯", taskType: "brand_strategy" },
  { id: "campaign_plan", label: "活动方案", emoji: "📣", taskType: "campaign_plan" },
]

const examples = [
  { goal: "帮我为手工耳环生成一段产品卖点文案", mode: "copywriting", label: "手工耳环产品文案" },
  { goal: "帮我为手工耳环生成小红书种草文案", mode: "xiaohongshu", label: "手工耳环小红书种草" },
  { goal: "帮我为手工耳环生成抖音短视频脚本", mode: "douyin", label: "手工耳环抖音脚本" },
  { goal: "帮我为手工银饰品牌写一套品牌定位", mode: "brand_strategy", label: "银饰品牌定位" },
  { goal: "帮我搭建一个全自动赚钱公司系统", mode: "copywriting", label: "自动赚钱系统拦截测试" },
]

// ── Agent 执行结果 ──────────────────────────────────────────────────────────

interface AgentRunResult {
  ok: boolean
  mode?: string
  agent_id: string
  task_type?: string
  summary?: string
  structured_output?: Record<string, unknown>
  output: Record<string, unknown>
  artifacts: string[]
  warnings?: string[]
  errors?: string[]
  error?: string
  blocked_by_governance?: boolean
  message?: string
  classification?: {
    capability_id?: string
    confidence?: number
    reason?: string
    needs_clarification?: boolean
    clarification_questions?: string[]
  }
  next_actions?: string[]
  risk_decision?: {
    risk_level?: string
    recommended_action?: string
  }
  timeline_events?: Array<Record<string, unknown>>
  metadata?: Record<string, unknown>
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
  plan?: Record<string, unknown>
  classification?: Record<string, unknown>
  result?: {
    ok: boolean
    checks?: Record<string, unknown>
    spec?: Record<string, unknown>
    [key: string]: unknown
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

function StructuredOutput({ output }: { output: Record<string, unknown> }) {
  const sections: { label: string; value: unknown; isList?: boolean }[] = []

  // 标题
  if (output.headline) sections.push({ label: "标题", value: output.headline })
  // 副标题
  if (output.subheadline) sections.push({ label: "副标题", value: output.subheadline })
  // 正文
  if (output.body) sections.push({ label: "正文", value: output.body })
  // CTA
  if (output.cta) sections.push({ label: "行动号召 (CTA)", value: output.cta })
  // 标签
  if (Array.isArray(output.hashtags) && output.hashtags.length > 0) {
    sections.push({ label: "标签", value: output.hashtags, isList: true })
  }
  if (Array.isArray(output.keywords) && output.keywords.length > 0) {
    sections.push({ label: "关键词", value: output.keywords, isList: true })
  }
  // 语气
  if (output.tone) sections.push({ label: "语气风格", value: output.tone })
  // 平台
  if (output.platform) sections.push({ label: "目标平台", value: output.platform })
  // 内容（social_media 场景）
  if (output.content && output.content !== output.body) {
    sections.push({ label: "文案内容", value: output.content })
  }
  // 推荐发布时间
  if (output.best_posting_time) sections.push({ label: "推荐发布时间", value: output.best_posting_time })
  // 互动钩子
  if (Array.isArray(output.engagement_hooks) && output.engagement_hooks.length > 0) {
    sections.push({ label: "互动钩子", value: output.engagement_hooks, isList: true })
  }
  // 媒体建议
  if (output.media_suggestion) sections.push({ label: "媒体建议", value: output.media_suggestion })
  // 备选标题
  if (Array.isArray(output.variations) && output.variations.length > 0) {
    sections.push({ label: "备选方案", value: output.variations, isList: true })
  }

  if (sections.length === 0) {
    // 没有识别到已知结构化字段，展示 key 列表
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
      {sections.map(({ label, value, isList }) => (
        <div key={label}>
          <h4 className="text-xs font-medium text-[#8A8A8A] mb-1">{label}</h4>
          {isList ? (
            <div className="flex flex-wrap gap-1.5">
              {(value as unknown[]).map((item, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {String(item)}
                </Badge>
              ))}
            </div>
          ) : typeof value === "string" && (value as string).includes("\n") ? (
            <div className="text-sm text-[#333] leading-relaxed whitespace-pre-wrap bg-[#F4F3EF] rounded-lg p-3">
              {String(value)}
            </div>
          ) : (
            <p className="text-sm text-[#333] leading-relaxed">{String(value)}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ── 主页面 ──────────────────────────────────────────────────────────────────

export default function MarketingPage() {
  const [mode, setMode] = useState("copywriting")
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
  const [showRawJson, setShowRawJson] = useState(false)

  // ── Agent 优先执行 ──────────────────────────────────────────────────────

  const handleGenerate = async () => {
    if (!goal.trim()) return
    setIsLoading(true)
    setAgentResult(null)
    setFallbackResult(null)
    setFallbackArtifact(null)
    setError(null)

    try {
      const selectedMode = marketingModes.find((item) => item.id === mode) || marketingModes[0]
      const platform = "platform" in selectedMode ? selectedMode.platform : undefined
      const result = await api.executeAgent("marketing", {
        goal,
        task_type: selectedMode.taskType,
        context: {
          mode: selectedMode.id,
          channel: selectedMode.label,
          ...(platform ? { platform } : {}),
        },
        input: {
          goal,
          mode: selectedMode.id,
          channel: selectedMode.label,
          ...(platform ? { platform } : {}),
        },
      })
      setAgentResult(result)
    } catch (err) {
      // 优先显示后端返回的具体错误信息
      const msg = err instanceof Error ? err.message : "Agent 执行失败"
      setError(msg.includes("Agent") ? msg : `Agent 执行失败: ${msg}`)
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
      const selectedMode = marketingModes.find((item) => item.id === mode)
      const platform = selectedMode && "platform" in selectedMode ? selectedMode.platform || "" : ""
      const response = await api.governanceRun(goal, platform, true)
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

  // 从 agent output 中提取可复制的纯文本
  const getCopyText = (): string => {
    const output = agentResult?.structured_output || agentResult?.output
    if (agentResult?.ok && output) {
      const o = output
      const parts: string[] = []
      if (o.headline) parts.push(String(o.headline))
      if (o.subheadline) parts.push(String(o.subheadline))
      if (o.body) parts.push(String(o.body))
      if (o.content) parts.push(String(o.content))
      if (o.cta) parts.push(String(o.cta))
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
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
          <FileText className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">写文案</h1>
          <p className="text-muted-foreground">基于市场分析的专业文案</p>
        </div>
      </div>

      {/* Marketing mode selection */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-3">选择文案类型</h3>
        <div className="flex flex-wrap gap-2">
          {marketingModes.map((item) => (
            <Button
              key={item.id}
              variant={mode === item.id ? "default" : "outline"}
              onClick={() => setMode(item.id)}
              className="gap-2"
            >
              <span>{item.emoji}</span>
              {item.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Goal input */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-3">
        <h3 className="font-semibold">产品描述</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="描述你的产品或文案需求，比如：手工制作的银饰耳环，适合年轻女性..."
          className="min-h-[100px]"
        />
        <Button
          onClick={handleGenerate}
          disabled={!goal.trim() || isLoading}
          variant="default"
          className="w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "Agent 正在生成..." : "生成文案"}
        </Button>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2 pt-2">
          <span className="text-xs text-[#8A8A8A]">示例:</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => {
                setGoal(ex.goal)
                setMode(ex.mode)
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
                Agent 生成成功
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
            {!!agentResult.task_type && (
              <Badge variant="outline">类型: {agentResult.task_type}</Badge>
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
                {copied ? "已复制" : "复制文案"}
              </Button>
            )}
            {agentResult.ok && (
              <SaveToDeliveryButton
                goal={goal}
                agentId={agentResult.agent_id || "marketing"}
                agentResult={agentResult as unknown as Record<string, unknown>}
                sourcePage="marketing"
              />
            )}
          </div>

          {/* 执行摘要 */}
          {Boolean(agentResult.summary) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-xs font-medium text-[#8A8A8A] mb-1">执行摘要</h4>
              <p className="text-sm text-[#333] leading-relaxed">{String(agentResult.summary)}</p>
            </div>
          )}

          {/* 降级原因（当 fallback=true 时显示） */}
          {agentResult.metadata?.fallback === true && Boolean(agentResult.metadata?.fallback_reason) && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#666]">
                <p className="font-medium text-yellow mb-1">降级原因</p>
                <p>{String(agentResult.metadata.fallback_reason)}</p>
              </div>
            </div>
          )}

          {/* 警告信息 */}
          {Boolean(agentResult.warnings && agentResult.warnings.length > 0) && (
            <div className="p-4 rounded-xl border border-amber-200 bg-amber-50">
              <h4 className="text-xs font-medium text-amber-800 mb-2">⚠️ 警告</h4>
              <ul className="text-sm text-amber-700 space-y-1">
                {agentResult.warnings?.map((warning, i) => (
                  <li key={i}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 错误信息 */}
          {Boolean(agentResult.errors && agentResult.errors.length > 0) && (
            <div className="p-4 rounded-xl border border-red-200 bg-red-50">
              <h4 className="text-xs font-medium text-red-800 mb-2">❌ 错误</h4>
              <ul className="text-sm text-red-700 space-y-1">
                {agentResult.errors?.map((err, i) => (
                  <li key={i}>• {err}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 建议的下一步操作 */}
          {Boolean(agentResult.next_actions && agentResult.next_actions.length > 0) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-xs font-medium text-[#8A8A8A] mb-2">💡 建议的下一步</h4>
              <ul className="text-sm text-[#333] space-y-1">
                {agentResult.next_actions?.map((action, i) => (
                  <li key={i}>• {action}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Agent 成功 → 结构化展示 */}
          {agentResult.ok && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-pink-500" />
                <h4 className="text-sm font-medium">Agent 生成结果</h4>
              </div>
              <StructuredOutput output={agentResult.structured_output || agentResult.output} />
            </div>
          )}

          {/* Agent 失败 → 显示错误 + fallback 按钮 */}
          {!agentResult.ok && (
            <div className="p-5 rounded-xl border border-amber-200 bg-amber-50 space-y-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <h4 className="text-sm font-medium text-amber-800">
                  {agentResult.blocked_by_governance
                    ? "Governance 拦截"
                    : agentUnavailable
                      ? "Marketing Agent 未启用或执行失败"
                      : "Agent 执行未成功"}
                </h4>
              </div>
              {/* 显示后端返回的 error / message / classification.reason */}
              <p className="text-xs text-amber-700">
                {agentResult.message || agentResult.error || agentResult.classification?.reason || "未知错误"}
              </p>
              {/* Governance 拦截时显示澄清问题 */}
              {agentResult.blocked_by_governance && agentResult.classification?.clarification_questions && agentResult.classification.clarification_questions.length > 0 && (
                <ul className="text-xs text-amber-600 list-disc pl-4 space-y-0.5">
                  {agentResult.classification.clarification_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              )}
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
          {Boolean((agentResult.structured_output || agentResult.output) &&
           Object.keys(agentResult.structured_output || agentResult.output).length > 0) && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setShowRawJson(!showRawJson)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">原始 JSON</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showRawJson ? "rotate-180" : ""}`} />
              </button>
              {showRawJson && (
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
                {copied ? "已复制" : "复制文案"}
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
    </div>
  )
}

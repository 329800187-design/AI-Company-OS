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

// ── 复杂字段渲染辅助 ────────────────────────────────────────────────────────

function renderComplexValue(value: unknown): React.ReactNode {
  if (value == null) return null
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <p className="text-sm text-[#333] leading-relaxed">{String(value)}</p>
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="text-xs text-[#8A8A8A]">无</p>
    // 数组元素是简单值 → badge 展示
    if (value.every((item) => typeof item === "string" || typeof item === "number")) {
      return (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item, i) => (
            <Badge key={i} variant="secondary" className="text-xs">{String(item)}</Badge>
          ))}
        </div>
      )
    }
    // 数组元素是对象 → 卡片列表
    return (
      <div className="space-y-2">
        {value.map((item, i) => (
          <div key={i} className="p-2.5 rounded-lg bg-[#F9F9F9] border border-[#E5E5E5] text-sm text-[#333]">
            {typeof item === "object" && item !== null ? (
              <div className="space-y-1">
                {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="text-xs text-[#8A8A8A] min-w-[80px] shrink-0">{k}:</span>
                    <span className="text-xs">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-xs">{String(item)}</span>
            )}
          </div>
        ))}
      </div>
    )
  }
  // 对象 → 键值对展示
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return <p className="text-xs text-[#8A8A8A]">空</p>
    return (
      <div className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 text-sm">
            <span className="text-xs text-[#8A8A8A] min-w-[80px] shrink-0 font-medium">{k}</span>
            <span className="text-[#333]">
              {typeof v === "object" ? (
                <pre className="whitespace-pre-wrap text-xs bg-[#F4F3EF] rounded p-2 max-h-[120px] overflow-auto">
                  {JSON.stringify(v, null, 2)}
                </pre>
              ) : (
                String(v)
              )}
            </span>
          </div>
        ))}
      </div>
    )
  }
  return <p className="text-sm text-[#333] leading-relaxed">{String(value)}</p>
}

function formatCopyValue(value: unknown): string {
  if (value == null) return ""
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  return JSON.stringify(value, null, 2)
}

/** 从 sections 中按 task_type 选择展示字段 */
function buildSections(output: Record<string, unknown>): { label: string; value: unknown; isList?: boolean; complex?: boolean }[] {
  const sections: { label: string; value: unknown; isList?: boolean; complex?: boolean }[] = []

  // ── seo_article ────────────────────────────────────────────────────────────
  if (output.meta_title != null) sections.push({ label: "SEO 标题 (Title)", value: output.meta_title })
  if (output.meta_description != null) sections.push({ label: "Meta 描述", value: output.meta_description })
  if (output.h1 != null) sections.push({ label: "H1 标题", value: output.h1 })
  if (output.content != null && output.content !== output.body) sections.push({ label: "正文内容", value: output.content })
  if (output.keywords != null) {
    sections.push({
      label: "关键词",
      value: output.keywords,
      isList: Array.isArray(output.keywords),
      complex: !Array.isArray(output.keywords),
    })
  }
  if (output.estimated_read_time != null) sections.push({ label: "预计阅读时长", value: output.estimated_read_time })
  if (Array.isArray(output.internal_link_suggestions) && output.internal_link_suggestions.length > 0) {
    sections.push({ label: "内链建议", value: output.internal_link_suggestions, complex: true })
  }

  // ── email_campaign ─────────────────────────────────────────────────────────
  if (output.subject != null) sections.push({ label: "邮件主题", value: output.subject })
  if (output.preheader != null) sections.push({ label: "预览文本", value: output.preheader })
  if (output.body != null && !sections.some((s) => s.value === output.body)) sections.push({ label: "邮件正文", value: output.body })
  if (output.plain_text != null) sections.push({ label: "纯文本版本", value: output.plain_text })
  if (output.cta_button != null) sections.push({ label: "CTA 按钮文案", value: output.cta_button })
  if (output.cta_link != null) sections.push({ label: "CTA 链接", value: output.cta_link })
  if (output.send_timing != null) sections.push({ label: "发送时机建议", value: output.send_timing })

  // ── brand_strategy ─────────────────────────────────────────────────────────
  if (output.brand_positioning != null) sections.push({ label: "品牌定位", value: output.brand_positioning })
  if (output.target_audience != null) sections.push({ label: "目标受众", value: output.target_audience, complex: typeof output.target_audience === "object" })
  if (output.differentiation != null) sections.push({ label: "差异化优势", value: output.differentiation })
  if (output.brand_voice != null) sections.push({ label: "品牌调性", value: output.brand_voice, complex: typeof output.brand_voice === "object" })
  if (output.visual_direction != null) sections.push({ label: "视觉方向", value: output.visual_direction })
  if (Array.isArray(output.tagline_options) && output.tagline_options.length > 0) {
    sections.push({ label: "Slogan 候选", value: output.tagline_options, isList: true })
  }
  if (output.competitor_insight != null) sections.push({ label: "竞品洞察", value: output.competitor_insight })

  // ── campaign_plan ──────────────────────────────────────────────────────────
  if (output.campaign_name != null) sections.push({ label: "活动名称", value: output.campaign_name })
  if (output.goal != null && !sections.some((s) => s.value === output.goal)) sections.push({ label: "活动目标", value: output.goal })
  if (Array.isArray(output.target_segments) && output.target_segments.length > 0) {
    sections.push({ label: "目标人群", value: output.target_segments, isList: true })
  }
  if (output.key_message != null) sections.push({ label: "核心信息", value: output.key_message })
  if (Array.isArray(output.channels) && output.channels.length > 0) {
    sections.push({ label: "投放渠道", value: output.channels, isList: true })
  }
  if (output.timeline != null) sections.push({ label: "时间规划", value: output.timeline, complex: true })
  if (Array.isArray(output.kpis) && output.kpis.length > 0) {
    sections.push({ label: "KPI 指标", value: output.kpis, complex: true })
  }
  if (output.budget_suggestion != null) sections.push({ label: "预算建议", value: output.budget_suggestion, complex: true })
  if (Array.isArray(output.risks) && output.risks.length > 0) {
    sections.push({ label: "风险提示", value: output.risks, complex: true })
  }

  // ── social_media ───────────────────────────────────────────────────────────
  if (output.platform != null && !sections.some((s) => s.value === output.platform)) {
    sections.push({ label: "目标平台", value: output.platform })
  }
  if (output.content != null && !sections.some((s) => s.value === output.content)) {
    sections.push({ label: "文案内容", value: output.content })
  }
  if (Array.isArray(output.hashtags) && output.hashtags.length > 0) {
    sections.push({ label: "标签", value: output.hashtags, isList: true })
  }
  if (output.best_posting_time != null) sections.push({ label: "推荐发布时间", value: output.best_posting_time })
  if (Array.isArray(output.engagement_hooks) && output.engagement_hooks.length > 0) {
    sections.push({ label: "互动钩子", value: output.engagement_hooks, isList: true })
  }
  if (output.media_suggestion != null) sections.push({ label: "媒体建议", value: output.media_suggestion })

  // ── copywriting (通用文案) ─────────────────────────────────────────────────
  if (output.headline != null && !sections.some((s) => s.value === output.headline)) {
    sections.push({ label: "标题", value: output.headline })
  }
  if (output.subheadline != null) sections.push({ label: "副标题", value: output.subheadline })
  if (output.body != null && !sections.some((s) => s.value === output.body)) {
    sections.push({ label: "正文", value: output.body })
  }
  if (output.cta != null && !sections.some((s) => s.value === output.cta)) {
    sections.push({ label: "行动号召 (CTA)", value: output.cta })
  }
  if (Array.isArray(output.variations) && output.variations.length > 0) {
    sections.push({ label: "备选方案", value: output.variations, isList: true })
  }
  if (output.tone != null && !sections.some((s) => s.value === output.tone)) {
    sections.push({ label: "语气风格", value: output.tone })
  }

  return sections
}

// ── 结构化字段展示组件 ──────────────────────────────────────────────────────

function StructuredOutput({ output }: { output: Record<string, unknown> }) {
  const sections = buildSections(output)

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
      {sections.map(({ label, value, isList, complex }) => (
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
          ) : complex || (typeof value === "object" && value !== null) ? (
            renderComplexValue(value)
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

  // 从 agent output 中提取可复制的纯文本（覆盖所有 task_type）
  const getCopyText = (): string => {
    const output = agentResult?.structured_output || agentResult?.output
    if (agentResult?.ok && output) {
      const o = output
      const parts: string[] = []
      // 通用字段
      if (o.headline) parts.push(String(o.headline))
      if (o.subheadline) parts.push(String(o.subheadline))
      if (o.body) parts.push(String(o.body))
      if (o.content) parts.push(String(o.content))
      if (o.cta) parts.push(String(o.cta))
      // seo_article
      if (o.meta_title) parts.push(`Title: ${String(o.meta_title)}`)
      if (o.meta_description) parts.push(`Description: ${String(o.meta_description)}`)
      if (o.h1) parts.push(`H1: ${String(o.h1)}`)
      if (o.estimated_read_time) parts.push(`阅读时长: ${String(o.estimated_read_time)}`)
      // email_campaign
      if (o.subject) parts.push(`主题: ${String(o.subject)}`)
      if (o.preheader) parts.push(`预览: ${String(o.preheader)}`)
      if (o.plain_text) parts.push(String(o.plain_text))
      if (o.cta_button) parts.push(`CTA: ${String(o.cta_button)}`)
      if (o.cta_link) parts.push(`链接: ${String(o.cta_link)}`)
      // brand_strategy
      if (o.brand_positioning) parts.push(String(o.brand_positioning))
      if (o.target_audience) parts.push(formatCopyValue(o.target_audience))
      if (o.differentiation) parts.push(formatCopyValue(o.differentiation))
      if (o.brand_voice) parts.push(formatCopyValue(o.brand_voice))
      if (o.visual_direction) parts.push(formatCopyValue(o.visual_direction))
      if (o.competitor_insight) parts.push(formatCopyValue(o.competitor_insight))
      // campaign_plan
      if (o.campaign_name) parts.push(`活动: ${String(o.campaign_name)}`)
      if (o.key_message) parts.push(String(o.key_message))
      if (Array.isArray(o.kpis) && o.kpis.length > 0) parts.push(`KPI: ${o.kpis.join(", ")}`)
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

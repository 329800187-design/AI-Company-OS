import { useState } from "react"
import { motion } from "framer-motion"
import {
  Image,
  Sparkles,
  Loader2,
  Copy,
  Check,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  RotateCcw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { SaveToDeliveryButton } from "@/components/features/save-to-delivery-button"

const examples = [
  {
    goal: "帮我为手工耳环生成产品图提示词",
    label: "手工耳环产品图提示词",
  },
  {
    goal: "帮我为手工银饰耳环生成小红书配图提示词",
    label: "手工银饰耳环配图提示词",
  },
  {
    goal: "帮我搭建一个全自动赚钱公司系统",
    label: "自动赚钱系统拦截测试",
  },
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

  // 图片提示词（后端字段名 image_prompt）
  if (output.image_prompt) sections.push({ label: "图片提示词", value: output.image_prompt })
  // 负面提示词
  if (output.negative_prompt) sections.push({ label: "负面提示词", value: output.negative_prompt })
  // 风格
  if (output.style) sections.push({ label: "风格", value: output.style })
  // 宽高比
  if (output.aspect_ratio) sections.push({ label: "宽高比", value: output.aspect_ratio })
  // 主体
  if (output.subject) sections.push({ label: "主体", value: output.subject })
  // 背景
  if (output.background) sections.push({ label: "背景", value: output.background })
  // 构图
  if (output.composition) sections.push({ label: "构图", value: output.composition })
  // 光线
  if (output.lighting) sections.push({ label: "光线", value: output.lighting })
  // 色彩方案
  if (output.color_palette) sections.push({ label: "色彩方案", value: output.color_palette })
  // 使用建议
  if (Array.isArray(output.usage_suggestions) && output.usage_suggestions.length > 0) {
    sections.push({ label: "使用建议", value: output.usage_suggestions, isList: true })
  }
  // 变体
  if (Array.isArray(output.variations) && output.variations.length > 0) {
    sections.push({ label: "变体方案", value: output.variations, isList: true })
  }
  // 限制说明
  if (Array.isArray(output.limitations) && output.limitations.length > 0) {
    sections.push({ label: "限制说明", value: output.limitations, isList: true })
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
                  {typeof item === "object" ? JSON.stringify(item) : String(item)}
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

export default function ImagePage() {
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
  const [showResult, setShowResult] = useState(false)

  const isFallback = agentResult?.metadata?.fallback === true

  // ── Agent 优先执行 ──────────────────────────────────────────────────────

  const handleGenerate = async () => {
    if (!goal.trim()) return
    setIsLoading(true)
    setAgentResult(null)
    setFallbackResult(null)
    setFallbackArtifact(null)
    setError(null)

    try {
      const result = await api.executeAgent("image", {
        goal,
        task_type: "image_generate",
        context: {},
        input: { prompt: goal },
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

  // 从 agent output 中提取可复制的纯文本
  const getCopyText = (): string => {
    if (agentResult?.ok) {
      const o = agentResult.structured_output || agentResult.output
      const parts: string[] = []
      if (o.image_prompt) parts.push(String(o.image_prompt))
      if (o.negative_prompt) parts.push(`Negative: ${String(o.negative_prompt)}`)
      if (o.style) parts.push(`Style: ${String(o.style)}`)
      if (o.aspect_ratio) parts.push(`Aspect: ${String(o.aspect_ratio)}`)
      if (o.composition) parts.push(`Composition: ${String(o.composition)}`)
      if (o.lighting) parts.push(`Lighting: ${String(o.lighting)}`)
      if (o.color_palette) parts.push(`Color: ${String(o.color_palette)}`)
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
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
          <Image className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">做图片</h1>
          <p className="text-[#8A8A8A]">
            当前生成<strong>图片提示词包</strong>，不是直接生成图片
          </p>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 rounded-xl border border-blue-500/20 bg-blue-500/5">
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-blue-400 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-400">图片提示词包模式</h3>
            <p className="text-sm text-[#8A8A8A] mt-1">
              系统将为你生成产品图片的提示词（Prompt），包含主图、细节图、场景图、风格关键词、负面提示词等。你需要配合 Midjourney / Stable Diffusion / DALL-E 等图片生成工具使用。
            </p>
          </div>
        </div>
      </div>

      {/* Goal Input */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-3">
        <h3 className="font-semibold">产品描述</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="描述你的产品，比如：手工制作的银饰耳环，适合年轻女性..."
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
          {isLoading ? "正在生成提示词包..." : "生成提示词包"}
        </Button>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2 pt-2">
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
                {copied ? "已复制" : "复制提示词"}
              </Button>
            )}
            {agentResult.ok && (
              <SaveToDeliveryButton
                goal={goal}
                agentId={agentResult.agent_id || "image"}
                agentResult={agentResult as unknown as Record<string, unknown>}
                sourcePage="image"
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
          {isFallback && Boolean(agentResult.metadata?.fallback_reason) && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#666]">
                <p className="font-medium text-yellow mb-1">降级原因</p>
                <p>{String(agentResult.metadata?.fallback_reason)}</p>
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
          {agentResult.ok && Boolean(agentResult.structured_output || agentResult.output) && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-violet-500" />
                <h4 className="text-sm font-medium">图片提示词结果</h4>
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
                  {agentUnavailable
                    ? "Image Agent 未启用或执行失败"
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
          {Boolean((agentResult.structured_output || agentResult.output) &&
           Object.keys(agentResult.structured_output || agentResult.output).length > 0) && (
            <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
              <button
                type="button"
                onClick={() => setShowResult(!showResult)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
              >
                <span className="text-sm font-medium">原始 JSON</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showResult ? "rotate-180" : ""}`} />
              </button>
              {showResult && (
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
                {copied ? "已复制" : "复制提示词"}
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
                <Image className="w-4 h-4" />
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
          <Image className="w-12 h-12 mx-auto text-[#8A8A8A] mb-4" />
          <p className="text-[#8A8A8A]">
            输入产品描述，生成图片提示词包
          </p>
          <p className="text-xs text-[#D4D4D4] mt-2">
            支持 Midjourney / Stable Diffusion / DALL-E 等工具
          </p>
        </div>
      )}
    </div>
  )
}

import { useState } from "react"
import { motion } from "framer-motion"
import { Search, Sparkles, Loader2, CheckCircle2, AlertCircle, ChevronDown, AlertTriangle, Globe, Database } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { SaveToDeliveryButton } from "@/components/features/save-to-delivery-button"

const examples = [
  { goal: "帮我为手工耳环做一份竞品调研简报", label: "手工耳环竞品简报" },
  { goal: "帮我做一份手工耳环市场调研简报", label: "手工耳环市场简报" },
  { goal: "帮我分析手工饰品行业的机会与风险", label: "手工饰品机会风险" },
]

interface ResearchResult {
  ok: boolean
  mode?: string
  agent_id: string
  task_type?: string
  summary?: string
  structured_output?: Record<string, unknown>
  output?: Record<string, unknown>
  artifacts?: string[]
  warnings?: string[]
  errors?: string[]
  error?: string
  next_actions?: string[]
  metadata?: Record<string, unknown>
}

interface ResearchData {
  research_question?: string
  market_summary?: string
  key_findings?: string[]
  competitors?: Array<{ name: string; strength: string; weakness: string; positioning: string }>
  opportunities?: string[]
  risks?: string[]
  recommended_actions?: string[]
  limitations?: string[]
  sources?: string[]
}

export default function ResearchPage() {
  const [query, setQuery] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<ResearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showFullOutput, setShowFullOutput] = useState(false)

  // Governance fallback state
  const [govFallbackLoading, setGovFallbackLoading] = useState(false)
  const [govFallbackResult, setGovFallbackResult] = useState<Record<string, unknown> | null>(null)

  const researchData: ResearchData = (() => {
    if (!result?.structured_output) return {}
    const so = result.structured_output as Record<string, unknown>
    return so as unknown as ResearchData
  })()

  const handleResearch = async () => {
    if (!query.trim()) return
    setIsLoading(true)
    setResult(null)
    setError(null)
    setGovFallbackResult(null)

    try {
      const response = await api.executeAgent("research", {
        goal: query,
        task_type: "research_brief",
        context: { source: "research_page" },
        input: { goal: query },
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : "调研失败")
    } finally {
      setIsLoading(false)
    }
  }

  const handleGovFallback = async () => {
    if (!query.trim()) return
    setGovFallbackLoading(true)
    setError(null)
    try {
      const response = await api.governanceRun(query, "", true)
      setGovFallbackResult(response as unknown as Record<string, unknown>)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Governance fallback 失败")
    } finally {
      setGovFallbackLoading(false)
    }
  }

  const isFallback = result?.metadata?.fallback === true
  const hasWarnings = (result?.warnings?.length ?? 0) > 0
  const hasErrors = (result?.errors?.length ?? 0) > 0

  // Search provider display mapping
  const searchProvider = String(result?.metadata?.search_provider ?? "")
  const searchProviderLabel: Record<string, { label: string; icon: typeof Globe; variant: "success" | "warning" | "outline" }> = {
    MockSearchProvider: { label: "模拟搜索", icon: Database, variant: "warning" },
    SerpAPIProvider: { label: "SerpAPI 实时搜索", icon: Globe, variant: "success" },
    BingSearchProvider: { label: "Bing 实时搜索", icon: Globe, variant: "success" },
  }
  const spInfo = searchProviderLabel[searchProvider]
  const sourcesCount = Array.isArray(result?.structured_output?.sources)
    ? (result.structured_output.sources as string[]).length
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">做调研</h1>
          <p className="text-[#8A8A8A]">竞品分析、市场调研、行业报告</p>
        </div>
      </div>

      {/* Input form */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-4">
        <h3 className="font-semibold">调研内容</h3>
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="描述你想调研的内容，比如：帮我为手工耳环做一份竞品调研简报..."
          className="min-h-[100px]"
        />

        <div className="flex items-center gap-3">
          <Button
            onClick={handleResearch}
            disabled={!query.trim() || isLoading}
            className="gap-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {isLoading ? "正在调研..." : "开始调研"}
          </Button>

          {/* Governance fallback button — explicit only */}
          {result && !result.ok && (
            <Button
              variant="outline"
              onClick={handleGovFallback}
              disabled={govFallbackLoading}
              className="gap-2"
            >
              {govFallbackLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <AlertTriangle className="w-4 h-4" />
              )}
              {govFallbackLoading ? "正在尝试..." : "Governance fallback"}
            </Button>
          )}
        </div>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-[#8A8A8A]">示例:</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setQuery(ex.goal)}
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

      {/* Warnings / Limitations banner */}
      {result && (hasWarnings || isFallback) && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 space-y-2"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow" />
            <h4 className="font-medium text-yellow text-sm">
              {isFallback ? "框架模式 — 非联网真实调研" : "调研限制"}
            </h4>
          </div>
          {result.warnings?.map((w, i) => (
            <p key={i} className="text-xs text-[#666]">• {w}</p>
          ))}
          {researchData.limitations?.map((l, i) => (
            <p key={`lim-${i}`} className="text-xs text-[#666]">• {l}</p>
          ))}
        </motion.div>
      )}

      {/* Errors banner */}
      {result && hasErrors && (
        <div className="p-4 rounded-xl border border-red/20 bg-red/5 space-y-1">
          {result.errors?.map((e, i) => (
            <p key={i} className="text-xs text-red">• {e}</p>
          ))}
        </div>
      )}

      {/* Result */}
      {result && result.ok && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Status bar */}
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white flex flex-wrap items-center gap-3">
            <Badge variant={isFallback ? "warning" : "success"} className="gap-1">
              {isFallback ? (
                <><AlertTriangle className="w-3 h-3" />框架模式</>
              ) : (
                <><CheckCircle2 className="w-3 h-3" />调研完成</>
              )}
            </Badge>
            {result.mode && (
              <Badge variant="outline">模式: {result.mode}</Badge>
            )}
            {result.agent_id && (
              <Badge variant="outline">Agent: {result.agent_id}</Badge>
            )}
            {!!result.metadata?.source && (
              <Badge variant="outline">来源: {String(result.metadata.source)}</Badge>
            )}
            {spInfo && (
              <Badge variant={spInfo.variant} className="gap-1">
                <spInfo.icon className="w-3 h-3" />
                {spInfo.label}
              </Badge>
            )}
            {sourcesCount > 0 && (
              <Badge variant="outline">{sourcesCount} 条来源</Badge>
            )}
            {result.ok && (
              <SaveToDeliveryButton
                goal={query}
                agentId={result.agent_id || "research"}
                agentResult={result as unknown as Record<string, unknown>}
                sourcePage="research"
              />
            )}
          </div>

          {/* Summary */}
          {Boolean(result.summary) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">执行摘要</h4>
              <p className="text-sm text-[#333]">{String(result.summary)}</p>
            </div>
          )}

          {/* 降级原因 */}
          {isFallback && Boolean(result.metadata?.fallback_reason) && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#666]">
                <p className="font-medium text-yellow mb-1">降级原因</p>
                <p>{String(result.metadata?.fallback_reason)}</p>
              </div>
            </div>
          )}

          {/* Research Question */}
          {researchData.research_question && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">调研问题</h4>
              <p className="text-sm text-[#333]">{researchData.research_question}</p>
            </div>
          )}

          {/* Market Summary */}
          {researchData.market_summary && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">市场概况</h4>
              <p className="text-sm text-[#333] leading-relaxed">{researchData.market_summary}</p>
            </div>
          )}

          {/* Key Findings */}
          {researchData.key_findings && researchData.key_findings.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">关键发现</h4>
              <ul className="space-y-1.5">
                {researchData.key_findings.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#333]">
                    <span className="text-orange-500 mt-0.5">•</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Competitors */}
          {researchData.competitors && researchData.competitors.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-3">竞品分析</h4>
              <div className="space-y-3">
                {researchData.competitors.map((c, i) => (
                  <div key={i} className="p-3 rounded-lg bg-[#F4F3EF] border border-border">
                    <div className="font-medium text-sm mb-1">{c.name}</div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-[#666]">
                      <div><span className="font-medium text-green-600">优势:</span> {c.strength}</div>
                      <div><span className="font-medium text-red-500">劣势:</span> {c.weakness}</div>
                      <div><span className="font-medium text-blue-500">定位:</span> {c.positioning}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Opportunities */}
          {researchData.opportunities && researchData.opportunities.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">机会</h4>
              <ul className="space-y-1.5">
                {researchData.opportunities.map((o, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#333]">
                    <span className="text-green-500 mt-0.5">+</span>
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Risks */}
          {researchData.risks && researchData.risks.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">风险</h4>
              <ul className="space-y-1.5">
                {researchData.risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#333]">
                    <span className="text-red-500 mt-0.5">!</span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended Actions */}
          {researchData.recommended_actions && researchData.recommended_actions.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">建议行动</h4>
              <ul className="space-y-1.5">
                {researchData.recommended_actions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#333]">
                    <span className="text-orange-500 mt-0.5">{i + 1}.</span>
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sources */}
          {researchData.sources && researchData.sources.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">信息来源</h4>
              <ul className="space-y-1">
                {researchData.sources.map((s, i) => (
                  <li key={i} className="text-xs text-[#666]">• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Full structured_output (collapsible) */}
          <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setShowFullOutput(!showFullOutput)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
            >
              <span className="text-sm font-medium">完整结构化产出</span>
              <ChevronDown
                className={`w-4 h-4 transition-transform ${showFullOutput ? "rotate-180" : ""}`}
              />
            </button>
            {showFullOutput && (
              <div className="px-4 pb-4">
                <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[400px] whitespace-pre-wrap">
                  {JSON.stringify(result.structured_output ?? result.output ?? null, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Governance fallback result */}
      {govFallbackResult && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="p-4 rounded-xl border border-blue-200 bg-blue-50 flex items-center gap-3">
            <Badge variant="outline" className="gap-1">
              <AlertTriangle className="w-3 h-3" />
              Governance Fallback
            </Badge>
            <span className="text-xs text-[#666]">以下结果来自 Governance 系统（非 Agent-first 链路）</span>
          </div>
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
            <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[400px] whitespace-pre-wrap">
              {JSON.stringify(govFallbackResult, null, 2)}
            </pre>
          </div>
        </motion.div>
      )}
    </div>
  )
}

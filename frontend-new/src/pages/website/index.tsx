import { useState } from "react"
import { motion } from "framer-motion"
import { Globe, Sparkles, Loader2, AlertCircle, CheckCircle2, ChevronDown, FileText, Eye, Search, Palette } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { SaveToDeliveryButton } from "@/components/features/save-to-delivery-button"

const examples = [
  { goal: "帮我为手工耳环生成一个落地页文案", label: "手工耳环落地页" },
  { goal: "帮我为手工耳环生成一个产品展示页文案", label: "产品展示页文案" },
  { goal: "帮我搭建一个全自动赚钱公司系统", label: "自动赚钱系统拦截测试" },
]

interface WebsiteAgentResult {
  ok: boolean
  mode?: string
  agent_id: string
  task_type?: string
  summary?: string
  structured_output?: {
    page_goal?: string
    target_audience?: string
    hero?: {
      headline?: string
      subheadline?: string
      primary_cta?: string
    }
    sections?: Array<{
      title?: string
      content?: string
      cta?: string | null
    }>
    ctas?: {
      primary?: string
      secondary?: string
      exit_intent?: string
    }
    trust_elements?: string[]
    seo?: {
      title?: string
      description?: string
      keywords?: string[]
    }
    design_direction?: string
    risks?: string[]
    recommendations?: string[]
    assumptions?: string[]
    limitations?: string[]
    content_type?: string
  }
  output?: Record<string, unknown>
  artifacts?: string[]
  warnings?: string[]
  errors?: string[]
  error?: string
  metadata?: Record<string, unknown>
}

export default function WebsitePage() {
  const [description, setDescription] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<WebsiteAgentResult | null>(null)
  const [showResult, setShowResult] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    if (!description.trim()) return
    setIsLoading(true)
    setResult(null)
    setError(null)

    try {
      const response = await api.executeAgent("website", {
        goal: description,
        task_type: "website_draft",
        context: {},
        input: { goal: description },
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败")
    } finally {
      setIsLoading(false)
    }
  }

  const isFallback = result?.metadata?.fallback === true
  const hasWarnings = (result?.warnings?.length ?? 0) > 0
  const hasErrors = (result?.errors?.length ?? 0) > 0
  const output = result?.structured_output

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
          <Globe className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">建网站</h1>
          <p className="text-[#8A8A8A]">落地页、产品页、预约页，一句话搞定</p>
        </div>
      </div>

      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-3">网站描述</h3>
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="描述你想要的网站，比如：一个手工耳环的产品展示页，要有产品图片、价格、购买按钮..."
          className="min-h-[120px]"
        />
        <Button
          onClick={handleGenerate}
          disabled={!description.trim() || isLoading}
          variant="default"
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "正在生成..." : "生成落地页文案"}
        </Button>

        {/* Example buttons */}
        <div className="flex flex-wrap gap-2 mt-4">
          <span className="text-xs text-[#8A8A8A]">示例:</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setDescription(ex.goal)}
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
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          {/* Status bar */}
          <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white flex flex-wrap items-center gap-3">
            {result.ok ? (
              <Badge variant="success" className="gap-1">
                <CheckCircle2 className="w-3 h-3" />
                生成成功
              </Badge>
            ) : (
              <Badge variant="destructive" className="gap-1">
                <AlertCircle className="w-3 h-3" />
                生成失败
              </Badge>
            )}
            {result.mode && (
              <Badge variant="outline">模式: {result.mode}</Badge>
            )}
            {!!result.metadata?.source && (
              <Badge variant="outline">来源: {String(result.metadata.source)}</Badge>
            )}
            {isFallback && (
              <Badge variant="warning">模板草稿</Badge>
            )}
            {result.ok && !isFallback && (
              <SaveToDeliveryButton
                goal={description}
                agentId={result.agent_id || "website"}
                agentResult={result as unknown as Record<string, unknown>}
                sourcePage="website"
              />
            )}
          </div>

          {/* Fallback warning */}
          {isFallback && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#666]">
                <p className="font-medium text-yellow mb-1">当前为草稿/模板生成，未部署网站</p>
                <p>配置 AI API Key 后可获得定制化落地页内容。</p>
              </div>
            </div>
          )}

          {/* Warnings */}
          {Boolean(hasWarnings) && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="w-4 h-4 text-yellow" />
                <span className="text-sm font-medium text-yellow">警告</span>
              </div>
              <ul className="text-sm text-[#666] space-y-1">
                {result.warnings!.map((w, i) => (
                  <li key={i}>• {String(w)}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Errors */}
          {hasErrors && (
            <div className="p-4 rounded-xl border border-red/20 bg-red/5">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="w-4 h-4 text-red" />
                <span className="text-sm font-medium text-red">错误</span>
              </div>
              <ul className="text-sm text-[#666] space-y-1">
                {result.errors!.map((e, i) => (
                  <li key={i}>• {e}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Summary */}
          {Boolean(result.summary) && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">执行摘要</h4>
              <p className="text-sm text-[#333]">{result.summary}</p>
            </div>
          )}

          {/* 降级原因 */}
          {isFallback && Boolean(result.metadata?.fallback_reason) && (
            <div className="p-4 rounded-xl border border-yellow/30 bg-yellow/5 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#666]">
                <p className="font-medium text-yellow mb-1">降级原因</p>
                <p>{String(result.metadata?.fallback_reason)}</p>
              </div>
            </div>
          )}

          {/* Page Goal */}
          {output?.page_goal && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <Eye className="w-4 h-4" />
                <h4 className="text-sm font-medium">页面目标</h4>
              </div>
              <p className="text-sm text-[#333] leading-relaxed">{output.page_goal}</p>
            </div>
          )}

          {/* Target Audience */}
          {output?.target_audience && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">目标受众</h4>
              <p className="text-sm text-[#333] leading-relaxed">{output.target_audience}</p>
            </div>
          )}

          {/* Hero Section */}
          {output?.hero && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <Eye className="w-4 h-4" />
                <h4 className="text-sm font-medium">Hero 区域</h4>
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-[#8A8A8A]">Headline:</span>
                  <p className="text-lg font-bold text-[#0B0B0B]">{output.hero.headline}</p>
                </div>
                <div>
                  <span className="text-xs text-[#8A8A8A]">Subheadline:</span>
                  <p className="text-sm text-[#666]">{output.hero.subheadline}</p>
                </div>
                <div>
                  <span className="text-xs text-[#8A8A8A]">CTA:</span>
                  <Badge variant="default" className="ml-2">{output.hero.primary_cta}</Badge>
                </div>
              </div>
            </div>
          )}

          {/* Sections */}
          {output?.sections && output.sections.length > 0 && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4" />
                <h4 className="text-sm font-medium">内容板块 ({output.sections.length})</h4>
              </div>
              <div className="space-y-4">
                {output.sections.map((section, i) => (
                  <div key={i} className="p-3 rounded-lg bg-[#F9F9F9] border border-[#E5E5E5]">
                    <h5 className="font-medium text-sm mb-1">{section.title}</h5>
                    <p className="text-sm text-[#666]">{section.content}</p>
                    {section.cta && (
                      <Badge variant="outline" className="mt-2">{section.cta}</Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SEO */}
          {output?.seo && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <Search className="w-4 h-4" />
                <h4 className="text-sm font-medium">SEO 信息</h4>
              </div>
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-[#8A8A8A]">Title:</span>
                  <p className="text-[#333]">{output.seo.title}</p>
                </div>
                <div>
                  <span className="text-[#8A8A8A]">Description:</span>
                  <p className="text-[#333]">{output.seo.description}</p>
                </div>
                {output.seo.keywords && output.seo.keywords.length > 0 && (
                  <div>
                    <span className="text-[#8A8A8A]">Keywords:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {output.seo.keywords.map((kw, i) => (
                        <Badge key={i} variant="outline" className="text-xs">{kw}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* CTAs */}
          {output?.ctas && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-3">行动号召</h4>
              <div className="space-y-2 text-sm">
                {output.ctas.primary && (
                  <div><span className="text-[#8A8A8A]">主要 CTA:</span> <Badge variant="default">{output.ctas.primary}</Badge></div>
                )}
                {output.ctas.secondary && (
                  <div><span className="text-[#8A8A8A]">次要 CTA:</span> <Badge variant="outline">{output.ctas.secondary}</Badge></div>
                )}
                {output.ctas.exit_intent && (
                  <div><span className="text-[#8A8A8A]">退出弹窗:</span> <Badge variant="outline">{output.ctas.exit_intent}</Badge></div>
                )}
              </div>
            </div>
          )}

          {/* Trust Elements */}
          {output?.trust_elements && output.trust_elements.length > 0 && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">信任元素</h4>
              <div className="flex flex-wrap gap-1.5">
                {output.trust_elements.map((t, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">{t}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Design Direction */}
          {output?.design_direction && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-2 mb-3">
                <Palette className="w-4 h-4" />
                <h4 className="text-sm font-medium">设计方向</h4>
              </div>
              <p className="text-sm text-[#666] whitespace-pre-wrap">{output.design_direction}</p>
            </div>
          )}

          {/* Risks */}
          {output?.risks && output.risks.length > 0 && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">⚠️ 风险</h4>
              <ul className="text-sm text-[#333] space-y-1">
                {output.risks.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {output?.recommendations && output.recommendations.length > 0 && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">💡 建议</h4>
              <ul className="text-sm text-[#333] space-y-1">
                {output.recommendations.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Assumptions */}
          {output?.assumptions && output.assumptions.length > 0 && (
            <div className="p-5 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">假设前提</h4>
              <ul className="text-sm text-[#666] space-y-1">
                {output.assumptions.map((a, i) => (
                  <li key={i}>• {a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Limitations */}
          {output?.limitations && output.limitations.length > 0 && (
            <div className="p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <h4 className="text-sm font-medium mb-2">限制说明</h4>
              <ul className="text-sm text-[#8A8A8A] space-y-1">
                {output.limitations.map((l, i) => (
                  <li key={i}>• {l}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Full result (collapsible) */}
          <div className="rounded-xl border border-[#E5E5E5] bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setShowResult(!showResult)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-[#F9F9F9] transition-colors"
            >
              <span className="text-sm font-medium">完整结果 JSON</span>
              <ChevronDown
                className={`w-4 h-4 transition-transform ${showResult ? "rotate-180" : ""}`}
              />
            </button>
            {showResult && (
              <div className="px-4 pb-4">
                <pre className="text-xs text-[#666] bg-[#F4F3EF] rounded-lg p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
                  {JSON.stringify(result ?? null, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Empty State */}
      {!result && !isLoading && (
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white/80 backdrop-blur-sm text-center py-12">
          <Globe className="w-12 h-12 mx-auto text-[#8A8A8A] mb-4" />
          <p className="text-[#8A8A8A]">描述你想要的网站，AI 帮你生成落地页文案</p>
        </div>
      )}
    </div>
  )
}

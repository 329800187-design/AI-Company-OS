import { useState } from "react"
import { motion } from "framer-motion"
import { Search, Sparkles, Loader2, Globe, TrendingUp, Users, FileText, CheckCircle2, AlertCircle, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

const researchTypes = [
  { id: "competitor", label: "竞品分析", icon: Globe },
  { id: "market", label: "市场调研", icon: TrendingUp },
  { id: "user", label: "用户画像", icon: Users },
  { id: "industry", label: "行业报告", icon: FileText },
]

interface PipelineResult {
  ok: boolean
  task_type: string
  used_web_search: boolean
  search_mode?: string
  used_tools: string[]
  sources: Array<{ title: string; url: string; summary: string }>
  analysis: string
  final_answer: string
  qa: { passed: boolean; score: number; problems: string[]; suggestions: string[] }
  confidence: number
  warnings: string[]
}

export default function ResearchPage() {
  const [type, setType] = useState("competitor")
  const [query, setQuery] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<PipelineResult | null>(null)

  const handleResearch = async () => {
    if (!query.trim()) return
    setIsLoading(true)
    setResult(null)

    try {
      const typeLabel = researchTypes.find((t) => t.id === type)?.label || "调研"
      const response = await api.executePipeline(
        `请进行${typeLabel}：${query}`,
        { research_type: type }
      )
      setResult(response)
    } catch (error) {
      console.error("Research failed:", error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">做调研</h1>
          <p className="text-muted-foreground">竞品分析、市场调研、行业报告</p>
        </div>
      </div>

      <GlowCard>
        <h3 className="font-semibold mb-3">调研类型</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {researchTypes.map((t) => (
            <Button
              key={t.id}
              variant={type === t.id ? "default" : "outline"}
              onClick={() => setType(t.id)}
              className="gap-2"
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </Button>
          ))}
        </div>
      </GlowCard>

      <GlowCard>
        <h3 className="font-semibold mb-3">调研内容</h3>
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="描述你想调研的内容，比如：分析竞品的价格和特点..."
          className="min-h-[100px]"
        />
        <Button
          onClick={handleResearch}
          disabled={!query.trim() || isLoading}
          variant="glow"
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "正在联网调研..." : "开始调研"}
        </Button>
      </GlowCard>

      {/* 结果展示 */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* 可信度和来源 */}
          <GlowCard>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">调研报告</h3>
              <div className="flex items-center gap-2">
                {result.search_mode === "mock" ? (
                  <Badge variant="warning" className="gap-1">
                    <AlertCircle className="w-3 h-3" />
                    模拟搜索
                  </Badge>
                ) : result.search_mode === "none" ? (
                  <Badge variant="warning" className="gap-1">
                    <AlertCircle className="w-3 h-3" />
                    未联网
                  </Badge>
                ) : result.used_web_search ? (
                  <Badge variant="success" className="gap-1">
                    <Globe className="w-3 h-3" />
                    已联网
                  </Badge>
                ) : (
                  <Badge variant="warning" className="gap-1">
                    <AlertCircle className="w-3 h-3" />
                    未联网
                  </Badge>
                )}
                <Badge variant="info">
                  可信度: {Math.round(result.confidence * 100)}%
                </Badge>
              </div>
            </div>

            {/* QA 状态 */}
            {result.qa && (
              <div className={`flex items-center gap-2 p-3 rounded-lg mb-4 ${
                result.qa.passed ? "bg-green/10" : result.qa.score >= 60 ? "bg-yellow/10" : "bg-red/10"
              }`}>
                {result.qa.passed ? (
                  <CheckCircle2 className="w-5 h-5 text-green" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-yellow" />
                )}
                <span className="text-sm">
                  QA 审核: {result.qa.score} 分
                  {!result.qa.passed && result.qa.score >= 60 && " - 建议人工复查"}
                </span>
              </div>
            )}

            {/* 分析结果 */}
            {result.analysis && (
              <div className="mb-4">
                <h4 className="text-sm font-medium mb-2">市场分析</h4>
                <div className="p-4 rounded-lg bg-background border border-border whitespace-pre-wrap text-sm">
                  {result.analysis}
                </div>
              </div>
            )}

            {/* 最终结果 */}
            <div>
              <h4 className="text-sm font-medium mb-2">调研结论</h4>
              <div className="p-4 rounded-lg bg-background border border-border whitespace-pre-wrap text-sm">
                {result.final_answer}
              </div>
            </div>

            {/* 来源列表 */}
            {result.sources && result.sources.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">信息来源 ({result.sources.length})</h4>
                <div className="space-y-2">
                  {result.sources.map((source, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-background border border-border">
                      <ExternalLink className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <a href={source.url} target="_blank" rel="noopener noreferrer"
                           className="text-sm font-medium text-primary hover:underline truncate block">
                          {source.title}
                        </a>
                        {source.summary && (
                          <p className="text-xs text-muted-foreground mt-1">{source.summary}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 使用的 Agent */}
            {result.used_tools && result.used_tools.length > 0 && (
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">协作 Agent:</span>
                {result.used_tools.map((agent, i) => (
                  <Badge key={i} variant="outline" className="text-xs">{agent}</Badge>
                ))}
              </div>
            )}

            {/* 警告 */}
            {result.warnings && result.warnings.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-yellow/10 border border-yellow/20">
                {result.warnings.map((warning, i) => (
                  <p key={i} className="text-sm text-yellow flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    {warning}
                  </p>
                ))}
              </div>
            )}
          </GlowCard>
        </motion.div>
      )}
    </div>
  )
}

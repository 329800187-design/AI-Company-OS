import { useState } from "react"
import { motion } from "framer-motion"
import { FileText, Sparkles, Loader2, Copy, Check, Globe, CheckCircle2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

const platforms = [
  { id: "xiaohongshu", label: "小红书", emoji: "📕" },
  { id: "taobao", label: "淘宝", emoji: "🛒" },
  { id: "wechat", label: "朋友圈", emoji: "💬" },
  { id: "douyin", label: "抖音", emoji: "🎵" },
]

interface PipelineResult {
  ok: boolean
  task_type: string
  used_web_search: boolean
  used_tools: string[]
  sources: Array<{ title: string; url: string; summary: string }>
  final_answer: string
  qa: { passed: boolean; score: number; problems: string[]; suggestions: string[] }
  confidence: number
  warnings: string[]
}

export default function MarketingPage() {
  const [platform, setPlatform] = useState("xiaohongshu")
  const [product, setProduct] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    if (!product.trim()) return
    setIsLoading(true)
    setResult(null)

    try {
      const platformLabel = platforms.find((p) => p.id === platform)?.label || platform
      const response = await api.executePipeline(
        `帮我写一条${platformLabel}文案，产品是${product}`,
        { platform, product }
      )
      setResult(response)
    } catch (error) {
      console.error("Marketing failed:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopy = () => {
    if (result?.final_answer) {
      navigator.clipboard.writeText(result.final_answer)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
          <FileText className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">写文案</h1>
          <p className="text-muted-foreground">基于市场分析的专业文案</p>
        </div>
      </div>

      <GlowCard>
        <h3 className="font-semibold mb-3">选择平台</h3>
        <div className="flex flex-wrap gap-2">
          {platforms.map((p) => (
            <Button
              key={p.id}
              variant={platform === p.id ? "default" : "outline"}
              onClick={() => setPlatform(p.id)}
              className="gap-2"
            >
              <span>{p.emoji}</span>
              {p.label}
            </Button>
          ))}
        </div>
      </GlowCard>

      <GlowCard>
        <h3 className="font-semibold mb-3">产品描述</h3>
        <Textarea
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          placeholder="描述你的产品，比如：手工制作的银饰耳环，适合年轻女性..."
          className="min-h-[100px]"
        />
        <Button
          onClick={handleGenerate}
          disabled={!product.trim() || isLoading}
          variant="glow"
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "正在分析市场并生成..." : "生成文案"}
        </Button>
      </GlowCard>

      {/* 结果展示 */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <GlowCard>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">生成结果</h3>
              <div className="flex items-center gap-2">
                {result.used_web_search ? (
                  <Badge variant="success" className="gap-1">
                    <Globe className="w-3 h-3" />
                    已联网调研
                  </Badge>
                ) : (
                  <Badge variant="warning">未联网</Badge>
                )}
                <Badge variant="info">
                  可信度: {Math.round(result.confidence * 100)}%
                </Badge>
                <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2">
                  {copied ? <Check className="w-4 h-4 text-green" /> : <Copy className="w-4 h-4" />}
                  {copied ? "已复制" : "复制"}
                </Button>
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

            {/* 文案内容 */}
            <div className="p-4 rounded-lg bg-background border border-border whitespace-pre-wrap text-sm">
              {result.final_answer}
            </div>

            {/* 来源 */}
            {result.sources && result.sources.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">参考来源</h4>
                <div className="space-y-1">
                  {result.sources.map((source, i) => (
                    <a key={i} href={source.url} target="_blank" rel="noopener noreferrer"
                       className="text-xs text-primary hover:underline block">
                      {source.title}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </GlowCard>
        </motion.div>
      )}
    </div>
  )
}

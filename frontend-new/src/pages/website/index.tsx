import { useState } from "react"
import { motion } from "framer-motion"
import { Globe, Sparkles, Loader2, Copy, Check, AlertCircle, CheckCircle2, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

export default function WebsitePage() {
  const [description, setDescription] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [copied, setCopied] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const handleGenerate = async () => {
    if (!description.trim()) return
    setIsLoading(true)
    setResult(null)

    try {
      const response = await api.executePipeline(
        `请生成一个网站页面：${description}`,
        { task_type: "website" }
      )
      setResult(response)
    } catch (error) {
      console.error("Website generation failed:", error)
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
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
          <Globe className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">建网站</h1>
          <p className="text-muted-foreground">落地页、产品页、预约页，一句话搞定</p>
        </div>
      </div>

      <GlowCard>
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
          variant="glow"
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "正在生成..." : "生成网站"}
        </Button>
      </GlowCard>

      {/* Result */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <GlowCard>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">生成结果</h3>
              <div className="flex items-center gap-2">
                {result.used_web_search ? (
                  <Badge variant="success" className="gap-1">
                    <Globe className="w-3 h-3" />
                    已联网
                  </Badge>
                ) : (
                  <Badge variant="warning">未联网</Badge>
                )}
                <Badge variant="info">
                  可信度: {Math.round((result.confidence || 0) * 100)}%
                </Badge>
              </div>
            </div>

            {/* QA Status */}
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

            {/* Used Tools */}
            {result.used_tools && result.used_tools.length > 0 && (
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs text-muted-foreground">使用工具:</span>
                {result.used_tools.map((tool: string, i: number) => (
                  <Badge key={i} variant="outline" className="text-xs">{tool}</Badge>
                ))}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 mb-4">
              <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2">
                {copied ? <Check className="w-4 h-4 text-green" /> : <Copy className="w-4 h-4" />}
                {copied ? "已复制" : "复制代码"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowPreview(!showPreview)} className="gap-2">
                <ExternalLink className="w-4 h-4" />
                {showPreview ? "隐藏预览" : "预览"}
              </Button>
            </div>

            {/* HTML Code */}
            <div className="rounded-lg bg-background border border-border overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-border">
                <span className="text-xs text-muted-foreground">HTML 代码</span>
              </div>
              <pre className="p-4 overflow-x-auto text-xs max-h-[300px]">
                <code>{result.final_answer}</code>
              </pre>
            </div>

            {/* Preview */}
            {showPreview && result.final_answer && (
              <div className="mt-4 rounded-lg border border-border overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted">
                  <span className="text-xs text-muted-foreground">预览</span>
                </div>
                <iframe
                  srcDoc={result.final_answer}
                  className="w-full h-[400px] bg-white"
                  title="Website Preview"
                />
              </div>
            )}

            {/* Warnings */}
            {result.warnings && result.warnings.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-yellow/10 border border-yellow/20">
                {result.warnings.map((warning: string, i: number) => (
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

      {/* Empty State */}
      {!result && !isLoading && (
        <GlowCard variant="glass" className="text-center py-12">
          <Globe className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">描述你想要的网站，AI 帮你生成</p>
        </GlowCard>
      )}
    </div>
  )
}

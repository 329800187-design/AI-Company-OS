import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Image, Sparkles, Loader2, Download, AlertCircle, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"

interface Capability {
  available: boolean
  installed: boolean
  running: boolean
  models: string[]
  error: string
  fix_hint: string
}

export default function ImagePage() {
  const [prompt, setPrompt] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [capability, setCapability] = useState<Capability | null>(null)
  const [loadingCap, setLoadingCap] = useState(true)

  useEffect(() => {
    checkCapability()
  }, [])

  const checkCapability = async () => {
    setLoadingCap(true)
    try {
      const caps = await fetch("/capabilities").then(r => r.json())
      setCapability(caps.comfyui || null)
    } catch (error) {
      console.error("Failed to check capability:", error)
    } finally {
      setLoadingCap(false)
    }
  }

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setIsLoading(true)
    setResult(null)

    try {
      const response = await fetch("/pipeline/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: `生成图片: ${prompt}` })
      })
      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error("Image generation failed:", error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
          <Image className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">生成图片</h1>
          <p className="text-muted-foreground">产品图、海报、Logo、社交媒体配图</p>
        </div>
      </div>

      {/* Capability Status */}
      {loadingCap ? (
        <GlowCard>
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>检测图片生成工具...</span>
          </div>
        </GlowCard>
      ) : capability?.available ? (
        <GlowCard>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green" />
            <span className="font-medium">ComfyUI 已就绪</span>
            <Badge variant="success">{capability.models.length} 个模型</Badge>
          </div>
        </GlowCard>
      ) : (
        <GlowCard className="border-yellow/50">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow mt-0.5" />
            <div>
              <h3 className="font-medium text-yellow">图片生成服务不可用</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {capability?.error || "未检测到可用的图片生成工具"}
              </p>
              {capability?.fix_hint && (
                <p className="text-sm text-muted-foreground mt-2">
                  修复建议: {capability.fix_hint}
                </p>
              )}
              <Button variant="outline" size="sm" className="mt-3" onClick={checkCapability}>
                重新检测
              </Button>
            </div>
          </div>
        </GlowCard>
      )}

      {/* Input */}
      <GlowCard>
        <h3 className="font-semibold mb-3">图片描述</h3>
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想要的图片，比如：一个简约风格的产品展示图..."
          className="min-h-[100px]"
        />
        <Button
          onClick={handleGenerate}
          disabled={!prompt.trim() || isLoading || !capability?.available}
          variant="glow"
          className="mt-4 w-full"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {isLoading ? "正在生成..." : "生成图片"}
        </Button>
      </GlowCard>

      {/* Result */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <GlowCard>
            {result.ok ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold">生成结果</h3>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Download className="w-4 h-4" />
                    下载
                  </Button>
                </div>
                {result.deliverables?.image_url && (
                  <img src={result.deliverables.image_url} alt="Generated" className="rounded-lg w-full" />
                )}
              </>
            ) : (
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red mt-0.5" />
                <div>
                  <h3 className="font-medium text-red">生成失败</h3>
                  <p className="text-sm text-muted-foreground mt-1">{result.error}</p>
                  {result.warnings?.map((w: string, i: number) => (
                    <p key={i} className="text-sm text-muted-foreground mt-1">{w}</p>
                  ))}
                </div>
              </div>
            )}
          </GlowCard>
        </motion.div>
      )}

      {/* Empty State */}
      {!result && !isLoading && capability?.available && (
        <GlowCard variant="glass" className="text-center py-12">
          <Image className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">输入描述，生成你的专属图片</p>
        </GlowCard>
      )}
    </div>
  )
}

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowRight,
  Loader2,
  FileText,
  Image,
  Search,
  Globe,
  Sparkles,
  Copy,
  Check,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  PenTool,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

interface TemplateDef {
  id: string
  name: string
  description: string
  goal: string
  icon: React.ElementType
  color: string
  category: string
}

const builtinTemplates: TemplateDef[] = [
  {
    id: "copy_pack_xiaohongshu",
    name: "小红书文案包",
    description: "生成小红书种草文案，包含标题方案、目标人群、正文文案、话题标签、行动号召、发布建议",
    goal: "帮我为手工耳环生成小红书种草文案",
    icon: FileText,
    color: "from-orange-500 to-amber-500",
    category: "文案",
  },
  {
    id: "copy_pack_douyin",
    name: "抖音脚本包",
    description: "生成抖音短视频脚本，包含开头钩子、视频分镜、卖点介绍、互动引导、行动号召",
    goal: "帮我为手工耳环生成抖音短视频脚本",
    icon: FileText,
    color: "from-rose-500 to-pink-500",
    category: "文案",
  },
  {
    id: "image_prompt_pack",
    name: "图片提示词包",
    description: "生成产品图片提示词，包含主图、细节图、场景图、风格关键词、负面提示词",
    goal: "帮我为手工耳环生成产品图片提示词",
    icon: Image,
    color: "from-violet-500 to-purple-500",
    category: "图片",
  },
  {
    id: "research_brief",
    name: "调研简报",
    description: "生成调研简报，包含调研目标、目标用户、竞品维度、痛点假设、内容机会、风险提醒",
    goal: "帮我做一份手工耳环的市场调研简报",
    icon: Search,
    color: "from-cyan-500 to-teal-500",
    category: "调研",
  },
  {
    id: "landing_page_copy",
    name: "落地页文案",
    description: "生成落地页文案，包含页面定位、首屏标题、核心卖点、目标用户、CTA文案、FAQ",
    goal: "帮我为手工耳环生成一个落地页文案",
    icon: Globe,
    color: "from-emerald-500 to-green-500",
    category: "网站",
  },
]

type StepStatus = "idle" | "classifying" | "executing" | "fetching_artifact" | "done" | "error"

interface RunState {
  status: StepStatus
  runId?: string
  runStatus?: string
  artifact?: string
  error?: string
  classification?: Record<string, unknown>
  summary?: string
}

export default function TemplatesPage() {
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDef | null>(null)
  const [goal, setGoal] = useState("")
  const [runState, setRunState] = useState<RunState>({ status: "idle" })
  const [copied, setCopied] = useState(false)
  const [expandedResult, setExpandedResult] = useState(false)

  const handleSelectTemplate = (tpl: TemplateDef) => {
    setSelectedTemplate(tpl)
    setGoal(tpl.goal)
    setRunState({ status: "idle" })
    setCopied(false)
    setExpandedResult(false)
  }

  const handleBack = () => {
    setSelectedTemplate(null)
    setGoal("")
    setRunState({ status: "idle" })
    setCopied(false)
    setExpandedResult(false)
  }

  const handleGenerate = async () => {
    if (!goal.trim()) return

    setRunState({ status: "classifying" })

    try {
      // Step 1: Execute governance run
      setRunState((s) => ({ ...s, status: "executing" }))
      const runResult = await api.governanceRun(goal, "", true)

      // Step 2: Check if blocked / needs clarification
      if (runResult.status === "rejected" || runResult.status === "needs_clarification") {
        setRunState({
          status: "error",
          runId: runResult.run_id,
          runStatus: runResult.status,
          error: (runResult.classification as Record<string, unknown>)?.reason as string || "该目标被系统拦截",
          classification: runResult.classification as Record<string, unknown>,
          summary: runResult.summary,
        })
        return
      }

      // Step 3: Fetch artifact
      if (runResult.status === "succeeded" && runResult.run_id) {
        setRunState((s) => ({ ...s, status: "fetching_artifact" }))
        const artifact = await api.governanceArtifact(runResult.run_id)
        setRunState({
          status: "done",
          runId: runResult.run_id,
          runStatus: runResult.status,
          artifact: artifact.content,
          summary: runResult.summary,
        })
      } else {
        setRunState({
          status: "error",
          runId: runResult.run_id,
          runStatus: runResult.status,
          error: runResult.summary || "执行未成功",
        })
      }
    } catch (err) {
      setRunState({
        status: "error",
        error: err instanceof Error ? err.message : "生成失败，请稍后重试",
      })
    }
  }

  const handleCopy = () => {
    if (runState.artifact) {
      navigator.clipboard.writeText(runState.artifact)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // ── Template list view ──────────────────────────────────────────
  if (!selectedTemplate) {
    return (
      <div className="space-y-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3"
        >
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <PenTool className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">场景模板</h1>
            <p className="text-muted-foreground">选择模板，一键生成完整方案</p>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {builtinTemplates.map((tpl, i) => {
            const Icon = tpl.icon
            return (
              <motion.div
                key={tpl.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <div
                  className="h-full p-6 rounded-2xl border border-[#E5E5E5] bg-white hover:border-[#B5B5B5] hover:translate-y-[-2px] transition-all duration-200 cursor-pointer group"
                  onClick={() => handleSelectTemplate(tpl)}
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${tpl.color} flex items-center justify-center shrink-0`}>
                      <Icon className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-[#0B0B0B]">{tpl.name}</h3>
                        <Badge variant="outline" className="text-[10px]">{tpl.category}</Badge>
                      </div>
                      <p className="text-sm text-[#8A8A8A] leading-relaxed">
                        {tpl.description}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-[#D4D4D4] mt-1 group-hover:text-[#8A8A8A] group-hover:translate-x-0.5 transition-all shrink-0" />
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    )
  }

  // ── Template detail / generation view ──────────────────────────
  const Icon = selectedTemplate.icon

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <button
          onClick={handleBack}
          className="w-10 h-10 rounded-xl bg-[#F4F3EF] flex items-center justify-center hover:bg-[#E5E5E5] transition-colors"
        >
          <ArrowRight className="w-5 h-5 rotate-180" />
        </button>
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${selectedTemplate.color} flex items-center justify-center`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">{selectedTemplate.name}</h1>
          <p className="text-muted-foreground">{selectedTemplate.description}</p>
        </div>
      </motion.div>

      {/* Goal input */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white space-y-4"
      >
        <h3 className="font-semibold">任务描述</h3>
        <Textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="描述你想生成的内容，例如：帮我为手工耳环生成小红书种草文案"
          className="min-h-[100px] text-base bg-[#F4F3EF] border-[#E5E5E5] rounded-xl"
        />
        <Button
          onClick={handleGenerate}
          disabled={!goal.trim() || runState.status === "executing" || runState.status === "fetching_artifact"}
          className="w-full gap-2"
        >
          {runState.status === "executing" || runState.status === "fetching_artifact" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {runState.status === "executing"
            ? "正在生成..."
            : runState.status === "fetching_artifact"
            ? "正在获取产物..."
            : "生成产物"}
        </Button>
      </motion.div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {/* Error state */}
        {runState.status === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="p-6 rounded-2xl border border-red/30 bg-red/5 space-y-3"
          >
            <div className="flex items-center gap-2 text-red">
              <AlertCircle className="w-5 h-5" />
              <h3 className="font-semibold">生成失败</h3>
            </div>
            <p className="text-sm text-red/80">{runState.error}</p>
            {runState.classification && (
              <div className="mt-2">
                <button
                  onClick={() => setExpandedResult(!expandedResult)}
                  className="flex items-center gap-1 text-xs text-red/60 hover:text-red/80"
                >
                  {expandedResult ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  查看分类详情
                </button>
                {expandedResult && (
                  <pre className="mt-2 text-xs text-red/70 bg-red/10 p-3 rounded-lg overflow-x-auto">
                    {JSON.stringify(runState.classification, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* Artifact result */}
        {runState.status === "done" && runState.artifact && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            {/* Summary */}
            {runState.summary && (
              <div className="p-4 rounded-2xl border border-green-200 bg-green-50">
                <p className="text-sm text-green-700">{runState.summary}</p>
              </div>
            )}

            {/* Artifact content */}
            <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">生成结果</h3>
                <div className="flex items-center gap-2">
                  <Badge variant="success" className="gap-1">
                    <Check className="w-3 h-3" />
                    已完成
                  </Badge>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopy}
                    className="gap-1"
                  >
                    {copied ? <Check className="w-4 h-4 text-green" /> : <Copy className="w-4 h-4" />}
                    {copied ? "已复制" : "复制"}
                  </Button>
                </div>
              </div>
              <div className="rounded-xl bg-[#F4F3EF] border border-border p-4 max-h-[600px] overflow-auto">
                <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed text-[#333]">
                  {runState.artifact}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

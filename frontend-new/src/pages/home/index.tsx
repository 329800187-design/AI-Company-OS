import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  FileText,
  Image,
  BarChart3,
  Search,
  Globe,
  ArrowRight,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Zap,
  Shield,
  Package,
} from "lucide-react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useAppStore } from "@/stores/app"
import { api } from "@/api/client"

const AGENT_COLORS: Record<string, string> = {
  marketing: "bg-blue-100 text-blue-800",
  image: "bg-purple-100 text-purple-800",
  data: "bg-green-100 text-green-800",
  research: "bg-amber-100 text-amber-800",
  website: "bg-cyan-100 text-cyan-800",
}

const scenes = [
  {
    id: "marketing",
    title: "写文案",
    desc: "通知、说明和方案表达，一键生成",
    icon: FileText,
  },
  {
    id: "image",
    title: "做图片",
    desc: "围绕交付目标生成图片与素材方向",
    icon: Image,
  },
  {
    id: "data",
    title: "看数据",
    desc: "上传表格，自动分析趋势与关键指标",
    icon: BarChart3,
  },
  {
    id: "research",
    title: "做调研",
    desc: "整理背景、对比选择、形成决策依据",
    icon: Search,
  },
  {
    id: "website",
    title: "建网站",
    desc: "从业务目标到页面结构与内容方案",
    icon: Globe,
  },
]

const quickPrompts = [
  "为新服务设计客户入职流程",
  "梳理本季度经营复盘的关键结论",
  "分析近期运营指标并提出行动建议",
  "制定下一次客户沟通计划",
]

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.2 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.23, 1, 0.32, 1] as const } },
}

export default function HomePage() {
  const [input, setInput] = useState("")
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)
  const [recentMissions, setRecentMissions] = useState<Array<{ mission_id: string; goal: string; status: string; created_at: string }>>([])
  const [recentDeliveries, setRecentDeliveries] = useState<Array<{ task_id: string; goal: string; agent_id: string; artifact_type: string; created_at: string }>>([])
  const [systemOk, setSystemOk] = useState<boolean | null>(null)

  useEffect(() => {
    api.listMissions(5, 0).then(res => setRecentMissions(res.missions)).catch(() => {})
    api.listMiniDeliveryTasks({ limit: 5 }).then(res => setRecentDeliveries(res.tasks)).catch(() => {})
    api.healthCheck().then(() => setSystemOk(true)).catch(() => setSystemOk(false))
  }, [])

  const handleSend = () => {
    if (!input.trim()) return
    setInput("")
    setCurrentPage("boss")
  }

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
        className="text-center pt-8 pb-2"
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="inline-block mb-6"
        >
          <span className="inline-block px-3 py-1 rounded-full border border-[#E5E5E5] text-[11px] text-[#8A8A8A] tracking-wider">
            AI Company OS
          </span>
        </motion.div>

        <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-[#0B0B0B] leading-[0.95] mb-4">
          你好
        </h1>

        <p className="text-lg text-[#8A8A8A] max-w-md mx-auto">
          告诉我想推进的业务目标，我来协同完成
        </p>
      </motion.div>

      {/* Quick Input */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="max-w-2xl mx-auto"
      >
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="描述目标、已有背景和期望交付物..."
              className="min-h-[70px] text-base bg-[#F4F3EF] border-[#E5E5E5] rounded-xl"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />
            <Button
              onClick={handleSend}
              className="self-end px-6 rounded-xl"
            >
              发送
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>

          {/* Quick prompts */}
          <div className="flex flex-wrap gap-2 mt-4">
            {quickPrompts.map((prompt, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + i * 0.08 }}
                onClick={() => setInput(prompt)}
                className="px-3 py-1.5 text-xs rounded-full border border-[#E5E5E5] text-[#8A8A8A] hover:text-[#0B0B0B] hover:border-[#B5B5B5] bg-white transition-colors"
              >
                {prompt}
              </motion.button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* System Status + Recent Missions */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        {/* System status */}
        <div className="p-4 rounded-2xl border border-[#E5E5E5] bg-white flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${systemOk === true ? "bg-green/10" : systemOk === false ? "bg-red/10" : "bg-[#F4F3EF]"}`}>
            <Zap className={`w-5 h-5 ${systemOk === true ? "text-green" : systemOk === false ? "text-red" : "text-[#8A8A8A]"}`} />
          </div>
          <div>
            <p className="text-sm font-medium">{systemOk === true ? "系统正常" : systemOk === false ? "系统异常" : "检查中..."}</p>
            <p className="text-xs text-[#8A8A8A]">后端状态</p>
          </div>
        </div>

        {/* Recent missions */}
        <div className="md:col-span-2 p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-[#8A8A8A]">最近任务</h3>
            {recentMissions.length > 0 && (
              <button onClick={() => setCurrentPage("reports")} className="text-xs text-[#8A8A8A] hover:text-[#0B0B0B]">
                查看全部 →
              </button>
            )}
          </div>
          {recentMissions.length === 0 ? (
            <p className="text-sm text-[#D4D4D4]">暂无任务，去执行一个吧</p>
          ) : (
            <div className="space-y-2">
              {recentMissions.map(m => (
                <div key={m.mission_id} className="flex items-center gap-2 text-sm">
                  {m.status === "done" ? <CheckCircle2 className="w-3.5 h-3.5 text-green shrink-0" /> :
                   m.status === "failed" ? <XCircle className="w-3.5 h-3.5 text-red shrink-0" /> :
                   <Clock className="w-3.5 h-3.5 text-[#8A8A8A] shrink-0" />}
                  <span className="truncate flex-1">{m.goal}</span>
                  <span className="text-xs text-[#D4D4D4] shrink-0">{m.created_at ? new Date(m.created_at).toLocaleDateString() : ""}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Recent Deliveries */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
        className="max-w-4xl mx-auto"
      >
        <div className="p-5 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#8A8A8A]">最近交付物</h3>
            </div>
            {recentDeliveries.length > 0 && (
              <button onClick={() => setCurrentPage("delivery")} className="text-xs text-[#8A8A8A] hover:text-[#0B0B0B]">
                查看全部 →
              </button>
            )}
          </div>
          {recentDeliveries.length === 0 ? (
            <p className="text-sm text-[#D4D4D4]">暂无交付物，执行 Agent 后保存的结果会出现在这里</p>
          ) : (
            <div className="space-y-2">
              {recentDeliveries.map(d => (
                <button
                  key={d.task_id}
                  onClick={() => {
                    window.history.pushState({}, "", `?page=delivery&taskId=${d.task_id}`)
                    setCurrentPage("delivery")
                  }}
                  className="w-full flex items-center gap-2 text-sm text-left hover:bg-[#F4F3EF] rounded-lg px-2 py-1.5 transition-colors"
                >
                  <Badge className={AGENT_COLORS[d.agent_id] || "bg-gray-100 text-gray-800"} variant="outline">
                    {d.agent_id}
                  </Badge>
                  <span className="truncate flex-1">{d.goal}</span>
                  <span className="text-xs text-[#D4D4D4] shrink-0">{d.created_at ? new Date(d.created_at).toLocaleDateString() : ""}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Scene Cards */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <motion.h2
          variants={itemVariants}
          className="text-sm font-medium text-[#8A8A8A] tracking-wider uppercase mb-4"
        >
          功能入口
        </motion.h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scenes.map((scene) => {
            const Icon = scene.icon
            return (
              <motion.div key={scene.id} variants={itemVariants}>
                <button
                  onClick={() => setCurrentPage(scene.id)}
                  className="w-full text-left p-5 rounded-2xl border border-[#E5E5E5] bg-white hover:border-[#B5B5B5] hover:translate-y-[-2px] transition-all duration-200 cursor-pointer group"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#F4F3EF] flex items-center justify-center shrink-0">
                      <Icon className="w-5 h-5 text-[#0B0B0B]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-[#0B0B0B] mb-1">{scene.title}</h3>
                      <p className="text-sm text-[#8A8A8A] leading-relaxed">{scene.desc}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#D4D4D4] mt-1 group-hover:text-[#8A8A8A] group-hover:translate-x-0.5 transition-all shrink-0" />
                  </div>
                </button>
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* Governance Quick Entry */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.4 }}
      >
        <button
          onClick={() => setCurrentPage("governance")}
          className="w-full text-left p-5 rounded-2xl border border-emerald-200 bg-emerald-50/50 hover:border-emerald-300 hover:translate-y-[-2px] transition-all duration-200 cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
              <Shield className="w-5 h-5 text-emerald-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-[#0B0B0B] mb-1">Governance 主入口</h3>
              <p className="text-sm text-[#8A8A8A] leading-relaxed">分类 → 计划 → 执行 → 产物交付，一站式闭环</p>
            </div>
            <ArrowRight className="w-4 h-4 text-emerald-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition-all shrink-0" />
          </div>
        </button>
      </motion.div>

      {/* Tips */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
      >
        <div className="max-w-2xl mx-auto p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-start gap-3">
            <span className="text-lg mt-0.5">💡</span>
            <div>
              <h4 className="font-medium text-sm text-[#0B0B0B] mb-1">小提示</h4>
              <p className="text-sm text-[#8A8A8A] leading-relaxed">
                不确定如何开始？直接说明目标、限制条件和希望得到的结果。
              </p>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

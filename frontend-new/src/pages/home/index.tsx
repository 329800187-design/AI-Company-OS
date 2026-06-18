import { useState } from "react"
import { motion } from "framer-motion"
import {
  FileText,
  Image,
  BarChart3,
  Search,
  Globe,
  MessageSquare,
  Sparkles,
  Zap,
  ChevronRight,
} from "lucide-react"
import { GlareCard } from "@/components/shared/glare-card"
import { NeonButton } from "@/components/shared/neon-button"
import { Textarea } from "@/components/ui/textarea"
import { useAppStore } from "@/stores/app"

const scenes = [
  {
    id: "marketing",
    title: "写文案",
    desc: "朋友圈、小红书、淘宝、抖音...一键生成",
    icon: FileText,
    color: "blue" as const,
    gradient: "from-blue-500 to-cyan-500",
    emoji: "📝",
  },
  {
    id: "image",
    title: "做图片",
    desc: "产品图、海报、Logo，说一句话就搞定",
    icon: Image,
    color: "cyan" as const,
    gradient: "from-cyan-500 to-teal-500",
    emoji: "🎨",
  },
  {
    id: "data",
    title: "看数据",
    desc: "上传 Excel，自动分析销售趋势",
    icon: BarChart3,
    color: "purple" as const,
    gradient: "from-purple-500 to-pink-500",
    emoji: "📊",
  },
  {
    id: "research",
    title: "做调研",
    desc: "竞品分析、市场调研、行业报告",
    icon: Search,
    color: "blue" as const,
    gradient: "from-blue-500 to-indigo-500",
    emoji: "🔍",
  },
  {
    id: "website",
    title: "建网站",
    desc: "产品页面、落地页，一句话生成",
    icon: Globe,
    color: "cyan" as const,
    gradient: "from-cyan-500 to-blue-500",
    emoji: "🌐",
  },
  {
    id: "chat",
    title: "问问题",
    desc: "有任何不懂的，直接问我就行",
    icon: MessageSquare,
    color: "purple" as const,
    gradient: "from-purple-500 to-violet-500",
    emoji: "💬",
  },
]

const quickPrompts = [
  "帮我写一条朋友圈文案，推广手工耳环",
  "帮我写 5 条小红书笔记标题",
  "分析一下我上个月的销售数据",
  "帮我做一个产品介绍页面",
]

export default function HomePage() {
  const [input, setInput] = useState("")
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  const handleSend = () => {
    if (!input.trim()) return
    setCurrentPage("chat")
  }

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center py-8"
      >
        <motion.div
          initial={{ scale: 0.9 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: "spring" }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-primary/20 mb-6"
          style={{
            background: "linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(6, 182, 212, 0.08))",
          }}
        >
          <Sparkles className="w-4 h-4 text-primary" />
          <span className="text-sm text-primary">你的 AI 员工已就绪</span>
        </motion.div>

        <h1 className="text-4xl md:text-5xl font-bold mb-4">
          <span className="text-foreground">你好！</span>
          <br />
          <span
            style={{
              background: "linear-gradient(135deg, #60a5fa, #22d3ee)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            我是你的 AI 助手
          </span>
        </h1>

        <p className="text-muted-foreground text-lg max-w-xl mx-auto">
          告诉我你想做什么，我来帮你完成
        </p>
      </motion.div>

      {/* Quick Input */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="max-w-2xl mx-auto"
      >
        <GlareCard className="p-6" glareColor="blue">
          <div className="flex gap-3">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="随便说什么都行，比如：帮我写一条朋友圈文案..."
              className="min-h-[70px] text-base bg-background/50"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />
            <NeonButton
              onClick={handleSend}
              color="blue"
              className="self-end px-6"
            >
              <Zap className="w-4 h-4" />
              发送
            </NeonButton>
          </div>

          {/* Quick prompts */}
          <div className="flex flex-wrap gap-2 mt-4">
            {quickPrompts.map((prompt, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                onClick={() => setInput(prompt)}
                className="px-3 py-1.5 text-xs rounded-full border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-primary/5 transition-all"
              >
                {prompt}
              </motion.button>
            ))}
          </div>
        </GlareCard>
      </motion.div>

      {/* Scene Cards */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          我能帮你做这些
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scenes.map((scene, i) => (
            <motion.div
              key={scene.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 + i * 0.08 }}
            >
              <GlareCard
                glareColor={scene.color}
                onClick={() => setCurrentPage(scene.id)}
                className="h-full p-5"
              >
                <div className="flex items-start gap-3">
                  <div className="text-3xl">{scene.emoji}</div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-1">{scene.title}</h3>
                    <p className="text-sm text-muted-foreground">{scene.desc}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground mt-1" />
                </div>
              </GlareCard>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Tips */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
      >
        <div className="max-w-2xl mx-auto p-4 rounded-xl bg-card/50 border border-border">
          <div className="flex items-start gap-3">
            <span className="text-xl">💡</span>
            <div>
              <h4 className="font-medium mb-1">小提示</h4>
              <p className="text-sm text-muted-foreground">
                不知道怎么描述？没关系！直接说大白话就行，比如"帮我写个朋友圈文案卖耳环"。
              </p>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

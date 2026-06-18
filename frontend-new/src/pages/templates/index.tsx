import { motion } from "framer-motion"
import { FileText, ArrowRight } from "lucide-react"
import { GlowCard } from "@/components/shared/glow-card"
import { useAppStore } from "@/stores/app"

const templates = [
  {
    id: "xiaohongshu",
    title: "小红书文案",
    desc: "生成爆款小红书笔记",
    emoji: "📕",
    page: "marketing",
  },
  {
    id: "product-desc",
    title: "产品描述",
    desc: "电商产品详情页文案",
    emoji: "📦",
    page: "marketing",
  },
  {
    id: "social-ad",
    title: "社交广告",
    desc: "朋友圈、抖音广告文案",
    emoji: "📢",
    page: "marketing",
  },
  {
    id: "landing-page",
    title: "落地页",
    desc: "产品落地页文案",
    emoji: "🌐",
    page: "website",
  },
  {
    id: "email",
    title: "营销邮件",
    desc: "EDM 邮件模板",
    emoji: "📧",
    page: "marketing",
  },
  {
    id: "brand-story",
    title: "品牌故事",
    desc: "品牌介绍文案",
    emoji: "✨",
    page: "marketing",
  },
]

export default function TemplatesPage() {
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
          <FileText className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">场景模板</h1>
          <p className="text-muted-foreground">选择模板，快速开始</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((tpl, i) => (
          <motion.div
            key={tpl.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <GlowCard
              onClick={() => setCurrentPage(tpl.page)}
              className="h-full"
            >
              <div className="flex items-start gap-4">
                <div className="text-3xl">{tpl.emoji}</div>
                <div className="flex-1">
                  <h3 className="font-semibold mb-1">{tpl.title}</h3>
                  <p className="text-sm text-muted-foreground">{tpl.desc}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground" />
              </div>
            </GlowCard>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  ClipboardList,
  Download,
  FileText,
  Globe2,
  History,
  Loader2,
  Megaphone,
  Play,
  RotateCcw,
  Search,
  Shield,
  ShieldOff,
  SkipForward,
  Sparkles,
  Target,
  Zap,
  BarChart3,
  Palette,
  BookOpen,
} from "lucide-react"
import { api } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

interface ModuleResult {
  module_id: string
  title: string
  status: string
  prompt?: string
  result: string
  confidence: number
  warnings: string[]
  error: string
  used_tools: string[]
  used_agents?: string[]
  mode?: string
  started_at?: string
  finished_at?: string
  duration_ms?: number
  next_actions?: string[]
  structured_output?: Record<string, unknown>
}

interface Mission {
  mission_id: string
  goal: string
  status: string
  created_at?: string
  updated_at?: string
  modules: ModuleResult[]
  metrics?: MissionMetrics
}

interface MissionSummary {
  mission_id: string
  goal: string
  status: string
  created_at: string
}

interface MissionEvent {
  id: number
  mission_id: string
  type: string
  module_id: string | null
  message: string
  payload: Record<string, unknown>
  created_at: string
}

interface MissionTemplate {
  id: string
  name: string
  description: string
  default_goal: string
  default_modules: string[]
  suggested_inputs: string[]
  expected_outputs: string[]
}

interface MissionMetrics {
  total_modules: number
  succeeded_modules: number
  failed_modules: number
  skipped_modules: number
  duration_ms: number
  warning_count: number
  next_action_count: number
  completion_rate: number
}

const MODULE_IDS = ["strategy", "market", "marketing", "landing", "actions"]

const moduleIcons: Record<string, React.ElementType> = {
  strategy: Target,
  market: Search,
  marketing: Megaphone,
  landing: Globe2,
  actions: ClipboardList,
}

const moduleDescriptions: Record<string, string> = {
  strategy: "把老板目标压缩成业务判断、关键机会和风险。",
  market: "调研市场、用户、竞品和可进入机会。",
  marketing: "生成卖点、内容方向、渠道打法和首批文案。",
  landing: "生成首屏、卖点、证明、CTA 等落地页结构。",
  actions: "拆成今天、本周、本月能执行的行动项。",
}

// Boss Lite 常用作战模板
const liteTemplates = [
  {
    id: "new-product",
    label: "新品上线",
    icon: Sparkles,
    goal: "我要为一个新产品做一次完整的新品上线策划，目标是产出市场定位分析、首批种草文案、视觉方向建议、核心数据指标和落地页框架。",
  },
  {
    id: "cold-start",
    label: "品牌冷启动",
    icon: Target,
    goal: "我要为一个新品牌做冷启动方案，目标是完成目标用户画像、竞品差异分析、初始获客渠道策略、第一批内容方向和品牌视觉调性建议。",
  },
  {
    id: "xiaohongshu",
    label: "小红书种草",
    icon: BookOpen,
    goal: "我要在小红书做一次种草投放，目标是产出 5 条种草笔记文案、封面视觉方向、关键词布局策略、达人合作建议和数据跟踪指标。",
  },
  {
    id: "douyin",
    label: "抖音短视频增长",
    icon: BarChart3,
    goal: "我要用抖音短视频做增长，目标是产出 5 条短视频脚本、选题方向、投流策略、账号人设建议和核心转化指标。",
  },
  {
    id: "seo",
    label: "SEO 内容增长",
    icon: Globe2,
    goal: "我要通过 SEO 内容做长期流量增长，目标是产出关键词矩阵、10 篇内容选题、页面结构建议、内链策略和排名跟踪指标。",
  },
  {
    id: "landing-page",
    label: "落地页转化",
    icon: Megaphone,
    goal: "我要优化一个产品的落地页转化率，目标是产出首屏文案、卖点排序、信任证明方案、CTA 策略和 A/B 测试建议。",
  },
  {
    id: "competitor",
    label: "竞品调研",
    icon: Search,
    goal: "我要做一次深度竞品调研，目标是分析 5 个核心竞品的定位、定价、卖点、渠道策略，找出差异化机会和可借鉴打法。",
  },
  {
    id: "data-review",
    label: "数据复盘",
    icon: ClipboardList,
    goal: "我要对上一阶段的运营数据做复盘，目标是产出关键指标分析、增长归因、问题诊断、下一阶段优化建议和具体行动计划。",
  },
]

const examples = [
  "帮我调研 AI 陪伴产品的市场机会，并给出第一版运营动作",
  "给我的知识付费课程做一套小红书推广方案和落地页草稿",
  "分析 5 个同类 SaaS 竞品，找出我们可以切入的差异化卖点",
  "我要为一个手工银饰品牌做一次新品上线",
]

// Boss Lite agent icons
const agentIcons: Record<string, React.ElementType> = {
  research: BookOpen,
  marketing: Megaphone,
  image: Palette,
  data: BarChart3,
  website: Globe2,
}

function valueToText(value: unknown): string {
  if (value == null) return ""
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  if (Array.isArray(value)) return value.map(valueToText).filter(Boolean).join("；")
  if (typeof value === "object") {
    const record = value as Record<string, unknown>
    const name = record.name || record.title || record.metric || record.label
    const description = record.description || record.summary || record.value
    const formula = record.formula
    const parts = [name, description].filter(Boolean).map(String)
    if (formula) parts.push(`公式：${String(formula)}`)
    if (parts.length) return parts.join(" — ")
    return Object.entries(record).slice(0, 4).map(([key, val]) => `${key}: ${valueToText(val)}`).join("；")
  }
  return String(value)
}

function listToText(value: unknown, limit = 3): string {
  if (Array.isArray(value)) return value.slice(0, limit).map(valueToText).filter(Boolean).join("；")
  return valueToText(value)
}

/** 从 structured_output 中提取可读摘要，控制在 80-120 字 */
function extractAgentSummary(agentId: string, summary: string, so: Record<string, unknown>): string {
  // 优先用 summary
  if (summary && summary.length > 10) return summary.length > 120 ? summary.slice(0, 117) + "..." : summary

  // 按 agent 类型提取关键字段
  switch (agentId) {
    case "research": {
      const parts: string[] = []
      const ms = so.market_summary as string
      if (ms) parts.push(ms)
      const kf = so.key_findings as unknown[]
      if (kf?.length) parts.push(`发现: ${valueToText(kf[0])}`)
      const op = so.opportunities as unknown[]
      if (op?.length) parts.push(`机会: ${valueToText(op[0])}`)
      const rk = so.risks as unknown[]
      if (rk?.length) parts.push(`风险: ${valueToText(rk[0])}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "市场调研完成"
    }
    case "marketing": {
      const parts: string[] = []
      const hl = so.headline as string
      if (hl) parts.push(hl)
      const sub = so.subheadline as string
      if (sub) parts.push(sub)
      const cta = so.cta as string
      if (cta) parts.push(`CTA: ${cta}`)
      const kw = so.keywords as unknown[]
      if (kw?.length) parts.push(`关键词: ${kw.slice(0, 3).map(valueToText).join("/")}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "营销方案完成"
    }
    case "image": {
      const parts: string[] = []
      const ip = so.image_prompt as string
      if (ip) parts.push(`提示词: ${ip}`)
      const st = so.style as string
      if (st) parts.push(`风格: ${st}`)
      const cp = so.color_palette
      if (cp) parts.push(`色彩: ${valueToText(cp)}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "视觉方案完成"
    }
    case "data": {
      const parts: string[] = []
      const aq = so.analysis_question as string
      if (aq) parts.push(aq)
      const km = so.key_metrics as unknown[]
      if (km?.length) parts.push(`指标: ${valueToText(km[0])}`)
      const fn = so.findings as unknown[]
      if (fn?.length) parts.push(`发现: ${valueToText(fn[0])}`)
      const rc = so.recommendations as unknown[]
      if (rc?.length) parts.push(`建议: ${valueToText(rc[0])}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "数据分析完成"
    }
    case "website": {
      const parts: string[] = []
      const pg = so.page_goal as string
      if (pg) parts.push(pg)
      const hero = so.hero as Record<string, unknown>
      if (hero?.headline) parts.push(`首屏: ${hero.headline}`)
      const sections = so.sections as Array<Record<string, unknown>>
      if (sections?.length) parts.push(`${sections.length} 个板块`)
      const seo = so.seo as Record<string, unknown>
      if (seo?.title) parts.push(`SEO: ${seo.title}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "落地页方案完成"
    }
    default:
      return summary || "执行完成"
  }
}

/** 从 structured_output 中提取结构化关键字段 */
function extractKeyFields(agentId: string, so: Record<string, unknown>): Array<{ label: string; value: string }> {
  const fields: Array<{ label: string; value: string }> = []
  if (!so || Object.keys(so).length === 0) return fields

  switch (agentId) {
    case "research":
      if (so.market_summary) fields.push({ label: "市场摘要", value: String(so.market_summary).slice(0, 200) })
      if (so.key_findings) fields.push({ label: "关键发现", value: listToText(so.key_findings, 3) })
      if (so.opportunities) fields.push({ label: "机会", value: listToText(so.opportunities, 3) })
      if (so.risks) fields.push({ label: "风险", value: listToText(so.risks, 3) })
      break
    case "marketing":
      if (so.headline) fields.push({ label: "核心文案", value: String(so.headline) })
      if (so.subheadline) fields.push({ label: "副标题", value: String(so.subheadline) })
      if (so.cta) fields.push({ label: "CTA", value: String(so.cta) })
      if (so.selling_points) fields.push({ label: "核心卖点", value: listToText(so.selling_points, 5) })
      if (so.keywords) fields.push({ label: "关键词", value: listToText(so.keywords, 5) })
      break
    case "image":
      if (so.style) fields.push({ label: "视觉风格", value: String(so.style) })
      if (so.image_prompt) fields.push({ label: "图片提示词", value: String(so.image_prompt).slice(0, 200) })
      if (so.color_palette) fields.push({ label: "色彩方案", value: valueToText(so.color_palette) })
      if (so.usage_suggestions) fields.push({ label: "使用建议", value: valueToText(so.usage_suggestions).slice(0, 200) })
      break
    case "data":
      if (so.analysis_question) fields.push({ label: "分析主题", value: String(so.analysis_question) })
      if (so.key_metrics) fields.push({ label: "关键指标", value: listToText(so.key_metrics, 5) })
      if (so.findings) fields.push({ label: "发现", value: listToText(so.findings, 3) })
      if (so.recommendations) fields.push({ label: "建议", value: listToText(so.recommendations, 3) })
      break
    case "website":
      if (so.page_goal) fields.push({ label: "页面目标", value: String(so.page_goal) })
      {
        const hero = so.hero as Record<string, unknown> | undefined
        if (hero?.headline) fields.push({ label: "首屏标题", value: String(hero.headline) })
        if (hero?.cta) fields.push({ label: "首屏 CTA", value: String(hero.cta) })
      }
      if (so.sections) {
        const secs = so.sections as Array<Record<string, unknown>>
        fields.push({ label: "页面板块", value: secs.slice(0, 5).map(s => s.title || s.name || "板块").join("、") })
      }
      break
  }
  return fields
}

export default function BossPage() {
  // Mode: "command-center" or "boss-lite"
  const [mode, setMode] = useState<"command-center" | "boss-lite">("boss-lite")
  const [goal, setGoal] = useState("")
  const [activeModule, setActiveModule] = useState("strategy")
  const [isRunning, setIsRunning] = useState(false)
  const [currentMission, setCurrentMission] = useState<Mission | null>(null)
  const [recentMissions, setRecentMissions] = useState<MissionSummary[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [enabledModules, setEnabledModules] = useState<string[]>([...MODULE_IDS])
  const [events, setEvents] = useState<MissionEvent[]>([])
  const [showEvents, setShowEvents] = useState(false)
  const [templates, setTemplates] = useState<MissionTemplate[]>([])
  const [showTemplates, setShowTemplates] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<MissionTemplate | null>(null)
  const [allowBrowserAutomation, setAllowBrowserAutomation] = useState(false)
  const [exportToast, setExportToast] = useState<"json" | "markdown" | null>(null)

  // Boss Lite state
  const [liteResult, setLiteResult] = useState<{
    ok: boolean
    task_id: string
    goal: string
    handoff_enabled?: boolean
    execution_mode?: string
    plan: Array<{
      step: number
      agent_id: string
      task_type: string
      title: string
      prompt: string
      purpose: string
      status: string
    }>
    results: Array<{
      agent_id: string
      title: string
      ok: boolean
      summary: string
      structured_output: Record<string, unknown>
      warnings: string[]
      errors: string[]
      error?: string
      duration_ms?: number
      used_handoff?: boolean
      handoff_sources?: string[]
    }>
    summary: {
      text: string
      succeeded: number
      failed: number
      total: number
      total_duration_ms?: number
    }
    structured_output: Record<string, unknown> & {
      total_duration_ms?: number
      handoff_enabled?: boolean
      handoff_sources?: string[]
      handoff_targets?: string[]
    }
    delivery_task_id?: string
  } | null>(null)
  const [liteActiveAgent, setLiteActiveAgent] = useState<string>("")
  const [liteProgressPhase, setLiteProgressPhase] = useState(0)
  const [copiedHistoryGoalId, setCopiedHistoryGoalId] = useState<string | null>(null)

  // Boss Lite 历史记录
  const [liteHistory, setLiteHistory] = useState<Array<{
    task_id: string
    goal: string
    created_at: string
    summary?: string
    artifact_type?: string
  }>>([])

  // 时间本地化：ISO → 中文本地时间
  const formatLocalTime = (iso: string): string => {
    if (!iso) return "时间未知"
    try {
      const d = new Date(iso)
      if (isNaN(d.getTime())) return "时间未知"
      const y = d.getFullYear()
      const m = d.getMonth() + 1
      const day = d.getDate()
      const h = d.getHours().toString().padStart(2, "0")
      const min = d.getMinutes().toString().padStart(2, "0")
      return `${y}/${m}/${day} ${h}:${min}`
    } catch {
      return "时间未知"
    }
  }

  // 摘要兜底：summary → goal 前 60 字 → "暂无摘要"
  const getSummaryFallback = (task: { summary?: string; goal?: string }): string => {
    if (task.summary?.trim()) return task.summary.trim()
    if (task.goal?.trim()) {
      const t = task.goal.trim()
      return t.length > 60 ? t.slice(0, 60) + "…" : t
    }
    return "暂无摘要"
  }

  const copyHistoryGoal = async (taskId: string, goalText: string) => {
    const text = goalText.trim()
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopiedHistoryGoalId(taskId)
    setTimeout(() => setCopiedHistoryGoalId(null), 1600)
  }
  const [liteHistoryLoading, setLiteHistoryLoading] = useState(false)

  const modules = currentMission?.modules || []
  const activeResult = modules.find((m) => m.module_id === activeModule) || null
  const completedCount = modules.filter((m) => m.status === "done").length
  const failedCount = modules.filter((m) => m.status === "failed").length
  const skippedCount = modules.filter((m) => m.status === "skipped").length

  // 加载历史 missions
  const loadRecentMissions = async () => {
    try {
      const data = await api.listMissions(10)
      setRecentMissions(data.missions || [])
    } catch (error) {
      console.error("Load recent missions failed:", error)
    }
  }

  // 加载 Boss Lite 历史记录
  const loadLiteHistory = async () => {
    setLiteHistoryLoading(true)
    try {
      const data = await api.listMiniDeliveryTasks({ agent_id: "boss", limit: 5 })
      setLiteHistory(data.tasks || [])
    } catch (error) {
      console.error("Load lite history failed:", error)
      setLiteHistory([])
    } finally {
      setLiteHistoryLoading(false)
    }
  }

  useEffect(() => {
    loadRecentMissions()
    loadTemplates()
    loadLiteHistory()

    // Check for mission to load from sessionStorage
    const loadMissionId = sessionStorage.getItem("load_mission_id")
    if (loadMissionId) {
      sessionStorage.removeItem("load_mission_id")
      loadMission(loadMissionId)
    }

    // Check for template to load from sessionStorage
    const tplData = sessionStorage.getItem("boss_selected_template")
    if (tplData) {
      sessionStorage.removeItem("boss_selected_template")
      try {
        const tpl = JSON.parse(tplData)
        setSelectedTemplate(tpl)
        setGoal(tpl.default_goal)
        setEnabledModules(tpl.default_modules)
      } catch {
        // ignore
      }
    }
  }, [])

  const loadTemplates = async () => {
    try {
      const data = await api.getTemplates()
      setTemplates(data.templates || [])
    } catch (error) {
      console.error("Load templates failed:", error)
    }
  }

  // Boss Lite: execute all agents
  const executeBossLite = async () => {
    const trimmed = goal.trim()
    if (!trimmed || isRunning) return

    setIsRunning(true)
    setLiteResult(null)
    setLiteProgressPhase(0)

    try {
      const result = await api.bossLiteExecute(trimmed)
      setLiteResult(result)
      if (result.results.length > 0) {
        setLiteActiveAgent(result.results[0].agent_id)
      }
      // 执行成功后刷新历史列表
      loadLiteHistory()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "执行失败"
      console.error("Boss Lite execute failed:", error)
      alert(`Boss Lite 执行失败: ${errorMsg}`)
    } finally {
      setIsRunning(false)
    }
  }

  // Boss Lite: reset to start new
  const resetLite = () => {
    setLiteResult(null)
    setLiteActiveAgent("")
    setLiteProgressPhase(0)
    setGoal("")
  }

  // 跳转到 Delivery 页面查看交付物
  const viewDelivery = (taskId: string) => {
    window.location.href = `/app?page=delivery&taskId=${encodeURIComponent(taskId)}`
  }

  // Boss Lite progress phase auto-cycle
  useEffect(() => {
    if (!isRunning || mode !== "boss-lite") return
    const timer = setInterval(() => {
      setLiteProgressPhase((prev) => (prev < 3 ? prev + 1 : prev))
    }, 4000)
    return () => clearInterval(timer)
  }, [isRunning, mode])

  // 加载事件日志
  const loadEvents = async (missionId: string) => {
    try {
      const data = await api.getMissionEvents(missionId)
      setEvents(data.events || [])
    } catch {
      setEvents([])
    }
  }

  // v2: 两阶段流程 — 阶段1: 只创建计划
  const createPlan = async () => {
    const trimmed = goal.trim()
    if (!trimmed || isRunning) return

    setIsRunning(true)
    setActiveModule("strategy")

    try {
      console.log("Creating mission plan with goal:", trimmed, "modules:", enabledModules)
      const mission = await api.createMission(trimmed, false, enabledModules, allowBrowserAutomation)
      console.log("Mission plan created:", mission)
      setCurrentMission({
        ...mission,
        modules: mission.modules || [],
      })
      // 不自动执行，状态应为 pending_review
      console.log("Plan ready for review, status:", mission.status)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "创建计划失败"
      console.error("Create plan failed:", error)
      if (errorMsg.includes("429") || errorMsg.includes("rate")) {
        alert("请求太频繁，请稍后再试。")
      } else if (errorMsg.includes("400")) {
        alert(`参数错误: ${errorMsg}`)
      } else {
        alert(`创建计划失败: ${errorMsg}`)
      }
    } finally {
      setIsRunning(false)
    }
  }

  // v2: 两阶段流程 — 阶段2: 确认执行（逐模块串行，每个120s超时）
  const confirmRun = async () => {
    if (!currentMission || isRunning) return

    setIsRunning(true)

    const pendingModules = currentMission.modules.filter(
      m => m.status !== "skipped" && m.status !== "done"
    )

    for (const mod of pendingModules) {
      // 切换到当前正在执行的模块标签
      setActiveModule(mod.module_id)

      try {
        // 120秒超时
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 120_000)

        const updated = await api.runMissionModule(
          currentMission.mission_id,
          mod.module_id,
          allowBrowserAutomation,
          controller.signal
        )
        clearTimeout(timeoutId)

        setCurrentMission({ ...updated, modules: updated.modules || [] })
      } catch (err) {
        console.error(`Module ${mod.module_id} failed:`, err)
        // 刷新看部分结果
        try {
          const refreshed = await api.getMission(currentMission.mission_id)
          setCurrentMission({ ...refreshed, modules: refreshed.modules || [] })
        } catch { /* 静默 */ }
      }
    }

    // 最终刷新事件日志
    try {
      const final = await api.getMission(currentMission.mission_id)
      setCurrentMission({ ...final, modules: final.modules || [] })
      loadEvents(currentMission.mission_id)
    } catch { /* 静默 */ }

    setIsRunning(false)
    loadRecentMissions()
  }

  // 用户接受结果
  const acceptMission = async () => {
    if (!currentMission || isRunning) return
    setIsRunning(true)
    try {
      const updated = await api.acceptMission(currentMission.mission_id)
      setCurrentMission({
        ...updated,
        modules: updated.modules || [],
      })
      loadRecentMissions()
    } catch (error) {
      console.error("Accept mission failed:", error)
      alert(`接受结果失败: ${error instanceof Error ? error.message : "未知错误"}`)
    } finally {
      setIsRunning(false)
    }
  }

  // 重跑单个模块
  const rerunModule = async (moduleId: string, forceAllowBrowser = false) => {
    if (!currentMission || isRunning) return

    const shouldAllow = forceAllowBrowser || allowBrowserAutomation
    setIsRunning(true)
    try {
      const updated = await api.runMissionModule(currentMission.mission_id, moduleId, shouldAllow)
      setCurrentMission({
        ...updated,
        modules: updated.modules || [],
      })
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "重跑失败"
      console.error("Module rerun failed:", error)
      alert(`重跑模块失败: ${errorMsg}`)
    } finally {
      setIsRunning(false)
    }
  }

  // 加载历史 mission
  const loadMission = async (missionId: string) => {
    try {
      const mission = await api.getMission(missionId)
      const safeMission = { ...mission, modules: mission.modules || [] }
      setCurrentMission(safeMission)
      setGoal(mission.goal || "")
      loadEvents(missionId)
      // 从 mission 恢复 enabled_modules
      const activeIds = safeMission.modules.filter((m) => m.status !== "skipped").map((m) => m.module_id)
      setEnabledModules(activeIds.length > 0 ? activeIds : [...MODULE_IDS])
      setActiveModule("strategy")
      setShowHistory(false)
    } catch (error) {
      console.error("Load mission failed:", error)
      alert(`加载历史任务失败: ${error instanceof Error ? error.message : "未知错误"}`)
    }
  }

  // 导出
  const handleExport = async (format: "json" | "markdown") => {
    if (!currentMission) return
    try {
      await api.exportMission(currentMission.mission_id, format)
      // 显示成功反馈
      setExportToast(format)
      setTimeout(() => setExportToast(null), 3000)
    } catch (error) {
      console.error("Export failed:", error)
      alert(`导出失败: ${error instanceof Error ? error.message : "未知错误"}`)
    }
  }

  // 模块 checkbox 切换
  const toggleModule = (moduleId: string) => {
    setEnabledModules((prev) => {
      if (prev.includes(moduleId)) {
        return prev.filter((m) => m !== moduleId)
      }
      return [...prev, moduleId]
    })
  }

  const statusBadge = (status: string) => {
    if (status === "running") return <Badge variant="info">执行中</Badge>
    if (status === "done") return <Badge variant="success">已完成</Badge>
    if (status === "ready_for_review") return <Badge variant="success">待审核</Badge>
    if (status === "partial") return <Badge variant="warning">部分结果</Badge>
    if (status === "pending_review") return <Badge variant="info">待确认</Badge>
    if (status === "failed") return <Badge variant="destructive">需处理</Badge>
    if (status === "blocked") return <Badge variant="warning">需授权</Badge>
    if (status === "skipped") return <Badge variant="secondary">已跳过</Badge>
    return <Badge variant="secondary">待执行</Badge>
  }

  // v2: Mission 状态文案映射
  const missionStatusText = (status: string) => {
    const map: Record<string, string> = {
      pending_review: "计划已生成，等待确认执行",
      pending: "计划已生成，等待确认执行",
      running: "正在执行模块中...",
      ready_for_review: "已生成结果，等待人工审核",
      partial: "证据不足，但已有可参考结果",
      done: "用户已确认完成",
      failed: "无有效结果",
    }
    return map[status] || status
  }

  const formatDuration = (ms?: number) => {
    if (!ms || ms <= 0) return null
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="inline-block px-3 py-1 rounded-full border border-[#E5E5E5] text-[11px] text-[#8A8A8A] tracking-wider mb-3">
              Boss Command Center
            </span>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[#0B0B0B]">
              老板运营指挥台
            </h1>
            <p className="text-sm text-[#8A8A8A] mt-2">
              输入一个业务目标，AI 自动拆解为多部门协同执行方案。
            </p>
            {/* Mode Toggle */}
            <div className="flex items-center gap-2 mt-4">
              <button
                type="button"
                onClick={() => setMode("boss-lite")}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  mode === "boss-lite"
                    ? "bg-[#0B0B0B] text-white"
                    : "bg-[#F4F3EF] text-[#8A8A8A] hover:text-[#0B0B0B]"
                )}
              >
                <Zap className="inline-block h-3.5 w-3.5 mr-1.5" />
                Boss Lite
              </button>
              <button
                type="button"
                onClick={() => setMode("command-center")}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  mode === "command-center"
                    ? "bg-[#0B0B0B] text-white"
                    : "bg-[#F4F3EF] text-[#8A8A8A] hover:text-[#0B0B0B]"
                )}
              >
                <Target className="inline-block h-3.5 w-3.5 mr-1.5" />
                指挥台
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {mode === "command-center" && modules.length > 0 && (
              <Badge variant={failedCount > 0 ? "warning" : completedCount === modules.length - skippedCount ? "success" : "secondary"}>
                {completedCount}/{modules.length - skippedCount} 完成
              </Badge>
            )}
            {mode === "command-center" && currentMission && (
              <Button variant="outline" size="sm" onClick={() => handleExport("markdown")} className="gap-1">
                <Download className="h-3.5 w-3.5" />
                导出
              </Button>
            )}

            {/* Boss Lite header actions */}
            {mode === "boss-lite" && liteResult && (
              <>
                {liteResult.delivery_task_id && (
                  <Badge variant="outline">
                    交付物: {liteResult.delivery_task_id}
                  </Badge>
                )}
                <Button variant="outline" size="sm" onClick={resetLite} className="gap-1">
                  <RotateCcw className="h-3.5 w-3.5" />
                  新任务
                </Button>
              </>
            )}

            {/* Metrics 小面板 */}
            {currentMission?.metrics && (currentMission.status !== "pending" && currentMission.status !== "pending_review" && currentMission.status !== "running") && (
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  完成率 {Math.round(currentMission.metrics.completion_rate * 100)}%
                </Badge>
                <Badge variant="outline">
                  {currentMission.metrics.succeeded_modules}/{currentMission.metrics.total_modules} 成功
                </Badge>
                {currentMission.metrics.failed_modules > 0 && (
                  <Badge variant="destructive">{currentMission.metrics.failed_modules} 失败</Badge>
                )}
                {currentMission.metrics.skipped_modules > 0 && (
                  <Badge variant="secondary">{currentMission.metrics.skipped_modules} 跳过</Badge>
                )}
                {currentMission.metrics.warning_count > 0 && (
                  <Badge variant="warning">{currentMission.metrics.warning_count} 警告</Badge>
                )}
                {currentMission.metrics.duration_ms > 0 && (
                  <Badge variant="outline">
                    {currentMission.metrics.duration_ms < 1000
                      ? `${currentMission.metrics.duration_ms}ms`
                      : `${(currentMission.metrics.duration_ms / 1000).toFixed(1)}s`}
                  </Badge>
                )}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowHistory(!showHistory)}
              className="gap-1"
            >
              <History className="h-3.5 w-3.5" />
              历史
            </Button>
          </div>
        </div>
      </motion.div>

      {/* 历史面板 — only in command-center mode */}
      {mode === "command-center" && showHistory && (
        <div className="p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <h3 className="mb-3 font-medium text-sm text-[#8A8A8A] tracking-wider uppercase">最近的 Mission</h3>
          {recentMissions.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无历史记录</p>
          ) : (
            <div className="space-y-2">
              {recentMissions.map((m) => (
                <button
                  key={m.mission_id}
                  type="button"
                  onClick={() => loadMission(m.mission_id)}
                  className="w-full rounded-lg border border-border p-3 text-left transition hover:border-primary/40 hover:bg-accent/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm">{m.goal}</span>
                    {statusBadge(m.status)}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{m.created_at}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Goal Input Card */}
      <motion.div
        id="boss-goal-input"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-[#0B0B0B]">
              今天要推进什么业务目标？
            </div>
            <Textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="例如：帮我调研 AI 陪伴产品的市场机会，并生成第一版运营行动包。"
              className="min-h-[120px] text-base bg-[#F4F3EF] border-[#E5E5E5] rounded-xl"
            />
            <div className="flex flex-wrap gap-2">
              {examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setGoal(example)}
                  className="rounded-full border border-[#E5E5E5] px-3 py-1.5 text-xs text-[#8A8A8A] transition hover:border-[#B5B5B5] hover:text-[#0B0B0B]"
                >
                  {example}
                </button>
              ))}
            </div>

            {/* Boss Lite 常用作战模板 */}
            {mode === "boss-lite" && !liteResult && !isRunning && (
              <div className="pt-1">
                <p className="text-xs text-[#B5B5B5] mb-2.5">
                  选择模板会自动填入目标，你也可以继续编辑。
                </p>
                <div className="flex flex-wrap gap-2">
                  {liteTemplates.map((tpl) => {
                    const Icon = tpl.icon
                    return (
                      <button
                        key={tpl.id}
                        type="button"
                        onClick={() => {
                          setGoal(tpl.goal)
                          setLiteResult(null)
                        }}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[#E5E5E5] bg-[#F9F9F7] px-3.5 py-1.5 text-xs font-medium text-[#5A5A5A] transition-all hover:border-[#0B0B0B] hover:text-[#0B0B0B] hover:bg-white"
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {tpl.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 模块选择 + 模板入口 — only in command-center mode */}
            {mode === "command-center" && !currentMission && (
              <div className="space-y-3 pt-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-xs font-medium text-muted-foreground">执行模块：</span>
                  {MODULE_IDS.map((id) => (
                    <label
                      key={id}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={enabledModules.includes(id)}
                        onChange={() => toggleModule(id)}
                        className="h-3.5 w-3.5 rounded border-border accent-primary"
                      />
                      {id === "strategy" ? "战略" : id === "market" ? "市场" : id === "marketing" ? "营销" : id === "landing" ? "落地页" : "清单"}
                    </label>
                  ))}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setShowTemplates(!showTemplates)}
                  className="gap-1"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {selectedTemplate ? `已选模板：${selectedTemplate.name}` : "从模板创建"}
                </Button>
              </div>
            )}

            {/* 模板选择面板 */}
            {showTemplates && !currentMission && (
              <div className="grid gap-3 pt-2 sm:grid-cols-2 lg:grid-cols-3">
                {templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => {
                      setSelectedTemplate(tpl)
                      setGoal(tpl.default_goal)
                      setEnabledModules(tpl.default_modules)
                      setShowTemplates(false)
                    }}
                    className={cn(
                      "rounded-lg border p-3 text-left transition-all",
                      selectedTemplate?.id === tpl.id
                        ? "border-primary/50 bg-primary/10"
                        : "border-border hover:border-primary/30 hover:bg-accent/50"
                    )}
                  >
                    <h4 className="text-sm font-medium">{tpl.name}</h4>
                    <p className="mt-1 text-xs text-muted-foreground">{tpl.description}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {tpl.default_modules.map((m) => (
                        <span key={m} className="rounded bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {m}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 浏览器自动化授权 — only in command-center mode */}
          {mode === "command-center" && (
            <div className="flex items-center gap-3 rounded-xl border border-[#E5E5E5] bg-[#F4F3EF] px-4 py-2.5">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allowBrowserAutomation}
                  onChange={(e) => setAllowBrowserAutomation(e.target.checked)}
                  className="h-4 w-4 rounded border-[#D4D4D4] accent-[#0B0B0B]"
                />
                {allowBrowserAutomation ? (
                  <Shield className="h-4 w-4 text-[#4A8A5A]" />
                ) : (
                  <ShieldOff className="h-4 w-4 text-[#B5B5B5]" />
                )}
                <span className="text-sm font-medium text-[#0B0B0B]">
                  允许本次打开浏览器采集数据
                </span>
              </label>
              {allowBrowserAutomation && (
                <span className="text-xs text-[#8A8A8A]">
                  （仅本次任务生效，不会永久保存）
                </span>
              )}
            </div>
          )}

          <div className="flex items-end gap-3">
            {mode === "boss-lite" ? (
              /* Boss Lite: single execute button */
              <Button
                onClick={executeBossLite}
                disabled={!goal.trim() || isRunning}
                variant="default"
                size="lg"
                className="w-full lg:w-auto"
              >
                {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                {isRunning ? "执行中，约需1分钟..." : "一键执行"}
              </Button>
            ) : (
              /* Command Center: two-phase flow */
              !currentMission || currentMission.status === "pending_review" || currentMission.status === "pending" ? (
                <>
                  {/* 阶段1: 生成计划 */}
                  <Button
                    onClick={createPlan}
                    disabled={!goal.trim() || isRunning || enabledModules.length === 0}
                    variant="default"
                    size="lg"
                    className="w-full lg:w-auto"
                  >
                    {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                    生成计划
                  </Button>
                  {/* 阶段2: 确认执行（仅在计划已创建时显示） */}
                  {currentMission && (
                    <Button
                      onClick={confirmRun}
                      disabled={isRunning}
                      variant="default"
                      size="lg"
                      className="w-full lg:w-auto bg-green hover:bg-green/90"
                    >
                      {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      确认执行
                    </Button>
                  )}
                </>
              ) : (
                <Button
                  onClick={confirmRun}
                  disabled={isRunning}
                  variant="outline"
                  size="lg"
                  className="w-full lg:w-auto"
                >
                  {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  重新执行
                </Button>
              )
            )}
          </div>
        </div>
      </motion.div>

      {/* Boss Lite Progress — 轻量进度展示 */}
      {mode === "boss-lite" && isRunning && !liteResult && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        >
          <div className="flex items-center gap-3 mb-5">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="font-medium text-[#0B0B0B]">
              正在协调 5 个 Agent 并行工作，通常需要 15–30 秒
            </span>
          </div>
          <div className="space-y-3">
            {[
              "Boss 正在拆解目标",
              "市场调研 / 营销 / 视觉 / 数据 / 落地页正在并行执行",
              "Boss 正在汇总作战报告",
              "保存到交付中心",
            ].map((label, phase) => (
              <div key={phase} className="flex items-center gap-3">
                {liteProgressPhase > phase ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-green" />
                ) : liteProgressPhase === phase ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                ) : (
                  <div className="h-4 w-4 shrink-0 rounded-full border border-[#D4D4D4]" />
                )}
                <span
                  className={cn(
                    "text-sm",
                    liteProgressPhase > phase
                      ? "text-green"
                      : liteProgressPhase === phase
                        ? "text-[#0B0B0B] font-medium"
                        : "text-[#B5B5B5]"
                  )}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Mission 状态横幅 + 审核按钮 — only in command-center mode */}
      {mode === "command-center" && currentMission && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "p-4 rounded-2xl border",
            currentMission.status === "ready_for_review" ? "border-green/30 bg-green/5" :
            currentMission.status === "partial" ? "border-yellow/30 bg-yellow/5" :
            currentMission.status === "failed" ? "border-red/30 bg-red/5" :
            currentMission.status === "running" ? "border-blue/30 bg-blue/5" :
            currentMission.status === "done" ? "border-green/20 bg-green/2" :
            "border-[#E5E5E5] bg-white"
          )}
        >
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {currentMission.status === "running" ? (
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              ) : currentMission.status === "ready_for_review" || currentMission.status === "done" ? (
                <CheckCircle2 className="h-5 w-5 text-green" />
              ) : currentMission.status === "partial" ? (
                <AlertCircle className="h-5 w-5 text-yellow" />
              ) : currentMission.status === "failed" ? (
                <AlertCircle className="h-5 w-5 text-red-500" />
              ) : (
                <FileText className="h-5 w-5 text-muted-foreground" />
              )}
              <div>
                <span className="font-medium text-sm">{missionStatusText(currentMission.status)}</span>
                {currentMission.metrics && (
                  <span className="ml-3 text-xs text-muted-foreground">
                    {currentMission.metrics.succeeded_modules}/{currentMission.metrics.total_modules} 模块完成
                    {currentMission.metrics.warning_count > 0 && ` · ${currentMission.metrics.warning_count} 警告`}
                    {currentMission.metrics.failed_modules > 0 && ` · ${currentMission.metrics.failed_modules} 失败`}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* 接受结果按钮 */}
              {(currentMission.status === "ready_for_review" || currentMission.status === "partial") && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={acceptMission}
                  disabled={isRunning}
                  className="gap-1 bg-green hover:bg-green/90"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  接受结果
                </Button>
              )}
              {/* 重新执行按钮 */}
              {currentMission.status !== "running" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={confirmRun}
                  disabled={isRunning}
                  className="gap-1"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  重新执行全部
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* Boss Lite Results */}
      {mode === "boss-lite" && liteResult && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Summary Banner */}
          <div className={cn(
            "p-4 rounded-2xl border",
            liteResult.ok ? "border-green/30 bg-green/5" : "border-red/30 bg-red/5"
          )}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {liteResult.ok ? (
                  <CheckCircle2 className="h-5 w-5 text-green" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-500" />
                )}
                <div>
                  <span className="font-medium text-sm">{liteResult.summary.text}</span>
                  {liteResult.delivery_task_id && (
                    <span className="ml-3 text-xs text-muted-foreground">
                      交付物 ID: {liteResult.delivery_task_id}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success">{liteResult.summary.succeeded} 成功</Badge>
                {liteResult.summary.failed > 0 && (
                  <Badge variant="destructive">{liteResult.summary.failed} 失败</Badge>
                )}
                {liteResult.summary.total_duration_ms != null && liteResult.summary.total_duration_ms > 0 && (
                  <Badge variant="outline">
                    耗时 {(liteResult.summary.total_duration_ms / 1000).toFixed(1)}s
                  </Badge>
                )}
                {/* Handoff 状态 Badge */}
                {(() => {
                  const hoEnabled = liteResult.handoff_enabled ?? liteResult.structured_output?.handoff_enabled
                  if (!hoEnabled) return null
                  const sources = liteResult.structured_output?.handoff_sources
                  const targets = liteResult.structured_output?.handoff_targets
                  if (sources?.length && targets?.length) {
                    return (
                      <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/5 text-primary">
                        {sources.join(" / ")} → {targets.join(" / ")}
                      </Badge>
                    )
                  }
                  return (
                    <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/5 text-primary">
                      部门协作已启用
                    </Badge>
                  )
                })()}
                {liteResult.delivery_task_id && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled
                    className="gap-1 opacity-70"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    已保存到交付中心
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Agent Navigation + Results */}
          <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
            <div className="space-y-3">
              {liteResult.results.map((r) => {
                const isActive = liteActiveAgent === r.agent_id

                return (
                  <button
                    key={r.agent_id}
                    type="button"
                    onClick={() => setLiteActiveAgent(r.agent_id)}
                    className={cn(
                      "w-full rounded-xl border p-4 text-left transition-all",
                      isActive
                        ? "border-primary/50 bg-primary/10"
                        : "border-border bg-card/70 hover:border-primary/30 hover:bg-accent/50"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background/70">
                        {r.ok ? (
                          <CheckCircle2 className="h-4 w-4 text-green" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-yellow" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{r.title}</span>
                          <Badge variant={r.ok ? "success" : "destructive"}>
                            {r.ok ? "成功" : "失败"}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {extractAgentSummary(r.agent_id, r.summary, r.structured_output)}
                        </p>
                        {/* Handoff 标记 */}
                        {r.used_handoff && (
                          <div className="mt-1.5 flex items-center gap-1.5">
                            <Badge variant="outline" className="text-[10px] border-primary/30 bg-primary/5 text-primary">
                              已参考上游洞察
                            </Badge>
                            {r.handoff_sources && r.handoff_sources.length > 0 && (
                              <span className="text-[10px] text-[#8A8A8A]">
                                来源：{r.handoff_sources.join(" / ")}
                              </span>
                            )}
                          </div>
                        )}
                        {r.duration_ms != null && r.duration_ms > 0 && (
                          <p className="mt-1 text-xs text-[#8A8A8A]">
                            耗时 {(r.duration_ms / 1000).toFixed(1)}s
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Active Agent Result Detail */}
            {liteResult.results.map((r) => {
              if (r.agent_id !== liteActiveAgent) return null
              const Icon = agentIcons[r.agent_id] || FileText

              return (
                <motion.div
                  key={r.agent_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="min-h-[520px] p-6 rounded-2xl border border-[#E5E5E5] bg-white">
                    <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                          <Icon className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <h2 className="text-xl font-semibold">{r.title}</h2>
                          <p className="text-sm text-muted-foreground">{r.agent_id}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                      <Badge variant={r.ok ? "success" : "destructive"}>
                        {r.ok ? "成功" : "失败"}
                      </Badge>
                      {r.duration_ms != null && r.duration_ms > 0 && (
                        <Badge variant="outline">
                          耗时 {(r.duration_ms / 1000).toFixed(1)}s
                        </Badge>
                      )}
                    </div>
                    </div>

                    {/* Summary — always show extracted summary */}
                    <div className="rounded-lg border border-border bg-background/60 p-4 mb-4">
                      <h4 className="mb-2 text-sm font-medium">摘要</h4>
                      <p className="text-sm text-muted-foreground">
                        {extractAgentSummary(r.agent_id, r.summary, r.structured_output)}
                      </p>
                    </div>

                    {/* Handoff 信息 — 仅在 used_handoff 时显示 */}
                    {r.used_handoff && r.handoff_sources && r.handoff_sources.length > 0 && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 mb-4">
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-primary" />
                          <span className="text-sm text-primary">
                            本部门输出已参考上游洞察：<strong>{r.handoff_sources.join(" / ")}</strong>
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Key Fields — structured readable block */}
                    {r.structured_output && (() => {
                      const keyFields = extractKeyFields(r.agent_id, r.structured_output)
                      if (keyFields.length === 0) return null
                      return (
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 mb-4">
                          <h4 className="mb-3 text-sm font-medium text-primary">关键信息</h4>
                          <div className="space-y-2">
                            {keyFields.map((field, i) => (
                              <div key={i} className="flex gap-2">
                                <span className="shrink-0 text-xs font-medium text-muted-foreground min-w-[80px]">
                                  {field.label}
                                </span>
                                <span className="text-sm">{field.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })()}

                    {/* Structured Output — raw JSON (collapsible) */}
                    {r.structured_output && Object.keys(r.structured_output).length > 0 && (() => {
                      const so = r.structured_output
                      const provider = so.provider as string | undefined
                      return (
                        <div className="space-y-3">
                          {/* Provider info */}
                          {provider && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>Provider:</span>
                              <Badge variant="outline">{provider}</Badge>
                            </div>
                          )}

                          {/* Raw JSON */}
                          <details className="rounded-lg border border-border bg-background/60">
                            <summary className="p-4 cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                              查看原始 JSON 输出
                            </summary>
                            <pre className="px-4 pb-4 whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground max-h-[400px] overflow-y-auto">
                              {JSON.stringify(so, null, 2)}
                            </pre>
                          </details>
                        </div>
                      )
                    })()}

                    {/* Warnings */}
                    {r.warnings.length > 0 && (
                      <div className="mt-4 rounded-lg border border-yellow/20 bg-yellow/10 p-3">
                        {r.warnings.map((w, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm text-yellow">
                            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Errors */}
                    {r.error && (
                      <div className="mt-4 rounded-lg border border-red/20 bg-red/5 p-3">
                        <div className="flex items-start gap-2 text-sm text-red-500">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                          <span>{r.error}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* 模块导航 + 结果 — only in command-center mode */}
      {mode === "command-center" && modules.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="space-y-3">
            {modules.map((module) => {
              const Icon = moduleIcons[module.module_id] || FileText
              const isActive = activeModule === module.module_id

              return (
                <button
                  key={module.module_id}
                  type="button"
                  onClick={() => setActiveModule(module.module_id)}
                  className={cn(
                    "w-full rounded-xl border p-4 text-left transition-all",
                    isActive
                      ? "border-primary/50 bg-primary/10"
                      : "border-border bg-card/70 hover:border-primary/30 hover:bg-accent/50"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background/70">
                      {module.status === "running" ? (
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      ) : module.status === "done" ? (
                        <CheckCircle2 className="h-4 w-4 text-green" />
                      ) : module.status === "failed" && module.mode === "blocked" ? (
                        <ShieldOff className="h-4 w-4 text-orange-500" />
                      ) : module.status === "failed" ? (
                        <AlertCircle className="h-4 w-4 text-yellow" />
                      ) : module.status === "skipped" ? (
                        <SkipForward className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Icon className="h-4 w-4 text-primary" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{module.title}</span>
                        {statusBadge(module.status)}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {moduleDescriptions[module.module_id] || ""}
                      </p>
                      {module.duration_ms != null && module.duration_ms > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          耗时 {formatDuration(module.duration_ms)}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          <motion.div
            key={activeModule}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="min-h-[520px] p-6 rounded-2xl border border-[#E5E5E5] bg-white">
              {activeResult && (
                <>
                  <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        {(() => {
                          const Icon = moduleIcons[activeResult.module_id] || FileText
                          return <Icon className="h-5 w-5 text-primary" />
                        })()}
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold">{activeResult.title}</h2>
                        <p className="text-sm text-muted-foreground">
                          {moduleDescriptions[activeResult.module_id] || ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {statusBadge(activeResult.status)}
                      {activeResult.confidence > 0 && (
                        <Badge variant="outline">置信度 {Math.round(activeResult.confidence * 100)}%</Badge>
                      )}
                      {activeResult.duration_ms != null && activeResult.duration_ms > 0 && (
                        <Badge variant="outline">{formatDuration(activeResult.duration_ms)}</Badge>
                      )}
                      {activeResult.status !== "running" && activeResult.status !== "skipped" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => rerunModule(activeResult.module_id)}
                          disabled={isRunning}
                          className="gap-1"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          重跑
                        </Button>
                      )}
                    </div>
                  </div>

                  {activeResult.status === "pending" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/40 text-center">
                      <FileText className="mb-3 h-10 w-10 text-muted-foreground" />
                      <h3 className="font-medium">模块尚未执行</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        点击上方「确认执行」按钮开始生成结果。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "running" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-primary/20 bg-primary/5 text-center">
                      <Loader2 className="mb-3 h-10 w-10 animate-spin text-primary" />
                      <h3 className="font-medium">正在生成 {activeResult.title}</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        正在调用 AI Company OS 的任务分类、路由和结果验证链路。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "skipped" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/40 text-center">
                      <SkipForward className="mb-3 h-10 w-10 text-muted-foreground" />
                      <h3 className="font-medium">模块已跳过</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        此模块未被选中执行。创建任务时可以选择要执行的模块。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "failed" && activeResult.mode === "blocked" && (
                    <div className="rounded-lg border border-orange-300 bg-orange-50 p-4">
                      <div className="flex items-start gap-3">
                        <ShieldOff className="mt-0.5 h-5 w-5 text-orange-500" />
                        <div>
                          <h3 className="font-medium text-orange-700">需要授权浏览器采集</h3>
                          <p className="mt-1 text-sm text-orange-600">
                            {activeResult.error || "此模块需要打开浏览器采集数据，请授权后重试。"}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-3 gap-1"
                            onClick={() => {
                              setAllowBrowserAutomation(true)
                              rerunModule(activeResult.module_id, true)
                            }}
                            disabled={isRunning}
                          >
                            <Shield className="h-3.5 w-3.5" />
                            授权并重试本模块
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeResult.status === "failed" && activeResult.mode !== "blocked" && (
                    <div className="rounded-lg border border-yellow/20 bg-yellow/10 p-4">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="mt-0.5 h-5 w-5 text-yellow" />
                        <div>
                          <h3 className="font-medium">模块未完成</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {activeResult.error || "当前模块执行失败，请稍后重试或检查模型配置。"}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeResult.result && (
                    <div className="space-y-4">
                      <div className="rounded-lg border border-border bg-background/60 p-4">
                        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                          {activeResult.result}
                        </pre>
                      </div>

                      {(activeResult.used_tools || []).length > 0 && (
                        <div className="flex flex-wrap items-center gap-2">
                          {(activeResult.used_tools || []).map((tool) => (
                            <Badge key={tool} variant="outline">
                              {tool}
                            </Badge>
                          ))}
                          {activeResult.mode && (
                            <Badge variant="secondary">mode: {activeResult.mode}</Badge>
                          )}
                          {/* 显示 Provider */}
                          {(() => {
                            const so = activeResult.structured_output as Record<string, unknown>
                            const provider = so?.provider as string
                            return provider ? (
                              <Badge variant="outline" className="gap-1">
                                <span className="text-xs">Provider:</span>
                                {provider}
                              </Badge>
                            ) : null
                          })()}
                        </div>
                      )}

                      {(activeResult.warnings || []).length > 0 && (
                        <div className="rounded-lg border border-yellow/20 bg-yellow/10 p-3">
                          {(activeResult.warnings || []).map((warning) => (
                            <div key={warning} className="flex items-start gap-2 text-sm text-yellow">
                              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                              <span>{warning}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeResult.next_actions && activeResult.next_actions.length > 0 && (
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                          <p className="mb-1 text-sm font-medium">下一步建议</p>
                          {activeResult.next_actions.map((action, i) => (
                            <div key={i} className="text-sm text-muted-foreground">• {action}</div>
                          ))}
                        </div>
                      )}

                      {/* 结构化输出 */}
                      {activeResult.structured_output && Object.keys(activeResult.structured_output).length > 0 && (() => {
                        const so = activeResult.structured_output as Record<string, unknown>
                        const competitors = so.competitors as Array<Record<string, string>> | undefined
                        const pricing = so.pricing as Record<string, unknown> | undefined
                        const evidence = so.evidence as Array<Record<string, string>> | undefined
                        const evidenceFiles = so.evidence_files as string[] | undefined
                        const screenshots = so.screenshots as string[] | undefined
                        const toolCalls = so.tool_calls as Array<Record<string, unknown>> | undefined
                        const imagePlan = so.image_plan as Record<string, unknown> | undefined
                        const provider = so.provider as string | undefined
                        const generatedAt = so.generated_at as string | undefined
                        const summary = so.summary as string | undefined
                        const status = so.status as string | undefined
                        const evidenceGatePassed = so.evidence_gate_passed as boolean | undefined
                        const missingEvidence = so.missing_evidence as string[] | undefined
                        return (
                          <div className="space-y-3">
                            {/* Provider 信息 */}
                            {provider && (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>执行 Provider:</span>
                                <Badge variant="outline">{provider}</Badge>
                                {generatedAt && (
                                  <span>生成时间: {new Date(generatedAt).toLocaleString("zh-CN")}</span>
                                )}
                                {status && (
                                  <Badge variant={status === "success" ? "success" : status === "partial" ? "warning" : "destructive"}>
                                    {status === "success" ? "成功" : status === "partial" ? "证据不足" : "失败"}
                                  </Badge>
                                )}
                              </div>
                            )}

                            {/* 证据门槛状态 */}
                            {evidenceGatePassed !== undefined && (
                              <div className={`rounded-lg border p-3 ${evidenceGatePassed ? "border-green/20 bg-green/5" : "border-yellow/20 bg-yellow/5"}`}>
                                <div className="flex items-center gap-2">
                                  {evidenceGatePassed ? (
                                    <CheckCircle2 className="h-4 w-4 text-green" />
                                  ) : (
                                    <AlertCircle className="h-4 w-4 text-yellow" />
                                  )}
                                  <span className="text-sm font-medium">
                                    {evidenceGatePassed ? "证据门槛已通过" : "证据门槛未通过"}
                                  </span>
                                </div>
                                {!evidenceGatePassed && missingEvidence && missingEvidence.length > 0 && (
                                  <div className="mt-2 text-xs text-muted-foreground">
                                    <p className="font-medium">缺失证据：</p>
                                    {missingEvidence.map((item, i) => (
                                      <p key={i}>• {item}</p>
                                    ))}
                                  </div>
                                )}
                                {!evidenceGatePassed && (
                                  <p className="mt-2 text-xs text-yellow">
                                    ⚠️ 证据不足，不能生成 TOP 推荐结论。请补充更多真实数据后重试。
                                  </p>
                                )}
                              </div>
                            )}

                            {/* 摘要 */}
                            {summary && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">摘要</h4>
                                <p className="text-sm text-muted-foreground">{summary}</p>
                              </div>
                            )}

                            {/* 工具调用记录 */}
                            {Array.isArray(toolCalls) && toolCalls.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  工具调用记录
                                  <Badge variant="secondary" className="ml-2">{toolCalls.length}</Badge>
                                </h4>
                                <div className="space-y-2">
                                  {toolCalls.map((tc, i) => {
                                    const tool = tc.tool as string;
                                    const args = tc.args as Record<string, unknown> | undefined;
                                    const result = tc.result as string | undefined;
                                    return (
                                      <div key={i} className="rounded bg-background/40 p-2 text-xs">
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline">{tool}</Badge>
                                          {args && (
                                            <span className="text-muted-foreground">
                                              args: {JSON.stringify(args).slice(0, 60)}...
                                            </span>
                                          )}
                                        </div>
                                        {result && (
                                          <p className="mt-1 text-muted-foreground">
                                            result: {result.slice(0, 100)}...
                                          </p>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {Array.isArray(competitors) && competitors.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">竞品分析</h4>
                                <div className="space-y-2">
                                  {competitors.map((c, i) => (
                                    <div key={i} className="rounded bg-background/40 p-2 text-sm">
                                      <span className="font-medium">{c.name || ""}</span>
                                      {c.price && <span className="ml-2 text-muted-foreground">价格: {c.price}</span>}
                                      {c.platform && <span className="ml-2 text-muted-foreground">平台: {c.platform}</span>}
                                      {c.source_url && (
                                        <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="ml-2 text-primary hover:underline">
                                          来源 ↗
                                        </a>
                                      )}
                                      {c.details && <p className="mt-1 text-muted-foreground">{c.details}</p>}
                                      {c.strengths && <p className="mt-1 text-muted-foreground">优势: {c.strengths}</p>}
                                      {c.weaknesses && <p className="mt-1 text-muted-foreground">劣势: {c.weaknesses}</p>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {pricing && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">定价信息</h4>
                                <pre className="whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground">
                                  {JSON.stringify(pricing, null, 2)}
                                </pre>
                              </div>
                            )}
                            {Array.isArray(evidence) && evidence.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  采集来源
                                  <Badge variant="secondary" className="ml-2">{evidence.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {evidence.map((ev, i) => (
                                    <div key={i} className="flex items-center gap-2 text-xs">
                                      {ev.url ? (
                                        <a href={ev.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                                          {ev.title || ev.url}
                                        </a>
                                      ) : (
                                        <span>{ev.title || "未知来源"}</span>
                                      )}
                                      {ev.type && <Badge variant="outline" className="text-[10px]">{ev.type}</Badge>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {Array.isArray(evidenceFiles) && evidenceFiles.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  证据文件
                                  <Badge variant="secondary" className="ml-2">{evidenceFiles.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {evidenceFiles.map((file, i) => (
                                    <div key={i} className="text-xs text-muted-foreground">📁 {file}</div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {Array.isArray(screenshots) && screenshots.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  截图
                                  <Badge variant="secondary" className="ml-2">{screenshots.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {screenshots.map((shot, i) => (
                                    <div key={i} className="text-xs text-muted-foreground">🖼️ {shot}</div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {imagePlan && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">图片/拍摄建议</h4>
                                <pre className="whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground">
                                  {JSON.stringify(imagePlan, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        )
                      })()}
                      {activeResult.status === "done" && (!activeResult.structured_output || Object.keys(activeResult.structured_output).length === 0) && (
                        <div className="rounded-lg border border-dashed border-border bg-background/40 p-4 text-center text-sm text-muted-foreground">
                          此模块未生成结构化数据。结果已保存在上方文本中。
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </div>
      )}

      {/* 运行日志面板 — only in command-center mode */}
      {mode === "command-center" && currentMission && events.length > 0 && (
        <div className="p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <button
            type="button"
            onClick={() => setShowEvents(!showEvents)}
            className="flex w-full items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-[#0B0B0B]">
              <FileText className="h-4 w-4 text-[#8A8A8A]" />
              运行日志
              <Badge variant="secondary" className="ml-1">{events.length}</Badge>
            </div>
            <span className="text-xs text-[#8A8A8A]">{showEvents ? "收起" : "展开"}</span>
          </button>

          {showEvents && (
            <div className="mt-4 space-y-2 max-h-[400px] overflow-y-auto">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className="flex items-start gap-3 rounded-lg border border-border bg-background/40 p-3 text-sm"
                >
                  <div className="shrink-0 text-xs text-muted-foreground w-[70px]">
                    {new Date(evt.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={
                        evt.type.includes("failed") ? "destructive" :
                        evt.type.includes("succeeded") ? "success" :
                        evt.type.includes("started") ? "info" :
                        evt.type.includes("skipped") ? "secondary" :
                        "outline"
                      } className="text-xs">
                        {evt.type}
                      </Badge>
                      {evt.module_id && (
                        <span className="text-xs text-muted-foreground">{evt.module_id}</span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-foreground">{evt.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 空状态（无 mission 时） — only in command-center mode */}
      {mode === "command-center" && !currentMission && !showHistory && (
        <div className="p-6 rounded-2xl border border-dashed border-[#E5E5E5] bg-white">
          <div className="flex min-h-[300px] flex-col items-center justify-center text-center">
            <Briefcase className="mb-3 h-12 w-12 text-[#D4D4D4]" />
            <h3 className="text-lg font-medium text-[#0B0B0B]">输入业务目标开始</h3>
            <p className="mt-2 max-w-md text-sm text-[#8A8A8A]">
              系统会先拆成 5 个模块（战略、市场、营销、落地页、执行清单）。您确认后逐一执行，并保存结果供人工审核。
            </p>
          </div>
        </div>
      )}

      {/* 最近 Boss 作战记录 — only in boss-lite mode */}
      {mode === "boss-lite" && !isRunning && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">最近 Boss 作战记录</h3>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadLiteHistory}
              disabled={liteHistoryLoading}
              className="gap-1 text-[#8A8A8A] hover:text-[#0B0B0B]"
            >
              {liteHistoryLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" />
              )}
              刷新
            </Button>
          </div>
          {liteHistoryLoading ? (
            <div className="flex items-center gap-2 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-4 text-sm text-[#6B6B6B]">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载历史记录...
            </div>
          ) : liteHistory.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B]">
              暂无 Boss 作战记录。执行一次 Boss Lite 后，作战报告会自动出现在这里。
            </div>
          ) : (
            <div className="space-y-3">
              {liteHistory.map((task) => (
                <div
                  key={task.task_id}
                  className="flex items-start justify-between gap-4 rounded-xl border border-[#E5E5E5] p-4 transition-all hover:border-[#B5B5B5] hover:bg-[#F9F9F7]"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-xs font-mono text-[#8A8A8A] bg-[#F4F3EF] px-2 py-0.5 rounded">
                        {task.task_id || "—"}
                      </span>
                      {task.artifact_type && (
                        <span className="text-[10px] font-medium text-[#6B6B6B] bg-[#EEF0E8] px-1.5 py-0.5 rounded">
                          {task.artifact_type}
                        </span>
                      )}
                      <span className="text-xs text-[#B5B5B5]">
                        {formatLocalTime(task.created_at)}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-[#0B0B0B] truncate">
                      {task.goal?.trim() || "未命名作战任务"}
                    </p>
                    <p className="mt-1 text-xs text-[#8A8A8A] line-clamp-2">
                      {getSummaryFallback(task)}
                    </p>
                  </div>
                  <div className="shrink-0 flex items-center gap-2">
                    {task.goal?.trim() && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyHistoryGoal(task.task_id, task.goal)}
                          className="gap-1"
                        >
                          <ClipboardList className="h-3.5 w-3.5" />
                          {copiedHistoryGoalId === task.task_id ? "已复制" : "复制目标"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setGoal(task.goal || "")
                            setLiteResult(null)
                            setLiteActiveAgent("")
                            setLiteProgressPhase(0)
                            setTimeout(() => {
                              document.getElementById("boss-goal-input")?.scrollIntoView({ behavior: "smooth", block: "center" })
                            }, 100)
                          }}
                          className="gap-1"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          复用目标
                        </Button>
                      </>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => viewDelivery(task.task_id)}
                      className="gap-1"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      查看交付物
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {/* Boss Lite 空状态 */}
      {mode === "boss-lite" && !liteResult && !isRunning && (
        <div className="p-6 rounded-2xl border border-dashed border-[#E5E5E5] bg-white">
          <div className="flex min-h-[300px] flex-col items-center justify-center text-center">
            <Zap className="mb-3 h-12 w-12 text-[#D4D4D4]" />
            <h3 className="text-lg font-medium text-[#0B0B0B]">Boss Lite：一句话启动多 Agent 协同</h3>
            <p className="mt-2 max-w-md text-sm text-[#8A8A8A]">
              输入业务目标，系统自动拆解为市场调研、营销方案、视觉方案、数据分析、落地页方案 5 个任务，由对应 Agent 依次执行，结果自动保存到交付中心。
            </p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              {["research", "marketing", "image", "data", "website"].map((id) => {
                const Icon = agentIcons[id] || FileText
                return (
                  <div key={id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#E5E5E5] text-xs text-[#8A8A8A]">
                    <Icon className="h-3.5 w-3.5" />
                    {id === "research" ? "市场调研" : id === "marketing" ? "营销方案" : id === "image" ? "视觉方案" : id === "data" ? "数据分析" : "落地页"}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Export Toast */}
      {exportToast && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-8 right-8 z-50 flex items-center gap-2 px-4 py-3 rounded-xl bg-green text-white shadow-lg"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span className="text-sm font-medium">
            已导出 {exportToast === "markdown" ? "Markdown" : "JSON"} 报告
          </span>
        </motion.div>
      )}
    </div>
  )
}

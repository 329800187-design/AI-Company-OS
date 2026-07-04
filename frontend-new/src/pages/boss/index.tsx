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

const examples = [
  "帮我调研 AI 陪伴产品的市场机会，并给出第一版运营动作",
  "给我的知识付费课程做一套小红书推广方案和落地页草稿",
  "分析 5 个同类 SaaS 竞品，找出我们可以切入的差异化卖点",
]

export default function BossPage() {
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

  useEffect(() => {
    loadRecentMissions()
    loadTemplates()

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
              输入一个业务目标，生成市场、营销、页面和执行清单。
            </p>
          </div>

          <div className="flex items-center gap-2">
            {modules.length > 0 && (
              <Badge variant={failedCount > 0 ? "warning" : completedCount === modules.length - skippedCount ? "success" : "secondary"}>
                {completedCount}/{modules.length - skippedCount} 完成
              </Badge>
            )}
            {currentMission && (
              <Button variant="outline" size="sm" onClick={() => handleExport("markdown")} className="gap-1">
                <Download className="h-3.5 w-3.5" />
                导出
              </Button>
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

      {/* 历史面板 */}
      {showHistory && (
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

            {/* 模块选择 + 模板入口 */}
            {!currentMission && (
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

          {/* 浏览器自动化授权 */}
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

          <div className="flex items-end gap-3">
            {!currentMission || currentMission.status === "pending_review" || currentMission.status === "pending" ? (
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
            )}
          </div>
        </div>
      </motion.div>

      {/* Mission 状态横幅 + 审核按钮 */}
      {currentMission && (
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

      {/* 模块导航 + 结果 */}
      {modules.length > 0 && (
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

      {/* 运行日志面板 */}
      {currentMission && events.length > 0 && (
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

      {/* 空状态（无 mission 时） */}
      {!currentMission && !showHistory && (
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

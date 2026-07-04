import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Briefcase,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Search,
  RefreshCw,
  Plus,
  ArrowRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import { useAppStore } from "@/stores/app"

interface MissionSummary {
  mission_id: string
  goal: string
  status: string
  created_at: string
  updated_at?: string
}

const statusConfig: Record<string, { label: string; variant: string; icon: React.ElementType }> = {
  pending: { label: "待执行", variant: "secondary", icon: Clock },
  running: { label: "执行中", variant: "info", icon: Loader2 },
  done: { label: "已完成", variant: "success", icon: CheckCircle2 },
  failed: { label: "失败", variant: "destructive", icon: XCircle },
}

export default function MissionsPage() {
  const [missions, setMissions] = useState<MissionSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const setCurrentPage = useAppStore((s) => s.setCurrentPage)

  useEffect(() => {
    loadMissions()
  }, [])

  const loadMissions = async () => {
    setIsLoading(true)
    try {
      const data = await api.listMissions(50)
      setMissions(data.missions || [])
    } catch {
      setMissions([])
    } finally {
      setIsLoading(false)
    }
  }

  const filteredMissions = missions.filter((m) => {
    if (filter !== "all" && m.status !== filter) return false
    if (searchQuery && !m.goal.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const stats = {
    total: missions.length,
    done: missions.filter((m) => m.status === "done").length,
    running: missions.filter((m) => m.status === "running").length,
    failed: missions.filter((m) => m.status === "failed").length,
    pending: missions.filter((m) => m.status === "pending").length,
  }

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr)
      const now = new Date()
      const diffMs = now.getTime() - d.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)
      const diffDays = Math.floor(diffMs / 86400000)

      if (diffMins < 1) return "刚刚"
      if (diffMins < 60) return `${diffMins} 分钟前`
      if (diffHours < 24) return `${diffHours} 小时前`
      if (diffDays < 7) return `${diffDays} 天前`
      return d.toLocaleDateString("zh-CN")
    } catch {
      return dateStr
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <Briefcase className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">任务中心</h1>
            <p className="text-sm text-muted-foreground">管理你的所有 Mission</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadMissions} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setCurrentPage("boss")} className="gap-2">
            <Plus className="w-4 h-4" />
            新建任务
          </Button>
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-2 md:grid-cols-5 gap-3"
      >
        {[
          { label: "全部", value: stats.total, color: "text-foreground" },
          { label: "已完成", value: stats.done, color: "text-green" },
          { label: "执行中", value: stats.running, color: "text-primary" },
          { label: "失败", value: stats.failed, color: "text-destructive" },
          { label: "待执行", value: stats.pending, color: "text-muted-foreground" },
        ].map((stat) => (
          <button
            key={stat.label}
            onClick={() => setFilter(filter === stat.label ? "all" : stat.label === "全部" ? "all" : stat.label === "已完成" ? "done" : stat.label === "执行中" ? "running" : stat.label === "失败" ? "failed" : "pending")}
            className={`p-4 rounded-xl border bg-white text-left transition-all ${
              (stat.label === "全部" && filter === "all") ||
              (stat.label === "已完成" && filter === "done") ||
              (stat.label === "执行中" && filter === "running") ||
              (stat.label === "失败" && filter === "failed") ||
              (stat.label === "待执行" && filter === "pending")
                ? "border-primary/50 bg-primary/5"
                : "border-[#E5E5E5] hover:border-[#B5B5B5]"
            }`}
          >
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-sm text-muted-foreground">{stat.label}</p>
          </button>
        ))}
      </motion.div>

      {/* Search */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="relative"
      >
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索任务..."
          className="w-full pl-10 pr-4 py-3 rounded-xl border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-primary/50"
        />
      </motion.div>

      {/* Mission List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : filteredMissions.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="p-12 rounded-2xl border border-dashed border-[#E5E5E5] bg-white text-center"
          >
            <Briefcase className="w-12 h-12 mx-auto mb-4 text-[#D4D4D4]" />
            <h3 className="text-lg font-medium mb-2">
              {searchQuery ? "没有匹配的任务" : "暂无任务"}
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              {searchQuery
                ? "尝试其他关键词"
                : "去「老板指挥台」输入一个业务目标开始"}
            </p>
            {!searchQuery && (
              <Button onClick={() => setCurrentPage("boss")} className="gap-2">
                <Plus className="w-4 h-4" />
                创建第一个任务
              </Button>
            )}
          </motion.div>
        ) : (
          filteredMissions.map((mission, i) => {
            const statusInfo = statusConfig[mission.status] || statusConfig.pending
            const StatusIcon = statusInfo.icon

            return (
              <motion.div
                key={mission.mission_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.03, 0.3) }}
              >
                <button
                  onClick={() => {
                    sessionStorage.setItem("load_mission_id", mission.mission_id)
                    setCurrentPage("boss")
                  }}
                  className="w-full text-left p-5 rounded-2xl border border-[#E5E5E5] bg-white hover:border-[#B5B5B5] hover:translate-y-[-1px] transition-all duration-200 group"
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                      mission.status === "done"
                        ? "bg-green/10"
                        : mission.status === "running"
                          ? "bg-primary/10"
                          : mission.status === "failed"
                            ? "bg-destructive/10"
                            : "bg-muted"
                    }`}>
                      <StatusIcon className={`w-5 h-5 ${
                        mission.status === "running" ? "animate-spin" : ""
                      } ${
                        mission.status === "done"
                          ? "text-green"
                          : mission.status === "running"
                            ? "text-primary"
                            : mission.status === "failed"
                              ? "text-destructive"
                              : "text-muted-foreground"
                      }`} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate mb-1">
                        {mission.goal}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{mission.mission_id}</span>
                        <span>·</span>
                        <span>{formatDate(mission.created_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <Badge variant={statusInfo.variant as any} className="text-xs">
                        {statusInfo.label}
                      </Badge>
                      <ArrowRight className="w-4 h-4 text-[#D4D4D4] group-hover:text-[#8A8A8A] group-hover:translate-x-0.5 transition-all" />
                    </div>
                  </div>
                </button>
              </motion.div>
            )
          })
        )}
      </div>
    </div>
  )
}

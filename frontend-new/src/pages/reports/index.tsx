import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  FileText,
  Download,
  RefreshCw,
  Search,
  AlertTriangle,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3,
  ExternalLink,
} from "lucide-react"
import { api } from "@/api/client"
import { CollaborationRunDetail } from "@/components/features/collaboration-run-detail"
import type { CollaborationRunDetailView } from "@/types"

interface GovernanceRecord {
  run_id: string
  goal: string
  capability_id: string
  status: string
  created_at: string
  updated_at: string
  artifact_path?: string
  result_ref?: string
  failure_reason?: string
  collaboration_plan?: {
    plan_id: string
    goal: string
    status: string
    steps: Array<{
      id: string
      name: string
      task_type: string
      required_capability: string
      status: string
      assigned_agent_id?: string
      result?: {
        ok: boolean
        agent_id?: string
        output?: Record<string, unknown>
        error?: string
      }
    }>
  }
}

interface ArtifactContent {
  run_id: string
  artifact_path: string
  content: string
}

export default function ReportsPage() {
  const [records, setRecords] = useState<GovernanceRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [filter, setFilter] = useState<"all" | "succeeded" | "failed" | "running">("all")
  const [searchQuery, setSearchQuery] = useState("")

  // 详情状态
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [artifactCache, setArtifactCache] = useState<Record<string, ArtifactContent>>({})
  const [collaborationCache, setCollaborationCache] = useState<Record<string, GovernanceRecord["collaboration_plan"]>>({})
  const [collaborationDetailCache, setCollaborationDetailCache] = useState<Record<string, CollaborationRunDetailView>>({})
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState("")
  const [actionLoading, setActionLoading] = useState(false)

  const loadRecords = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.listGovernanceRuns(50, 0)
      setRecords(res.records)
    } catch {
      setError("无法加载报告，请检查后端服务")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadRecords() }, [loadRecords])

  const loadArtifact = async (runId: string) => {
    if (artifactCache[runId]) {
      setSelectedId(runId)
      return
    }
    setSelectedId(runId)
    setDetailLoading(true)
    setDetailError("")
    try {
      const artifact = await api.governanceArtifact(runId)
      setArtifactCache((prev) => ({ ...prev, [runId]: artifact }))
    } catch {
      setDetailError("加载产物失败，该记录可能没有关联的产物文件")
    } finally {
      setDetailLoading(false)
    }
  }

  const handleApprove = async (stepId: string, comment?: string) => {
    const runId = selectedId
    if (!runId) return
    const plan = collaborationCache[runId]
    if (!plan) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepApprove(plan.plan_id, stepId, comment)
      setCollaborationCache((prev) => ({ ...prev, [runId]: updated as GovernanceRecord["collaboration_plan"] }))
      const detail = await api.collaborationPlanGet(plan.plan_id)
      setCollaborationDetailCache((prev) => ({ ...prev, [runId]: detail }))
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "批准失败")
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (stepId: string, comment?: string) => {
    const runId = selectedId
    if (!runId) return
    const plan = collaborationCache[runId]
    if (!plan) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepReject(plan.plan_id, stepId, comment)
      setCollaborationCache((prev) => ({ ...prev, [runId]: updated as GovernanceRecord["collaboration_plan"] }))
      const detail = await api.collaborationPlanGet(plan.plan_id)
      setCollaborationDetailCache((prev) => ({ ...prev, [runId]: detail }))
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "拒绝失败")
    } finally {
      setActionLoading(false)
    }
  }

  const handleRetry = async (stepId: string) => {
    const runId = selectedId
    if (!runId) return
    const plan = collaborationCache[runId]
    if (!plan) return
    setActionLoading(true)
    try {
      const updated = await api.collaborationStepRetry(plan.plan_id, stepId)
      setCollaborationCache((prev) => ({ ...prev, [runId]: updated as GovernanceRecord["collaboration_plan"] }))
      const detail = await api.collaborationPlanGet(plan.plan_id)
      setCollaborationDetailCache((prev) => ({ ...prev, [runId]: detail }))
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "重试失败")
    } finally {
      setActionLoading(false)
    }
  }

  const loadCollaboration = async (runId: string) => {
    if (collaborationDetailCache[runId]) {
      setSelectedId(runId)
      return
    }
    setSelectedId(runId)
    setDetailLoading(true)
    setDetailError("")
    try {
      const existingPlan = collaborationCache[runId]
      const detail = existingPlan ? null : await api.governanceRunDetail(runId)
      const plan = existingPlan || detail?.collaboration_plan
      if (plan) {
        setCollaborationCache((prev) => ({ ...prev, [runId]: plan }))
        const collaborationDetail = await api.collaborationPlanGet(plan.plan_id)
        setCollaborationDetailCache((prev) => ({ ...prev, [runId]: collaborationDetail }))
      }
    } catch {
      setDetailError("加载协同数据失败")
    } finally {
      setDetailLoading(false)
    }
  }

  const toggleDetail = (record: GovernanceRecord) => {
    if (selectedId === record.run_id) {
      setSelectedId(null)
      return
    }
    // 协同记录：从缓存或 API 加载协同数据
    if (record.capability_id === "collaboration.controlled") {
      loadCollaboration(record.run_id)
      return
    }
    // 只有 succeeded 且有 artifact_path 的记录才尝试加载产物
    if (record.status === "succeeded" && record.artifact_path) {
      loadArtifact(record.run_id)
    } else {
      setSelectedId(record.run_id)
    }
  }

  const handleExport = async (runId: string) => {
    try {
      const artifact = await api.governanceArtifact(runId)
      const blob = new Blob([artifact.content], { type: "text/markdown;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `governance-report-${runId.slice(0, 8)}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setError("导出失败，请重试")
    }
  }

  const filteredRecords = records.filter((r) => {
    if (filter === "succeeded" && r.status !== "succeeded") return false
    if (filter === "failed" && r.status !== "failed") return false
    if (filter === "running" && r.status !== "running") return false
    if (searchQuery && !r.goal.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const stats = {
    total: records.length,
    succeeded: records.filter((r) => r.status === "succeeded").length,
    failed: records.filter((r) => r.status === "failed").length,
    running: records.filter((r) => r.status === "running").length,
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "succeeded": return <CheckCircle2 className="w-4 h-4 text-emerald-400" />
      case "failed": return <XCircle className="w-4 h-4 text-red-400" />
      case "running": return <Clock className="w-4 h-4 text-blue-400 animate-pulse" />
      default: return <Clock className="w-4 h-4 text-[#666]" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "succeeded": return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
      case "failed": return "bg-red-500/10 text-red-400 border-red-500/20"
      case "running": return "bg-blue-500/10 text-blue-400 border-blue-500/20"
      default: return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
    }
  }

  const statusLabel = (s: string) =>
    s === "succeeded" ? "成功" : s === "failed" ? "失败" : s === "running" ? "运行中" : s === "planned" ? "已规划" : s === "rejected" ? "已拒绝" : s === "needs_clarification" ? "需澄清" : s

  return (
    <div className="min-h-screen bg-[#0B0B0B] p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">报告中心</h1>
              <p className="text-sm text-[#8A8A8A]">查看最近通过 Governance 生成的产物</p>
            </div>
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="grid grid-cols-4 gap-4 mb-6"
        >
          <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-xs text-[#8A8A8A] mt-1">总记录数</div>
          </div>
          <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
            <div className="text-2xl font-bold text-emerald-400">{stats.succeeded}</div>
            <div className="text-xs text-[#8A8A8A] mt-1">成功</div>
          </div>
          <div className="p-4 bg-red-500/5 border border-red-500/10 rounded-xl">
            <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
            <div className="text-xs text-[#8A8A8A] mt-1">失败</div>
          </div>
          <div className="p-4 bg-blue-500/5 border border-blue-500/10 rounded-xl">
            <div className="text-2xl font-bold text-blue-400">{stats.running}</div>
            <div className="text-xs text-[#8A8A8A] mt-1">运行中</div>
          </div>
        </motion.div>

        {/* Filters & Search */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="flex gap-3 mb-6"
        >
          <div className="flex gap-1 bg-white/5 border border-white/10 rounded-xl p-1">
            {(["all", "succeeded", "failed", "running"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  filter === f ? "bg-white text-black" : "text-[#8A8A8A] hover:text-white"
                }`}
              >
                {f === "all" ? "全部" : f === "succeeded" ? "成功" : f === "failed" ? "失败" : "运行中"}
              </button>
            ))}
          </div>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#666]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索报告..."
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#666] text-sm focus:outline-none focus:border-white/30"
            />
          </div>
          <button onClick={loadRecords} disabled={loading}
            className="px-4 py-2 bg-white/10 border border-white/10 text-white rounded-xl hover:bg-white/15 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </motion.div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3"
            >
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span className="text-sm text-red-300">{error}</span>
              <button onClick={() => setError("")} className="ml-auto text-red-400 hover:text-red-300">
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Record List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-[#8A8A8A]">加载中...</p>
            </div>
          </div>
        ) : filteredRecords.length === 0 ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20"
          >
            <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-4">
              <BarChart3 className="w-8 h-8 text-[#666]" />
            </div>
            <h3 className="text-lg font-medium text-white mb-2">
              {searchQuery || filter !== "all" ? "未找到匹配的报告" : "还没有报告"}
            </h3>
            <p className="text-sm text-[#8A8A8A]">
              {searchQuery || filter !== "all" ? "尝试调整筛选条件" : "完成一个任务后，报告会自动出现在这里"}
            </p>
          </motion.div>
        ) : (
          <div className="space-y-3">
            {filteredRecords.map((record, i) => {
              const isSelected = selectedId === record.run_id
              const artifact = artifactCache[record.run_id]
              const hasArtifact = record.status === "succeeded" && !!record.artifact_path
              const collabPlan = record.collaboration_plan || collaborationCache[record.run_id]
              const collabDetail = collaborationDetailCache[record.run_id]
              const isCollaborationRecord = record.capability_id === "collaboration.controlled"
              const isCollaboration = isCollaborationRecord && !!collabPlan
              const isLoadingArtifact = isSelected && detailLoading && !artifact && !isCollaborationRecord
              const isLoadingCollaboration = isSelected && detailLoading && isCollaborationRecord

              return (
                <motion.div
                  key={record.run_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    {getStatusIcon(record.status)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-medium text-white truncate">{record.goal}</h3>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${getStatusColor(record.status)}`}>
                          {statusLabel(record.status)}
                        </span>
                        {record.capability_id && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            {record.capability_id}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-[#666]">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {record.created_at ? new Date(record.created_at).toLocaleString() : "未知"}
                        </span>
                        <span>ID: {record.run_id.slice(0, 12)}</span>
                        {record.failure_reason && (
                          <span className="text-red-400 truncate max-w-[200px]">
                            {record.failure_reason}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleDetail(record)}
                        className={`px-3 py-1.5 text-[10px] rounded-lg transition-colors ${
                          hasArtifact || isCollaborationRecord
                            ? "bg-white/10 text-white hover:bg-white/15"
                            : "bg-white/5 text-[#666] hover:bg-white/10"
                        }`}
                      >
                        {isSelected ? "收起" : isCollaboration ? "查看协同" : hasArtifact ? "查看产物" : "状态详情"}
                      </button>
                      {hasArtifact && !isCollaborationRecord && (
                        <button
                          onClick={() => handleExport(record.run_id)}
                          className="px-3 py-1.5 text-[10px] bg-white text-black rounded-lg hover:bg-white/90 transition-colors flex items-center gap-1"
                        >
                          <Download className="w-3 h-3" />
                          导出
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expanded Detail */}
                  <AnimatePresence>
                    {isSelected && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-4 pt-4 border-t border-white/10">
                          {/* Loading artifact */}
                          {isLoadingArtifact && (
                            <div className="flex items-center gap-2 py-4">
                              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                              <span className="text-xs text-[#8A8A8A]">加载产物...</span>
                            </div>
                          )}

                          {isLoadingCollaboration && (
                            <div className="flex items-center gap-2 py-4">
                              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                              <span className="text-xs text-[#8A8A8A]">加载协同详情...</span>
                            </div>
                          )}

                          {/* Artifact load error */}
                          {isSelected && detailError && !artifact && (
                            <div className="flex items-center gap-2 py-4 text-amber-400">
                              <AlertTriangle className="w-4 h-4" />
                              <span className="text-xs">{detailError}</span>
                              <button onClick={() => isCollaborationRecord ? loadCollaboration(record.run_id) : loadArtifact(record.run_id)}
                                className="text-xs underline ml-2 hover:text-amber-300">重试</button>
                            </div>
                          )}

                          {/* Record info for non-artifact records */}
                          {record.status !== "succeeded" && (
                            <div className="space-y-3">
                              <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 bg-white/5 rounded-lg">
                                  <div className="text-[10px] text-[#8A8A8A] mb-1">状态</div>
                                  <div className="text-sm text-white">{statusLabel(record.status)}</div>
                                </div>
                                <div className="p-3 bg-white/5 rounded-lg">
                                  <div className="text-[10px] text-[#8A8A8A] mb-1">能力类型</div>
                                  <div className="text-sm text-white">{record.capability_id || "未知"}</div>
                                </div>
                              </div>
                              {record.failure_reason && (
                                <div className="p-3 bg-red-500/5 border border-red-500/10 rounded-lg">
                                  <div className="text-[10px] text-red-400 mb-1">失败原因</div>
                                  <p className="text-xs text-red-300">{record.failure_reason}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Artifact content */}
                          {artifact && (
                            <div className="space-y-3">
                              <div className="flex items-center gap-2">
                                <ExternalLink className="w-4 h-4 text-emerald-400" />
                                <span className="text-xs font-medium text-emerald-400">Markdown 产物</span>
                              </div>
                              <div className="p-4 bg-white/5 border border-white/10 rounded-lg max-h-[500px] overflow-auto">
                                <pre className="text-xs text-[#8A8A8A] whitespace-pre-wrap font-mono leading-relaxed">
                                  {artifact.content}
                                </pre>
                              </div>
                            </div>
                          )}

                          {/* Collaboration steps */}
                          {isCollaboration && collabPlan && (
                            <CollaborationRunDetail
                              planId={collabPlan.plan_id}
                              status={collabPlan.status}
                              steps={collabPlan.steps}
                              timeline={collabDetail?.timeline}
                              artifacts={collabDetail?.artifacts}
                              onApprove={handleApprove}
                              onReject={handleReject}
                              onRetry={handleRetry}
                              actionLoading={actionLoading}
                            />
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

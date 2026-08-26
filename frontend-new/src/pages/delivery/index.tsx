import { useState, useEffect, useCallback, useRef } from "react"
import { motion } from "framer-motion"
import {
  Package, Loader2, AlertCircle, Copy, Check, Eye, EyeOff, Search, X, Download, ExternalLink,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"
import DeliveryDetail from "./detail"

interface DeliveryTask {
  task_id: string
  goal: string
  agent_id: string
  artifact_type: string
  source_page: string
  created_at: string
  artifact_path: string
  result_path: string
}

const PAGE_SIZE = 50

const AGENT_COLORS: Record<string, string> = {
  marketing: "bg-blue-100 text-blue-800",
  image: "bg-purple-100 text-purple-800",
  data: "bg-green-100 text-green-800",
  research: "bg-amber-100 text-amber-800",
  website: "bg-cyan-100 text-cyan-800",
}

export default function DeliveryPage() {
  // 从 URL 读取 taskId
  const getTaskIdFromUrl = () => {
    const params = new URLSearchParams(window.location.search)
    return params.get("taskId")
  }
  const [detailTaskId, setDetailTaskId] = useState<string | null>(getTaskIdFromUrl)

  // 列表状态（hooks 必须在条件 return 之前声明）
  const [tasks, setTasks] = useState<DeliveryTask[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const taskCountRef = useRef(0)

  // 筛选
  const [filterAgent, setFilterAgent] = useState("")
  const [filterType, setFilterType] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")

  // 预览
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState("")
  const [previewLoading, setPreviewLoading] = useState(false)

  // 复制
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const navigateToDetail = (taskId: string) => {
    const url = new URL(window.location.href)
    url.searchParams.set("taskId", taskId)
    window.history.pushState({}, "", url.toString())
    setDetailTaskId(taskId)
  }

  const navigateBack = () => {
    const url = new URL(window.location.href)
    url.searchParams.delete("taskId")
    window.history.pushState({}, "", url.toString())
    setDetailTaskId(null)
  }

  // 监听浏览器后退/前进
  useEffect(() => {
    const handler = () => {
      const params = new URLSearchParams(window.location.search)
      setDetailTaskId(params.get("taskId"))
    }
    window.addEventListener("popstate", handler)
    return () => window.removeEventListener("popstate", handler)
  }, [])

  const fetchTasks = useCallback(async (reset = true) => {
    if (reset) {
      setLoading(true)
    } else {
      setLoadingMore(true)
    }
    setError(null)
    try {
      const resp = await api.listMiniDeliveryTasks({
        q: debouncedQuery || undefined,
        agent_id: filterAgent || undefined,
        artifact_type: filterType || undefined,
        limit: PAGE_SIZE,
        offset: reset ? 0 : taskCountRef.current,
      })
      if (reset) {
        setTasks(resp.tasks)
        taskCountRef.current = resp.tasks.length
      } else {
        setTasks(prev => [...prev, ...resp.tasks])
        taskCountRef.current += resp.tasks.length
      }
      setWarnings(resp.warnings)
      setTotal(resp.total)
      setHasMore(resp.has_more)
    } catch (error) {
      setError(error instanceof Error ? error.message : "加载失败")
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [debouncedQuery, filterAgent, filterType])

  // 搜索 debounce
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // debouncedQuery 变化时重置分页
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchTasks(true)
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [fetchTasks])

  const handleLoadMore = () => {
    fetchTasks(false)
  }

  const handlePreview = async (taskId: string) => {
    if (previewId === taskId) {
      setPreviewId(null)
      return
    }
    setPreviewId(taskId)
    setPreviewLoading(true)
    try {
      const content = await api.getMiniDeliveryArtifact(taskId)
      setPreviewContent(content)
    } catch (error) {
      setPreviewContent(`加载失败: ${error instanceof Error ? error.message : "未知错误"}`)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleCopyTaskId = async (taskId: string) => {
    await navigator.clipboard.writeText(taskId)
    setCopiedId(taskId)
    setTimeout(() => setCopiedId(null), 1500)
  }

  const handleDownload = (taskId: string) => {
    const downloadUrl = api.getMiniDeliveryDownloadUrl(taskId)
    window.open(downloadUrl, "_blank")
  }

  const formatDate = (iso: string) => {
    if (!iso) return "-"
    try {
      return new Date(iso).toLocaleString("zh-CN", {
        month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
      })
    } catch {
      return iso
    }
  }

  // 收集筛选选项
  const agentIds = [...new Set(tasks.map(t => t.agent_id).filter(Boolean))]
  const artifactTypes = [...new Set(tasks.map(t => t.artifact_type).filter(Boolean))]

  // 如果有 taskId，显示详情页
  if (detailTaskId) {
    return <DeliveryDetail taskId={detailTaskId} onBack={navigateBack} />
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <Package className="w-6 h-6 text-primary" />
        <h1 className="text-2xl font-bold">交付中心</h1>
        <Badge variant="secondary">{total} 项</Badge>
      </div>

      {/* 警告 */}
      {warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
          {warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
        </div>
      )}

      {/* 筛选栏 */}
      <div className="flex flex-wrap gap-3 items-center">
        <Search className="w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="搜索目标、任务 ID、Agent、类型"
          className="border rounded-md px-3 py-1.5 text-sm bg-background flex-1 min-w-[200px]"
        />
        {searchQuery && (
          <Button variant="ghost" size="sm" onClick={() => setSearchQuery("")}>
            <X className="w-3 h-3 mr-1" /> 清除搜索
          </Button>
        )}
        <select
          value={filterAgent}
          onChange={e => setFilterAgent(e.target.value)}
          className="border rounded-md px-3 py-1.5 text-sm bg-background"
        >
          <option value="">全部 Agent</option>
          {agentIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="border rounded-md px-3 py-1.5 text-sm bg-background"
        >
          <option value="">全部类型</option>
          {artifactTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        {(searchQuery || filterAgent || filterType) && (
          <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(""); setFilterAgent(""); setFilterType("") }}>
            <X className="w-3 h-3 mr-1" /> 清除
          </Button>
        )}
      </div>

      {/* 错误 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* 加载 */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* 空状态 */}
      {!loading && tasks.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>暂无交付物</p>
          <p className="text-xs mt-1">执行 Agent 后保存的结果会出现在这里</p>
        </div>
      )}

      {/* 列表 */}
      {!loading && tasks.length > 0 && (
        <div className="space-y-3">
          {tasks.map((task, idx) => (
            <motion.div
              key={task.task_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.03 }}
              className="border rounded-lg p-4 bg-card hover:shadow-sm transition-shadow"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={AGENT_COLORS[task.agent_id] || "bg-gray-100 text-gray-800"}>
                      {task.agent_id}
                    </Badge>
                    <Badge variant="outline">{task.artifact_type}</Badge>
                    {task.source_page && (
                      <span className="text-xs text-muted-foreground">来自 {task.source_page}</span>
                    )}
                  </div>
                  <p className="text-sm font-medium truncate">{task.goal}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{formatDate(task.created_at)}</span>
                    <span className="font-mono">{task.task_id}</span>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigateToDetail(task.task_id)}
                    title="查看详情"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handlePreview(task.task_id)}
                    title="快速预览"
                  >
                    {previewId === task.task_id ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDownload(task.task_id)}
                    title="下载产物"
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCopyTaskId(task.task_id)}
                    title="复制 task_id"
                  >
                    {copiedId === task.task_id
                      ? <Check className="w-4 h-4 text-green-600" />
                      : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {/* 预览区域 */}
              {previewId === task.task_id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  className="mt-3 border-t pt-3"
                >
                  {previewLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                      <Loader2 className="w-4 h-4 animate-spin" /> 加载产物中...
                    </div>
                  ) : (
                    <pre className="text-xs bg-muted rounded-md p-4 overflow-auto max-h-96 whitespace-pre-wrap font-mono">
                      {previewContent}
                    </pre>
                  )}
                </motion.div>
              )}
            </motion.div>
          ))}

          {/* 加载更多 */}
          {hasMore && (
            <div className="flex justify-center pt-2 pb-4">
              <Button
                variant="outline"
                size="sm"
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" /> 加载中...</>
                ) : (
                  `加载更多（已显示 ${tasks.length} / ${total}）`
                )}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

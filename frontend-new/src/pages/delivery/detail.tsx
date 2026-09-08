import { useState, useEffect, useCallback } from "react"
import { motion } from "framer-motion"
import {
  ArrowLeft, Loader2, AlertCircle, Copy, Check, Download, FileText, Database, Bot, FileDown,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/api/client"

interface TaskDetail {
  task_id: string
  goal: string
  agent_id: string
  artifact_type: string
  source_page: string
  created_at: string
  ok: boolean
  mode: string
  summary: string
  artifact_path: string
  raw_agent_result_path: string
  has_raw_agent_result: boolean
  agent_result_summary?: string
}

const AGENT_COLORS: Record<string, string> = {
  marketing: "bg-blue-100 text-blue-800",
  image: "bg-purple-100 text-purple-800",
  data: "bg-green-100 text-green-800",
  research: "bg-amber-100 text-amber-800",
  website: "bg-cyan-100 text-cyan-800",
}

interface DeliveryDetailProps {
  taskId: string
  onBack: () => void
}

export default function DeliveryDetail({ taskId, onBack }: DeliveryDetailProps) {
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [artifact, setArtifact] = useState("")
  const [loading, setLoading] = useState(true)
  const [artifactLoading, setArtifactLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getMiniDeliveryTaskDetail(taskId)
      setDetail(data)
    } catch (error) {
      setError(error instanceof Error ? error.message : "加载任务详情失败")
    } finally {
      setLoading(false)
    }
  }, [taskId])

  const fetchArtifact = useCallback(async () => {
    setArtifactLoading(true)
    try {
      const content = await api.getMiniDeliveryArtifact(taskId)
      setArtifact(content)
    } catch {
      setArtifact("(产物文件不可用)")
    } finally {
      setArtifactLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchData()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [fetchData])

  useEffect(() => {
    if (loading || error) return

    const timeoutId = window.setTimeout(() => {
      void fetchArtifact()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [loading, error, fetchArtifact])

  const handleCopyTaskId = async () => {
    await navigator.clipboard.writeText(taskId)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleDownload = async () => {
    try {
      await api.downloadMiniDeliveryArtifact(taskId)
    } catch (error) {
      setError(error instanceof Error ? error.message : "下载交付物失败")
    }
  }

  const handlePdfDownload = async () => {
    try {
      await api.downloadMiniDeliveryPdf(taskId)
    } catch (error) {
      setError(error instanceof Error ? error.message : "导出 PDF 失败")
    }
  }

  const formatDate = (iso: string) => {
    if (!iso) return "-"
    try {
      return new Date(iso).toLocaleString("zh-CN", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit",
      })
    } catch {
      return iso
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="w-4 h-4 mr-2" /> 返回列表
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      </div>
    )
  }

  if (!detail) return null

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 顶部导航 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="w-4 h-4 mr-2" /> 返回列表
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopyTaskId}>
            {copied ? <Check className="w-4 h-4 mr-1 text-green-600" /> : <Copy className="w-4 h-4 mr-1" />}
            {copied ? "已复制" : "复制 ID"}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-1" /> 下载
          </Button>
          <Button variant="outline" size="sm" onClick={handlePdfDownload}>
            <FileDown className="w-4 h-4 mr-1" /> 导出 PDF
          </Button>
        </div>
      </div>

      {/* 标题区 */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-2">
          <Badge className={AGENT_COLORS[detail.agent_id] || "bg-gray-100 text-gray-800"}>
            {detail.agent_id}
          </Badge>
          <Badge variant="outline">{detail.artifact_type}</Badge>
          {detail.source_page && (
            <span className="text-xs text-muted-foreground">来自 {detail.source_page}</span>
          )}
          <Badge variant={detail.ok ? "success" : "destructive"}>
            {detail.ok ? "成功" : "失败"}
          </Badge>
        </div>
        <h1 className="text-xl font-bold">{detail.goal}</h1>
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          <span>{formatDate(detail.created_at)}</span>
          <span className="font-mono">{detail.task_id}</span>
          <span>模式: {detail.mode}</span>
        </div>
      </motion.div>

      {/* Artifact 内容 */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="w-4 h-4" /> 交付物内容
            </CardTitle>
          </CardHeader>
          <CardContent>
            {artifactLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
                <Loader2 className="w-4 h-4 animate-spin" /> 加载产物中...
              </div>
            ) : (
              <pre className="text-sm bg-muted rounded-md p-4 overflow-auto max-h-[32rem] whitespace-pre-wrap font-mono leading-relaxed">
                {artifact}
              </pre>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* 元数据 */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="w-4 h-4" /> 元数据
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">任务 ID</span>
                <p className="font-mono text-xs mt-0.5 break-all">{detail.task_id}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Agent</span>
                <p className="mt-0.5">{detail.agent_id}</p>
              </div>
              <div>
                <span className="text-muted-foreground">类型</span>
                <p className="mt-0.5">{detail.artifact_type}</p>
              </div>
              <div>
                <span className="text-muted-foreground">模式</span>
                <p className="mt-0.5">{detail.mode}</p>
              </div>
              <div>
                <span className="text-muted-foreground">状态</span>
                <p className="mt-0.5">{detail.ok ? "✅ 成功" : "❌ 失败"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">创建时间</span>
                <p className="mt-0.5">{formatDate(detail.created_at)}</p>
              </div>
              {detail.summary && (
                <div className="col-span-2">
                  <span className="text-muted-foreground">摘要</span>
                  <p className="mt-0.5">{detail.summary}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Raw Agent Result */}
      {detail.has_raw_agent_result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Bot className="w-4 h-4" /> Agent 原始结果
              </CardTitle>
            </CardHeader>
            <CardContent>
              {detail.agent_result_summary ? (
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {detail.agent_result_summary}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">（无摘要信息）</p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  )
}

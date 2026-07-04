import { useState } from "react"
import { FileText, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { api } from "@/api/client"

interface SaveToDeliveryButtonProps {
  goal: string
  agentId: string
  agentResult: Record<string, unknown>
  sourcePage: string
  artifactType?: string
  disabled?: boolean
}

/**
 * 通用"保存到交付中心"按钮。
 *
 * 内部管理 loading / success / error 状态，
 * 调用 api.saveAgentResultToDelivery() 并展示结果消息。
 *
 * 仅在传入 agentResult 时渲染（由父页面控制）。
 */
export function SaveToDeliveryButton({
  goal,
  agentId,
  agentResult,
  sourcePage,
  artifactType,
  disabled = false,
}: SaveToDeliveryButtonProps) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const handleSave = async () => {
    if (!agentResult) return
    setLoading(true)
    setMessage(null)

    try {
      const response = await api.saveAgentResultToDelivery({
        goal,
        agent_id: agentId,
        agent_result: agentResult,
        source_page: sourcePage,
        ...(artifactType ? { artifact_type: artifactType } : {}),
      })
      setMessage(`✅ 保存成功！任务 ID: ${response.task_id}`)
    } catch (err) {
      setMessage(`❌ 保存失败: ${err instanceof Error ? err.message : "未知错误"}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <Button
        variant="default"
        size="sm"
        onClick={handleSave}
        disabled={disabled || loading}
        className="gap-2"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <FileText className="w-4 h-4" />
        )}
        {loading ? "保存中..." : "保存到交付中心"}
      </Button>
      {message && (
        <span
          className={`text-sm ${
            message.startsWith("✅")
              ? "text-green-700"
              : "text-red-600"
          }`}
        >
          {message}
        </span>
      )}
    </div>
  )
}

import { CheckCircle2, ChevronDown, Clock3, ShieldCheck } from "lucide-react"

interface ActionAuditRecord {
  action_id: string
  connector_id: string
  status: string
  approval_note?: string
  approval_expires_at?: string | null
  cancellation_reason?: string
  preflight?: {
    ready?: boolean
    checked_at?: string
    external_side_effects?: boolean
    target_host?: string
    payload_sha256?: string
    checks?: Array<{ name?: string; passed?: boolean; detail?: string }>
  }
  receipt?: Record<string, unknown>
}

function formatTime(value?: string | null) {
  if (!value) return "未记录"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

export function ActionAuditDetails({ action }: { action: ActionAuditRecord }) {
  const preflight = action.preflight
  const receipt = action.receipt ?? {}
  const receiptDigest = asText(receipt.payload_sha256)
  const receiptTime = asText(receipt.executed_at)
  const targetHost = asText(receipt.target_host) ?? preflight?.target_host
  const statusCode = asNumber(receipt.status_code)
  const requestId = asText(receipt.request_id)
  const checks = preflight?.checks ?? []

  return (
    <details className="group basis-full border-t border-[#E5E5E5] pt-2 text-[11px] text-[#5A5A5A]">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 font-medium text-[#5A5A5A] hover:text-[#0B0B0B]">
        <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
        审计记录
      </summary>
      <div className="mt-2 grid gap-2 border-l-2 border-[#E5E5E5] pl-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-medium text-[#0B0B0B]">连接器</span>
          <span>{action.connector_id}</span>
          {targetHost && <span className="text-[#8A8A8A]">目标主机：{targetHost}</span>}
          <span className="text-[#8A8A8A]">动作 ID：{action.action_id}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="flex items-center gap-1 font-medium text-[#0B0B0B]">
            <ShieldCheck className="h-3.5 w-3.5" />预检
          </span>
          <span>{preflight?.ready ? "已通过" : "尚未通过"}</span>
          {preflight?.checked_at && <span className="text-[#8A8A8A]">{formatTime(preflight.checked_at)}</span>}
          {preflight?.external_side_effects !== undefined && (
            <span className={preflight.external_side_effects ? "text-amber-700" : "text-green-700"}>
              {preflight.external_side_effects ? "执行可能联系外部系统" : "预检无外部副作用"}
            </span>
          )}
        </div>

        {checks.length > 0 && (
          <ul className="grid gap-1">
            {checks.map((check, index) => (
              <li key={`${check.name ?? "check"}-${index}`} className="flex items-start gap-1.5 text-[#777]">
                <CheckCircle2 className={`mt-0.5 h-3 w-3 shrink-0 ${check.passed ? "text-green-700" : "text-red-700"}`} />
                <span>{check.detail || check.name || "已完成检查"}</span>
              </li>
            ))}
          </ul>
        )}

        {(action.approval_note || action.approval_expires_at) && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="flex items-center gap-1 font-medium text-[#0B0B0B]"><Clock3 className="h-3.5 w-3.5" />人工批准</span>
            {action.approval_note && <span>{action.approval_note}</span>}
            {action.approval_expires_at && <span className="text-[#8A8A8A]">有效至 {formatTime(action.approval_expires_at)}</span>}
          </div>
        )}

        {action.status === "executed" && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-medium text-[#0B0B0B]">执行回执</span>
            {receipt.simulated === true && <span className="text-green-700">本地模拟已完成</span>}
            {receipt.delivered === true && <span className="text-green-700">外部投递已确认</span>}
            {receiptTime && <span className="text-[#8A8A8A]">{formatTime(receiptTime)}</span>}
            {statusCode !== null && <span className="text-[#8A8A8A]">HTTP {statusCode}</span>}
            {requestId && <span className="text-[#8A8A8A]">请求 ID：{requestId}</span>}
            {receiptDigest && <span className="break-all text-[#8A8A8A]">载荷摘要：{receiptDigest}</span>}
          </div>
        )}

        {action.status === "cancelled" && action.cancellation_reason && (
          <span className="text-red-700">取消原因：{action.cancellation_reason}</span>
        )}
        {action.status === "failed" && <span className="text-red-700">执行未成功；已保留状态，未自动重试。</span>}
      </div>
    </details>
  )
}

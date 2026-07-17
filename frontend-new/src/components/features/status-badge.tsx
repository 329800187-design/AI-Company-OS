import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react"

interface StatusBadgeProps {
  status: string
  className?: string
}

const statusConfig: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  done: { label: "成功", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: CheckCircle2 },
  failed: { label: "失败", color: "bg-red-500/10 text-red-400 border-red-500/20", icon: XCircle },
  running: { label: "运行中", color: "bg-blue-500/10 text-blue-400 border-blue-500/20", icon: Clock },
  pending: { label: "待执行", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20", icon: Clock },
  skipped: { label: "已跳过", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20", icon: AlertCircle },
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] || { label: status, color: "bg-zinc-500/10 text-zinc-400", icon: Clock }
  const Icon = config.icon

  return (
    <span className={cn("inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border", config.color, className)}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
}

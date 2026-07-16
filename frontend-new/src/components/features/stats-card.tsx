import { cn } from "@/lib/utils"

interface StatsCardProps {
  label: string
  value: string | number
  icon?: React.ReactNode
  variant?: "default" | "success" | "warning" | "danger"
  className?: string
}

const variantStyles = {
  default: "border-[#E5E5E5] bg-white",
  success: "border-emerald-500/20 bg-emerald-500/5",
  warning: "border-amber-500/20 bg-amber-500/5",
  danger: "border-red-500/20 bg-red-500/5",
}

const valueStyles = {
  default: "text-[#0B0B0B]",
  success: "text-emerald-400",
  warning: "text-amber-400",
  danger: "text-red-400",
}

export function StatsCard({ label, value, icon, variant = "default", className }: StatsCardProps) {
  return (
    <div className={cn("p-4 rounded-xl border", variantStyles[variant], className)}>
      {icon && <div className="mb-2">{icon}</div>}
      <div className={cn("text-2xl font-bold", valueStyles[variant])}>{value}</div>
      <div className="mt-1 text-xs text-[#8A8A8A]">{label}</div>
    </div>
  )
}

import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

interface LoadingSpinnerProps {
  text?: string
  className?: string
}

export function LoadingSpinner({ text = "加载中...", className }: LoadingSpinnerProps) {
  return (
    <div className={cn("flex items-center justify-center py-20", className)}>
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-8 h-8 animate-spin text-white" />
        <p className="text-sm text-[#8A8A8A]">{text}</p>
      </div>
    </div>
  )
}

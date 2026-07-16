import { cn } from "@/lib/utils"
import { AlertTriangle, X } from "lucide-react"

interface ErrorAlertProps {
  message: string
  onDismiss?: () => void
  className?: string
}

export function ErrorAlert({ message, onDismiss, className }: ErrorAlertProps) {
  return (
    <div className={cn("p-4 rounded-xl border border-red-500/20 bg-red-500/10 flex items-center gap-3", className)}>
      <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
      <span className="text-sm text-red-300 flex-1">{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-red-400 hover:text-red-300">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}

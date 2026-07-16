import { useEffect, useRef } from "react"
import { AlertTriangle } from "lucide-react"
import { Button } from "./button"

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "danger" | "default"
  onConfirm: () => void
  onCancel: () => void
  onDismiss?: () => void
  confirmDisabled?: boolean
  cancelDisabled?: boolean
}

/** Lightweight modal confirmation dialog with keyboard and focus management. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "danger",
  onConfirm,
  onCancel,
  onDismiss,
  confirmDisabled = false,
  cancelDisabled = false,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const dismiss = onDismiss ?? onCancel

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement
    cancelButtonRef.current?.focus()

    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        dismiss()
      } else if (e.key === "Tab") {
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (!focusable?.length) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    window.addEventListener("keydown", handler)
    return () => {
      window.removeEventListener("keydown", handler)
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus()
      }
    }
  }, [open, dismiss])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      onClick={dismiss}
      data-testid="confirm-dialog-backdrop"
    >
      <div
        ref={dialogRef}
        className="w-full max-w-sm rounded-xl border border-[#E5E5E5] bg-white p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        data-testid="confirm-dialog"
      >
        <div className="flex items-start gap-3 mb-4">
          {variant === "danger" && (
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-50">
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </div>
          )}
          <div>
            <h3 id="confirm-dialog-title" className="text-sm font-medium text-[#0B0B0B]">
              {title}
            </h3>
            <p id="confirm-dialog-description" className="mt-1 whitespace-pre-line text-xs text-[#8A8A8A] leading-relaxed">
              {description}
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button
            ref={cancelButtonRef}
            variant="outline"
            size="sm"
            onClick={onCancel}
            disabled={cancelDisabled}
            data-testid="confirm-dialog-cancel"
            className="h-7 text-xs"
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "danger" ? "destructive" : "default"}
            size="sm"
            onClick={onConfirm}
            disabled={confirmDisabled}
            data-testid="confirm-dialog-confirm"
            className="h-7 text-xs"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}

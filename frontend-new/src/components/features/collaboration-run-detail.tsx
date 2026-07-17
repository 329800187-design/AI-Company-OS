import { Clock3, FileText, History, PackageOpen } from "lucide-react"
import { CollaborationSteps } from "@/components/features/collaboration-steps"
import type {
  CollaborationArtifactView,
  CollaborationStepView,
  CollaborationTimelineEvent,
} from "@/types"

interface CollaborationRunDetailProps {
  planId?: string
  status?: string
  steps?: CollaborationStepView[]
  timeline?: CollaborationTimelineEvent[]
  artifacts?: CollaborationArtifactView[]
  onApprove?: (stepId: string, comment?: string) => void | Promise<void>
  onReject?: (stepId: string, comment?: string) => void | Promise<void>
  onRetry?: (stepId: string) => void | Promise<void>
  actionLoading?: boolean
}

function formatTime(value?: string) {
  if (!value) return "unknown"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function eventTone(eventType?: string) {
  if (eventType?.includes("succeeded")) return "border-emerald-500/20 bg-emerald-500/5 text-emerald-300"
  if (eventType?.includes("failed")) return "border-red-500/20 bg-red-500/5 text-red-300"
  if (eventType?.includes("waiting")) return "border-amber-500/20 bg-amber-500/5 text-amber-300"
  if (eventType?.includes("retry")) return "border-blue-500/20 bg-blue-500/5 text-blue-300"
  return "border-white/10 bg-white/5 text-[#8A8A8A]"
}

function getArtifactLabel(artifact: CollaborationArtifactView) {
  const step = artifact.step_name || artifact.step_id || "unknown step"
  return `${artifact.kind || "file"} · ${step}`
}

export function CollaborationRunDetail({
  planId,
  status,
  steps,
  timeline,
  artifacts,
  onApprove,
  onReject,
  onRetry,
  actionLoading,
}: CollaborationRunDetailProps) {
  return (
    <div className="space-y-4">
      <CollaborationSteps
        planId={planId}
        status={status}
        steps={steps}
        onApprove={onApprove}
        onReject={onReject}
        onRetry={onRetry}
        actionLoading={actionLoading}
      />

      {artifacts && artifacts.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-white">
            <PackageOpen className="h-3.5 w-3.5 text-cyan-300" />
            产物中心
            <span className="rounded-full border border-white/10 px-1.5 py-0.5 text-[10px] text-[#8A8A8A]">
              {artifacts.length}
            </span>
          </div>
          <div className="space-y-2">
            {artifacts.map((artifact, index) => (
              <div
                key={artifact.artifact_id || `${artifact.path}-${index}`}
                className="flex items-start gap-2 rounded-md border border-white/10 bg-black/20 p-2"
              >
                <FileText className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-cyan-300" />
                <div className="min-w-0">
                  <div className="text-[11px] text-white">{getArtifactLabel(artifact)}</div>
                  <div className="mt-0.5 break-all text-[10px] text-[#8A8A8A]">{artifact.path}</div>
                  {artifact.agent_id && (
                    <div className="mt-0.5 text-[10px] text-[#666]">Agent: {artifact.agent_id}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {timeline && timeline.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="mb-3 flex items-center gap-2 text-xs font-medium text-white">
            <History className="h-3.5 w-3.5 text-purple-300" />
            审计时间线
            <span className="rounded-full border border-white/10 px-1.5 py-0.5 text-[10px] text-[#8A8A8A]">
              {timeline.length}
            </span>
          </div>
          <div className="space-y-2">
            {timeline.map((event, index) => (
              <div
                key={event.event_id || `${event.event_type}-${index}`}
                className={`rounded-md border p-2 ${eventTone(event.event_type)}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-medium text-white">
                    {event.summary || event.event_type || "event"}
                  </span>
                  {event.event_type && (
                    <span className="rounded-full border border-white/10 px-1.5 py-0.5 text-[10px]">
                      {event.event_type}
                    </span>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-[10px] text-[#8A8A8A]">
                  <span className="flex items-center gap-1">
                    <Clock3 className="h-3 w-3" />
                    {formatTime(event.timestamp)}
                  </span>
                  {event.actor && <span>Actor: {event.actor}</span>}
                  {event.payload?.step_id != null && <span>Step: {String(event.payload.step_id)}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

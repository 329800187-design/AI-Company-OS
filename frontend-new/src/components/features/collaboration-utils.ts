import type { CollaborationPlanView, CollaborationStepView } from "@/types"

/** Extract collaboration data from the supported governance response shapes. */
export function extractCollaboration(data: Record<string, unknown>): {
  planId?: string
  status?: string
  steps?: CollaborationStepView[]
} | undefined {
  const collaborationPlan = data.collaboration_plan as CollaborationPlanView | undefined
  if (collaborationPlan?.steps && collaborationPlan.steps.length > 0) {
    return {
      planId: collaborationPlan.plan_id,
      status: collaborationPlan.status,
      steps: collaborationPlan.steps,
    }
  }

  if (Array.isArray(data.steps) && data.steps.length > 0) {
    return {
      planId: data.plan_id as string | undefined,
      status: data.status as string | undefined,
      steps: data.steps as CollaborationStepView[],
    }
  }

  return undefined
}

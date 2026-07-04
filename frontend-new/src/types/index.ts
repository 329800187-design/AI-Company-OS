/** Shared API response types */

// ── Memory ──────────────────────────────────────────────────────────────────

export interface Memory {
  key: string
  content: string
  source: string
  tags: string[]
  importance: number
  created_at: string
  accessed_at: string
  access_count: number
}

export interface MemoryForm {
  key: string
  content: string
  source: string
  tags: string
  importance: number
}

// ── Mission / Boss ──────────────────────────────────────────────────────────

export interface MissionModule {
  module_id: string
  title: string
  status: string
  prompt?: string
  result: string
  confidence: number
  warnings: string[]
  error: string
  used_tools: string[]
  used_agents?: string[]
  mode?: string
  structured_output?: Record<string, unknown>
  started_at?: string
  finished_at?: string
  duration_ms?: number
  next_actions?: string[]
}

export interface MissionMetrics {
  total_modules: number
  succeeded_modules: number
  failed_modules: number
  skipped_modules: number
  duration_ms: number
  warning_count: number
  next_action_count: number
  completion_rate: number
}

export interface MissionDetail {
  mission_id: string
  goal: string
  status: string
  created_at: string
  updated_at: string
  modules: MissionModule[]
  metrics: MissionMetrics
}

export interface MissionSummary {
  mission_id: string
  goal: string
  status: string
  created_at: string
  updated_at: string
}

// ── Template ────────────────────────────────────────────────────────────────

export interface Template {
  id: string
  name: string
  description: string
  default_goal: string
  default_modules: string[]
  suggested_inputs: string[]
  expected_outputs: string[]
}

// ── Config / Provider ───────────────────────────────────────────────────────

export interface ProviderInfo {
  id: string
  name: string
  description: string
  configured: boolean
}

export interface SystemConfig {
  server: Record<string, unknown>
  providers: ProviderInfo[]
  current_provider: string
  agents: Record<string, unknown>
  logging: Record<string, unknown>
}

// ── Brain ───────────────────────────────────────────────────────────────────

export interface BrainItem {
  brain_id: string
  name: string
  provider: string
  description: string
  icon: string
  enabled: boolean
}

// ── Capability ──────────────────────────────────────────────────────────────

export interface Capability {
  tool: string
  available: boolean
  installed: boolean
  running: boolean
  version: string
  models: unknown[]
  error: string
  fix_hint: string
}

export type Capabilities = Record<string, Capability>

// ── System Health ───────────────────────────────────────────────────────────

export interface SystemHealth {
  backend: boolean
  database: boolean
  apiConfigured: boolean
  currentProvider: string
  browserApproved: boolean
  hermesAvailable: boolean
  version: string
}

// ── Usage ───────────────────────────────────────────────────────────────────

export interface UsageStats {
  hours: number
  calls: number
  tokens: number
  cost_yuan: number
}

export interface UsageTotal {
  total_calls: number
  total_tokens: number
  total_cost_yuan: number
}

export interface UsageRecord {
  model: string
  tokens: number
  cost_yuan: number
  timestamp: string
  duration_ms: number
}

// ── Skills ──────────────────────────────────────────────────────────────────

export interface Skill {
  name: string
  title: string
  description: string
  category: string
  capabilities: string[]
  triggers: string[]
}

// ── Workflow ────────────────────────────────────────────────────────────────

export interface WorkflowStep {
  name: string
  agent: string
  task_type: string
  depends_on: string[]
}

export interface Workflow {
  name: string
  title: string
  description: string
  version: string
  triggers: string[]
  steps: WorkflowStep[]
}

// ── Pipeline ────────────────────────────────────────────────────────────────

export interface PipelineResult {
  ok: boolean
  mode: string
  task_id: string
  task_type: string
  used_tools: string[]
  tool_trace: Array<{ tool: string; action: string; status: string; summary: string }>
  used_web_search: boolean
  search_mode: string
  sources: Array<{ title: string; url: string; summary: string }>
  analysis: string
  final_answer: string
  deliverables: Record<string, unknown>
  qa: { passed: boolean; score: number; problems: string[]; suggestions: string[] }
  confidence: number
  warnings: string[]
  error: string
}

// ── Collaboration / Governance ───────────────────────────────────────────────

export interface CollaborationStepView {
  step_id?: string
  id?: string
  name?: string
  status?: string
  assigned_agent_id?: string | null
  required_capability?: string
  matched_capability?: string | null
  routing_reason?: string | null
  candidate_agent_ids?: string[]
  depends_on?: string[]
  review_required?: boolean
  expected_output?: string | null
  task_type?: string
  error?: string | null
  result?: {
    ok?: boolean
    agent_id?: string
    output?: Record<string, unknown>
    artifacts?: string[]
    error?: string | null
  }
}

export interface CollaborationPlanView {
  plan_id?: string
  goal?: string
  status?: string
  steps?: CollaborationStepView[]
}

// ── Chat ────────────────────────────────────────────────────────────────────

export interface CollaborationTimelineEvent {
  event_id?: string
  event_type?: string
  timestamp?: string
  actor?: string
  summary?: string
  payload?: Record<string, unknown>
}

export interface CollaborationArtifactView {
  artifact_id?: string
  step_id?: string
  step_name?: string
  agent_id?: string
  path: string
  kind?: string
}

export interface CollaborationRunDetailView {
  plan?: CollaborationPlanView
  step_records?: Array<Record<string, unknown>>
  timeline?: CollaborationTimelineEvent[]
  artifacts?: CollaborationArtifactView[]
}

export interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  isError?: boolean
  timestamp?: number
}

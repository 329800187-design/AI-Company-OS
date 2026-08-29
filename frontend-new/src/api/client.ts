import type { CollaborationRunDetailView, MissionMetrics } from "@/types"

const API_BASE = ""

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

class ApiClient {
  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {}, signal } = options

    const config: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      signal,
    }

    if (body) {
      config.body = JSON.stringify(body)
    }

    const response = await fetch(`${API_BASE}${endpoint}`, config)

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Chat API
  async chat(message: string, history: Array<{ role: string; content: string }> = []) {
    return this.request<{ reply: string; model: string; provider: string }>("/commander/chat/send", {
      method: "POST",
      body: { message, history },
    })
  }

  // Commander APIs
  async runCommander(goal: string) {
    return this.request<{ session_id: string; status: string; message?: string }>("/commander/run", {
      method: "POST",
      body: { 目标: goal },
    })
  }

  async getCommanderStatus(sessionId: string) {
    return this.request<{
      session_id: string
      status: string
      steps: Array<{
        name: string
        status: string
        result?: string
      }>
      final_result?: string
    }>(`/commander/sessions/${sessionId}`)
  }

  // Agent APIs
  async runAgent(agentName: string, task: string, allowBrowserAutomation = false) {
    const body: Record<string, unknown> = { goal: task }
    if (agentName === "marketing") {
      body.prompt = task
      body.platform = "xiaohongshu"
    } else if (agentName === "codex") {
      body.code = task
    } else if (agentName === "image") {
      body.prompt = task
    } else if (agentName === "video") {
      body.prompt = task
    }
    if (agentName === "openclaw") {
      body.allow_browser_automation = allowBrowserAutomation
    }

    return this.request<{ status: string; data?: Record<string, unknown> }>(`/agents/${agentName}/run`, {
      method: "POST",
      body,
    })
  }

  // Config APIs
  async getConfig() {
    return this.request<{
      server: Record<string, unknown>
      providers: Array<Record<string, unknown>>
      current_provider: string
      agents: Record<string, unknown>
      logging: Record<string, unknown>
    }>("/config/status")
  }

  async getProviders() {
    return this.request<{
      providers: Array<Record<string, unknown>>
      current: string
    }>("/config/providers")
  }

  async getProvidersHealth() {
    return this.request<{
      search: {
        name: string
        is_mock: boolean
        has_api_key: boolean
        env_provider: string
        available: boolean
        providers: Array<{ name: string; has_key: boolean; env_var: string }>
      }
      image: {
        name: string
        is_mock: boolean
        has_api_key: boolean
        env_provider: string
        available: boolean
        providers: Array<{ name: string; has_key: boolean; env_var: string }>
      }
    }>("/config/providers/health")
  }

  async saveConfig(config: Record<string, unknown>) {
    return this.request<{ success: boolean; message: string }>("/config/save", {
      method: "POST",
      body: config,
    })
  }

  async testConnection(provider: string) {
    return this.request<{ status: "ok" | "error"; message: string }>("/config/test", {
      method: "POST",
      body: { provider },
    })
  }

  // Brain APIs
  async getBrains() {
    return this.request<{
      brains: Array<{
        brain_id: string
        name: string
        provider: string
        description: string
        icon: string
        enabled: boolean
      }>
      current: {
        brain_id: string
        name: string
      }
    }>("/brain/list")
  }

  async switchBrain(brainId: string) {
    return this.request<{ success: boolean }>("/brain/switch", {
      method: "POST",
      body: { brain_id: brainId },
    })
  }

  // Health check
  async healthCheck() {
    return this.request<{ status: string; version: string }>("/health")
  }

  // Local browser verification
  async runBrowserVerification() {
    return this.request<BrowserVerificationRun>("/browser-verification/runs", { method: "POST" })
  }

  async getBrowserVerificationRuns() {
    return this.request<{ runs: BrowserVerificationRun[] }>("/browser-verification/runs")
  }

  // Pipeline API - 统一任务执行
  async executePipeline(message: string, context?: Record<string, unknown>) {
    return this.request<{
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
    }>("/pipeline/execute", {
      method: "POST",
      body: { message, context: context || {} },
    })
  }

  // Boss Command Center APIs
  async getTemplates() {
    return this.request<{
      templates: Array<{
        id: string
        name: string
        description: string
        default_goal: string
        default_modules: string[]
        suggested_inputs: string[]
        expected_outputs: string[]
        // Phase 6.20: 通用业务流程模板协议
        protocol_version?: string
        template_type?: string
        domain_lock?: boolean
        context_schema?: Record<string, unknown>
        review_checklist?: string[]
        input_fields?: Array<{
          name: string
          label: string
          type: "text" | "select"
          required: boolean
          placeholder?: string
          options?: string[]
          default?: string
        }>
        output_schema?: { sections: Array<{ id: string; title: string; module: string }> }
        expected_sections?: string[]
        suggested_review_checklist?: string[]
        prompt_overrides?: Record<string, string>
        aliased_to?: string
      }>
      total: number
    }>("/boss/templates")
  }

  async createMissionFromTemplate(templateId: string, overrides?: {
    goal?: string
    enabledModules?: string[]
    inputs?: Record<string, string>
    autoRun?: boolean
    allowBrowserAutomation?: boolean
  }) {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      metrics: {
        total_modules: number
        succeeded_modules: number
        failed_modules: number
        skipped_modules: number
        duration_ms: number
        warning_count: number
        next_action_count: number
        completion_rate: number
      }
      modules: Array<{
        module_id: string
        title: string
        status: string
        result: string
        confidence: number
        warnings: string[]
        error: string
        used_tools: string[]
        mode?: string
      }>
    }>("/boss/missions/from-template", {
      method: "POST",
      body: {
        template_id: templateId,
        goal: overrides?.goal,
        enabled_modules: overrides?.enabledModules,
        inputs: overrides?.inputs,
        auto_run: overrides?.autoRun,
        allow_browser_automation: overrides?.allowBrowserAutomation ?? false,
      },
    })
  }

  async createMission(goal: string, autoRun = false, enabledModules?: string[], allowBrowserAutomation = false) {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      modules: Array<{
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
      }>
      metrics?: {
        total_modules: number
        succeeded_modules: number
        failed_modules: number
        skipped_modules: number
        duration_ms: number
        warning_count: number
        next_action_count: number
        completion_rate: number
      }
    }>("/boss/missions", {
      method: "POST",
      body: { goal, auto_run: autoRun, enabled_modules: enabledModules, allow_browser_automation: allowBrowserAutomation },
    })
  }

  async listMissions(limit = 20, offset = 0) {
    return this.request<{
      missions: Array<{
        mission_id: string
        goal: string
        status: string
        created_at: string
        updated_at: string
      }>
      total: number
    }>(`/boss/missions?limit=${limit}&offset=${offset}`)
  }

  async getMission(missionId: string) {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      modules: Array<{
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
      }>
      metrics?: {
        total_modules: number
        succeeded_modules: number
        failed_modules: number
        skipped_modules: number
        duration_ms: number
        warning_count: number
        next_action_count: number
        completion_rate: number
      }
    }>(`/boss/missions/${missionId}`)
  }

  async runMission(missionId: string, allowBrowserAutomation = false) {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      modules: Array<{
        module_id: string
        title: string
        status: string
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
      }>
      metrics?: {
        total_modules: number
        succeeded_modules: number
        failed_modules: number
        skipped_modules: number
        duration_ms: number
        warning_count: number
        next_action_count: number
        completion_rate: number
      }
    }>(`/boss/missions/${missionId}/run`, {
      method: "POST",
      body: { allow_browser_automation: allowBrowserAutomation },
    })
  }

  async runMissionModule(missionId: string, moduleId: string, allowBrowserAutomation = false, signal?: AbortSignal) {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      modules: Array<{
        module_id: string
        title: string
        status: string
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
      }>
      metrics?: {
        total_modules: number
        succeeded_modules: number
        failed_modules: number
        skipped_modules: number
        duration_ms: number
        warning_count: number
        next_action_count: number
        completion_rate: number
      }
    }>(`/boss/missions/${missionId}/modules/${moduleId}/run`, {
      method: "POST",
      body: { allow_browser_automation: allowBrowserAutomation },
      signal,
    })
  }

  async acceptMission(missionId: string, comment = "") {
    return this.request<{
      mission_id: string
      goal: string
      status: string
      created_at: string
      updated_at: string
      modules: Array<{
        module_id: string
        title: string
        status: string
        result: string
        confidence: number
        warnings: string[]
        error: string
        used_tools: string[]
        used_agents?: string[]
        mode?: string
        structured_output?: Record<string, unknown>
        next_actions?: string[]
      }>
      metrics?: MissionMetrics
    }>(`/boss/missions/${missionId}/accept`, {
      method: "POST",
      body: { comment },
    })
  }

  async getBossOperatingOverview() {
    return this.request<{
      mission_count: number
      accepted_mission_count: number
      status_counts: Record<string, number>
      outcome_count: number
      outcome_counts: Record<string, number>
      outcome_feedback_rate: number
      action_count: number
      action_counts: Record<string, number>
      executed_action_count: number
      kpi_observation_count: number
      operating_memory_governance: {
        active_count?: number
        retired_count?: number
        expiring_count?: number
        available?: boolean
      }
      operating_cycle_count: number
      operating_cycle_counts: Record<string, number>
      reviewed_cycle_count: number
    }>("/boss/overview")
  }

  async getMissionActionConnectors() {
    return this.request<{
      connectors: Array<{
        connector_id: string
        display_name: string
        mode: "simulation" | "external"
        configured: boolean
        requires_human_approval: boolean
        requires_preflight: boolean
        external_side_effects: boolean
        note?: string
      }>
    }>("/boss/action-connectors")
  }

  async createMissionAction(
    missionId: string,
    payload: { action_type: string; summary?: string; payload?: Record<string, unknown>; connector_id?: string },
  ) {
    return this.request<{ mission_id: string; action: Record<string, unknown> }>(
      `/boss/missions/${missionId}/actions`, { method: "POST", body: payload },
    )
  }

  async approveMissionAction(actionId: string, approvalNote = "") {
    return this.request<{ action: Record<string, unknown> }>(`/boss/actions/${actionId}/approve`, {
      method: "POST", body: { approval_note: approvalNote },
    })
  }

  async cancelMissionAction(actionId: string, reason: string) {
    return this.request<{ action: Record<string, unknown> }>(`/boss/actions/${actionId}/cancel`, {
      method: "POST", body: { reason },
    })
  }

  async preflightMissionAction(actionId: string) {
    return this.request<{ action: Record<string, unknown> }>(`/boss/actions/${actionId}/preflight`, {
      method: "POST",
    })
  }

  async executeMissionAction(actionId: string) {
    return this.request<{ action: Record<string, unknown> }>(`/boss/actions/${actionId}/execute`, {
      method: "POST",
    })
  }

  async recordMissionKpi(
    missionId: string,
    payload: { name: string; value: number; unit?: string; direction?: "increased" | "decreased" | "unchanged" | "unknown"; note?: string; action_id?: string },
  ) {
    return this.request<{ mission_id: string; observation: Record<string, unknown> }>(
      `/boss/missions/${missionId}/kpis`, { method: "POST", body: payload },
    )
  }

  async listOperatingCycles(limit = 20) {
    return this.request<{ cycles: Array<Record<string, unknown>>; total: number }>(
      `/boss/operating-cycles?limit=${limit}`,
    )
  }

  async createOperatingCycle(payload: {
    name: string; objective: string; period_start?: string; period_end?: string; target_metrics?: Record<string, unknown>
  }) {
    return this.request<Record<string, unknown>>("/boss/operating-cycles", { method: "POST", body: payload })
  }

  async attachOperatingCycleObservation(cycleId: string, observationId: number) {
    return this.request<Record<string, unknown>>(`/boss/operating-cycles/${cycleId}/observations`, {
      method: "POST", body: { observation_id: observationId },
    })
  }

  async reviewOperatingCycle(cycleId: string, payload: { conclusion: string; decision: "continue" | "adjust" | "pause" | "complete"; next_actions?: string[] }) {
    return this.request<Record<string, unknown>>(`/boss/operating-cycles/${cycleId}/review`, {
      method: "POST", body: payload,
    })
  }

  async recordMissionOutcome(
    missionId: string,
    outcomeStatus: "improved" | "unchanged" | "worse" | "inconclusive",
    note = "",
    metrics: Record<string, number> = {},
  ) {
    return this.request<{
      mission_id: string
      outcome: {
        mission_id: string
        outcome_status: "improved" | "unchanged" | "worse" | "inconclusive"
        metrics: Record<string, number>
        note: string
        observed_at: string
      }
    }>(`/boss/missions/${missionId}/outcome`, {
      method: "POST",
      body: { outcome_status: outcomeStatus, metrics, note },
    })
  }

  // 清理超时 running 模块
  async cleanupStaleMissions(timeoutMinutes = 30) {
    return this.request<{
      cleaned_modules: number
      affected_missions: string[]
      details: Array<{
        mission_id: string
        module_id: string
        old_status: string
        new_status: string
        has_result: boolean
      }>
    }>("/boss/missions/cleanup-stale", {
      method: "POST",
      body: { timeout_minutes: timeoutMinutes },
    })
  }

  // Boss Lite API
  async bossLiteExecute(goal: string, agents?: string[], saveToDelivery = true) {
    return this.request<{
      ok: boolean
      task_id: string
      goal: string
      plan: Array<{
        step: number
        agent_id: string
        task_type: string
        title: string
        prompt: string
        purpose: string
        status: string
      }>
      results: Array<{
        agent_id: string
        title: string
        ok: boolean
        summary: string
        structured_output: Record<string, unknown>
        warnings: string[]
        errors: string[]
        error?: string
      }>
      summary: {
        text: string
        succeeded: number
        failed: number
        total: number
      }
      structured_output: Record<string, unknown>
      delivery_task_id?: string
    }>("/boss/lite/execute", {
      method: "POST",
      body: { goal, agents, save_to_delivery: saveToDelivery },
    })
  }

  async getMissionEvents(missionId: string) {
    return this.request<{
      mission_id: string
      events: Array<{
        id: number
        mission_id: string
        type: string
        module_id: string | null
        message: string
        payload: Record<string, unknown>
        created_at: string
      }>
      total: number
    }>(`/boss/missions/${missionId}/events`)
  }

  // Memory APIs
  async searchMemory(query: string, limit = 20) {
    return this.request<{
      memories: Array<{
        key: string
        content: string
        source: string
        tags: string[]
        importance: number
        created_at: string
        accessed_at: string
        access_count: number
      }>
      count: number
    }>(`/memory/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  }

  async recentMemory(limit = 20) {
    return this.request<{
      memories: Array<{
        key: string
        content: string
        source: string
        tags: string[]
        importance: number
        created_at: string
        accessed_at: string
        access_count: number
      }>
      count: number
    }>(`/memory/recent?limit=${limit}`)
  }

  async rememberMemory(key: string, content: string, source = "user", tags: string[] = [], importance = 0.5) {
    return this.request<{ status: string }>("/memory/remember", {
      method: "POST",
      body: { key, content, source, tags, importance },
    })
  }

  async getMemoryContext(goal: string) {
    return this.request<{ context: string; goal: string }>(
      `/memory/context?goal=${encodeURIComponent(goal)}`
    )
  }

  async clearMemory() {
    return this.request<{ status: string; message: string }>("/memory/clear", {
      method: "DELETE",
    })
  }

  async deleteMemory(key: string) {
    return this.request<{ status: string; message: string }>(`/memory/${encodeURIComponent(key)}`, {
      method: "DELETE",
    })
  }

  async updateMemory(key: string, updates: {
    content?: string
    source?: string
    tags?: string[]
    importance?: number
  }) {
    return this.request<{ status: string }>(`/memory/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: updates,
    })
  }

  // Report / Export APIs
  async exportSession(sessionId: string, format: "html" | "csv" | "json" = "html") {
    const response = await fetch(`${API_BASE}/export/session/${sessionId}?format=${format}`)
    if (!response.ok) {
      throw new Error(`Export failed: HTTP ${response.status}`)
    }
    const blob = await response.blob()
    const ext = format === "html" ? "html" : format === "csv" ? "csv" : "json"
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `report-${sessionId.slice(0, 8)}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  async exportMission(missionId: string, format: "json" | "markdown" = "json") {
    const response = await fetch(`${API_BASE}/boss/missions/${missionId}/export?format=${format}`)
    if (!response.ok) {
      throw new Error(`Export failed: HTTP ${response.status}`)
    }
    const blob = await response.blob()
    const ext = format === "markdown" ? "md" : "json"
    const filename = `boss-mission-${missionId}.${ext}`
    const url = URL.createObjectURL(blob)
    // 触发浏览器下载
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // ── System Metrics ──────────────────────────────────────────────────────────

  async getSystemMetrics() {
    return this.request<{
      usage: {
        "24h_calls": number
        "24h_tokens": number
        "all_calls": number
        "all_tokens": number
        "cost_yuan": number
      }
      agents: Record<string, string>
      cache: Record<string, unknown>
      payment: { active: boolean; tx_count: number }
      db: Record<string, number>
    }>("/system/metrics")
  }

  async getSystemHealth() {
    return this.request<{
      status: string
      agents: Record<string, { status: string; error?: string }>
      timestamp: string
    }>("/system/health")
  }

  // ── Usage ───────────────────────────────────────────────────────────────────

  async getUsageStats(hours = 24) {
    return this.request<{
      hours: number
      calls: number
      tokens: number
      cost_yuan: number
    }>(`/usage/stats?hours=${hours}`)
  }

  async getUsageTotal() {
    return this.request<{
      total_calls: number
      total_tokens: number
      total_cost_yuan: number
    }>("/usage/total")
  }

  async getUsageRecent(limit = 50) {
    return this.request<{
      calls: Array<{
        model: string
        tokens: number
        cost_yuan: number
        timestamp: string
        duration_ms: number
      }>
      count: number
    }>(`/usage/recent?limit=${limit}`)
  }

  // ── Skills ──────────────────────────────────────────────────────────────────

  async listSkills() {
    return this.request<{
      skills: Array<{
        name: string
        title: string
        description: string
        category: string
        capabilities: string[]
        triggers: string[]
      }>
      count: number
    }>("/skills/list")
  }

  async matchSkills(goal: string) {
    return this.request<{
      matched: Array<{
        name: string
        title: string
        score: number
      }>
      goal: string
    }>(`/skills/match?goal=${encodeURIComponent(goal)}`)
  }

  async createSkill(skill: {
    name: string
    title: string
    description: string
    category: string
    capabilities: string[]
    triggers: string[]
    body: string
  }) {
    return this.request<{ status: string; skill: Record<string, unknown> }>("/skills/create", {
      method: "POST",
      body: skill,
    })
  }

  // ── Workflows (DAG) ────────────────────────────────────────────────────────

  async listWorkflows() {
    return this.request<{
      workflows: Array<{ name: string; count: number }>
      total: number
    }>("/workflows/dag/list")
  }

  async getWorkflow(name: string) {
    return this.request<{
      name: string
      title: string
      description: string
      version: string
      triggers: string[]
      steps: Array<{
        name: string
        agent: string
        task_type: string
        depends_on: string[]
      }>
    }>(`/workflows/dag/${encodeURIComponent(name)}`)
  }

  async runWorkflow(name: string, variables: Record<string, string> = {}) {
    return this.request<{
      status: string
      workflow: string
      results: Record<string, unknown>
    }>("/workflows/dag/run", {
      method: "POST",
      body: { workflow: name, inputs: variables },
    })
  }

  // ── Agent Execution APIs ────────────────────────────────────────────────

  async executeAgent(agentId: string, task: {
    goal: string
    task_type: string
    context?: Record<string, unknown>
    input?: Record<string, unknown>
  }) {
    return this.request<{
      ok: boolean
      mode?: string
      agent_id: string
      task_type?: string
      summary?: string
      structured_output?: Record<string, unknown>
      output: Record<string, unknown>
      artifacts: string[]
      warnings?: string[]
      errors?: string[]
      error?: string
      next_actions?: string[]
      risk_decision?: {
        risk_level?: string
        recommended_action?: string
      }
      timeline_events?: Array<Record<string, unknown>>
      metadata?: Record<string, unknown>
    }>(`/agents/${agentId}/execute`, {
      method: "POST",
      body: {
        task_id: "",
        goal: task.goal,
        task_type: task.task_type,
        context: task.context || {},
        input: task.input || {},
      },
    })
  }

  // ── Governance APIs ────────────────────────────────────────────────────────

  async governanceRun(goal: string, platform: string = "", execute: boolean = false) {
    return this.request<{
      run_id: string
      status: string
      artifact_path?: string
      json_path?: string
      task_id?: string
      mode?: string
      summary?: string
      plan?: Record<string, unknown>
      classification?: Record<string, unknown>
      result?: {
        ok: boolean
        checks?: Record<string, unknown>
        spec?: Record<string, unknown>
        [key: string]: unknown
      }
    }>("/governance/run", {
      method: "POST",
      body: { goal, platform, execute },
    })
  }

  async governanceArtifact(runId: string) {
    return this.request<{
      run_id: string
      artifact_path: string
      content: string
    }>(`/governance/runs/${runId}/artifact`)
  }

  // ── MiniDelivery: 保存 Agent 结果 ──────────────────────
  async saveAgentResultToDelivery(payload: {
    goal: string
    agent_id: string
    agent_result: Record<string, unknown>
    artifact_type?: string
    title?: string
    source_page?: string
  }) {
    return this.request<{
      task_id: string
      artifact_path: string
      result_path: string
      agent_id: string
      artifact_type: string
    }>("/minidelivery/save-from-agent", {
      method: "POST",
      body: payload,
    })
  }

  async governanceRunDetail(runId: string) {
    return this.request<{
      run_id: string
      goal: string
      capability_id: string
      status: string
      created_at: string
      updated_at: string
      artifact_path?: string
      result_ref?: string
      failure_reason?: string
      collaboration_plan?: {
        plan_id: string
        goal: string
        status: string
        steps: Array<{
          id: string
          name: string
          task_type: string
          required_capability: string
          status: string
          assigned_agent_id?: string
          result?: {
            ok: boolean
            agent_id?: string
            output?: Record<string, unknown>
            error?: string
          }
        }>
      }
    }>(`/governance/runs/${runId}`)
  }

  async listGovernanceRuns(limit = 20, offset = 0) {
    return this.request<{
      total: number
      records: Array<{
        run_id: string
        goal: string
        capability_id: string
        status: string
        created_at: string
        updated_at: string
        artifact_path?: string
        result_ref?: string
        failure_reason?: string
        collaboration_plan?: {
          plan_id: string
          goal: string
          status: string
          steps: Array<{
            id: string
            name: string
            task_type: string
            required_capability: string
            status: string
            assigned_agent_id?: string
            result?: {
              ok: boolean
              agent_id?: string
              output?: Record<string, unknown>
              error?: string
            }
          }>
        }
      }>
    }>(`/governance/runs?limit=${limit}&offset=${offset}`)
  }

  // ── Collaboration APIs ──────────────────────────────────────────────────

  async collaborationPlanGet(planId: string) {
    return this.request<CollaborationRunDetailView>(`/collaboration/runs/${planId}`)
  }

  async collaborationRunResume(runId: string) {
    return this.request<Record<string, unknown>>(`/collaboration/runs/${runId}/resume`, {
      method: "POST",
    })
  }

  async collaborationStepApprove(planId: string, stepId: string, comment?: string) {
    return this.request<Record<string, unknown>>(`/collaboration/runs/${planId}/approve`, {
      method: "POST",
      body: { step_id: stepId, ...(comment !== undefined ? { comment } : {}) },
    })
  }

  async collaborationStepReject(planId: string, stepId: string, comment?: string) {
    return this.request<Record<string, unknown>>(`/collaboration/runs/${planId}/reject`, {
      method: "POST",
      body: { step_id: stepId, ...(comment !== undefined ? { comment } : {}) },
    })
  }

  async collaborationStepRetry(planId: string, stepId: string) {
    return this.request<Record<string, unknown>>(`/collaboration/runs/${planId}/retry-step`, {
      method: "POST",
      body: { step_id: stepId },
    })
  }

  // ── Agent Discovery & Enable/Disable ──────────────────────────────────────

  async getDiscoveredAgents() {
    return this.request<{
      agents: Array<{
        id: string
        name: string
        kind: string
        executable?: string
        endpoint?: string
        status: string
        capabilities: string[]
        task_types: string[]
        risk_level: string
        requires_api_key: boolean
        requires_gpu: boolean
        requires_confirmation: boolean
        enabled: boolean
        runnable: boolean
        source: string
        timeout_seconds: number
        input_schema?: Record<string, unknown> | null
        output_schema?: Record<string, unknown> | null
        tools: string[]
        supports_files: boolean
        supports_web_search: boolean
        supports_code_execution: boolean
        supports_image_generation: boolean
        supports_browser: boolean
        priority: number
        cost_level: string
        latency_level: string
        reliability_score: number
        health: Record<string, unknown>
        last_error?: string
        llm_binding?: {
          provider?: string
          model?: string
          configured?: boolean
          credential_source?: string
          ready?: boolean
          configured_providers?: string[]
        }
        requires_llm?: boolean
      }>
      total: number
      enabled_count: number
      scan_scope?: {
        project_root?: string
        project_agent_dirs?: string[]
        path_commands?: string[]
        local_services?: string[]
        mcp_configs?: string[]
        filesystem_scan?: string
      }
      planning?: {
        available_enabled: Array<{ id: string; name: string; capabilities: string[]; task_types: string[]; runnable?: boolean }>
        message: string
      }
      llm_providers?: Array<Record<string, unknown> & { id: string; name: string; status: string; model?: string; note?: string }>
      local_services?: Array<Record<string, unknown> & { id: string; name: string; status: string }>
      browsers?: Array<Record<string, unknown> & { id: string; name: string; status: string }>
      tools?: Array<Record<string, unknown> & { id: string; name: string; status: string }>
      machine_scan?: { machine_id?: string; scanned_at?: string; platform?: string; scope?: string }
    }>("/agent-console/discovered")
  }

  async enableAgent(agentId: string) {
    return this.request<{ ok: boolean; agent_id: string; enabled: boolean; message: string }>(
      `/agent-console/${agentId}/enable`,
      { method: "POST" }
    )
  }

  async disableAgent(agentId: string) {
    return this.request<{ ok: boolean; agent_id: string; enabled: boolean; message: string }>(
      `/agent-console/${agentId}/disable`,
      { method: "POST" }
    )
  }

  // ── Universal Search ────────────────────────────────────────────────────────

  async universalSearch(query: string, scope = "all", limit = 20) {
    return this.request<{
      query: string
      scope: string
      total: number
      hits: {
        memories: Array<{ key: string; content: string; source: string }>
        skills: Array<{ name: string; title: string; score: number }>
        sessions: Array<{ goal: string; status: string; created_at: string }>
        workflows: Array<{ name: string; description: string }>
      }
    }>(`/search?q=${encodeURIComponent(query)}&scope=${scope}&limit=${limit}`)
  }

  // ── MiniDelivery 交付物列表（Phase 2A）───────────────────────────────────

  async listMiniDeliveryTasks(filters?: {
    q?: string
    agent_id?: string
    artifact_type?: string
    source_page?: string
    limit?: number
    offset?: number
  }) {
    const params = new URLSearchParams()
    if (filters?.q) params.set("q", filters.q)
    if (filters?.agent_id) params.set("agent_id", filters.agent_id)
    if (filters?.artifact_type) params.set("artifact_type", filters.artifact_type)
    if (filters?.source_page) params.set("source_page", filters.source_page)
    if (filters?.limit !== undefined) params.set("limit", String(filters.limit))
    if (filters?.offset !== undefined) params.set("offset", String(filters.offset))
    const qs = params.toString()
    return this.request<{
      tasks: Array<{
        task_id: string
        goal: string
        agent_id: string
        artifact_type: string
        source_page: string
        created_at: string
        artifact_path: string
        result_path: string
      }>
      warnings: string[]
      total: number
      limit: number
      offset: number
      has_more: boolean
    }>(`/minidelivery/tasks${qs ? "?" + qs : ""}`)
  }

  async getMiniDeliveryTaskDetail(taskId: string) {
    return this.request<{
      task_id: string
      goal: string
      agent_id: string
      artifact_type: string
      source_page: string
      created_at: string
      ok: boolean
      mode: string
      summary: string
      artifact_path: string
      raw_agent_result_path: string
      has_raw_agent_result: boolean
      agent_result_summary?: string
    }>(`/minidelivery/tasks/${taskId}`)
  }

  async getMiniDeliveryArtifact(taskId: string) {
    const response = await fetch(`${API_BASE}/minidelivery/tasks/${taskId}/artifact`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return response.text()
  }

  // ── MiniDelivery 下载 URL（Phase 2B）───────────────────────────────────

  getMiniDeliveryDownloadUrl(taskId: string) {
    return `${API_BASE}/minidelivery/tasks/${taskId}/download`
  }

  // ── MiniDelivery PDF 导出（Phase 5.1）───────────────────────────────────

  getMiniDeliveryPdfUrl(taskId: string) {
    return `${API_BASE}/minidelivery/tasks/${taskId}/pdf`
  }

  // ── MiniDelivery 任务对比（Phase 5.2）─────────────────────────────────

  async compareMiniDeliveryTasks(taskIds: [string, string]) {
    return this.request<{
      ok: boolean
      tasks: Array<{
        task_id: string
        goal: string | null
        created_at: string
        artifact_type: string | null
        source_page: string | null
        agent_id: string | null
        ok: boolean | null
        mode: string | null
        summary: string | null
        succeeded: number | null
        failed: number | null
        total: number | null
        total_duration_ms: number | null
        handoff_enabled: boolean | null
        execution_mode: string | null
      }>
      diff: {
        goal_changed: boolean
        goal_diff?: { a: string; b: string }
        succeeded_diff: number | null
        failed_diff: number | null
        total_diff: number | null
        total_duration_ms_diff: number | null
        handoff_changed: boolean
        execution_mode_changed: boolean
        artifact_type_changed: boolean
        summary_changed: boolean
      }
    }>("/minidelivery/tasks/compare", {
      method: "POST",
      body: { task_ids: taskIds },
    })
  }

  // ── Graph Template APIs ──────────────────────────────────────────────

  async listBossGraphTemplates() {
    return this.request<{
      ok: boolean
      templates: Array<{
        template_id: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
        created_at: string
        updated_at: string
      }>
      total: number
    }>("/boss/graph/templates")
  }

  async getBossGraphTemplate(templateId: string) {
    return this.request<{
      ok: boolean
      template: {
        template_id: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
        created_at: string
        updated_at: string
      }
    }>(`/boss/graph/templates/${templateId}`)
  }

  async createBossGraphTemplate(payload: {
    name: string
    description?: string
    goal_hint?: string
    source_template_id?: string
    nodes: Array<{
      id: string
      agent_id: string
      task_type?: string
      title?: string
      prompt?: string
    }>
    edges: Array<{
      from_node: string
      to_node: string
      handoff_type?: string
    }>
  }) {
    return this.request<{
      ok: boolean
      template: {
        template_id: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
        created_at: string
        updated_at: string
      }
    }>("/boss/graph/templates", {
      method: "POST",
      body: payload,
    })
  }

  async deleteBossGraphTemplate(templateId: string) {
    return this.request<{
      ok: boolean
      deleted: boolean
      template_id: string
    }>(`/boss/graph/templates/${templateId}`, {
      method: "DELETE",
    })
  }

  async updateBossGraphTemplateLayout(templateId: string, canvasLayout: Record<string, { x: number; y: number }>) {
    return this.request<{
      ok: boolean
      template: Record<string, unknown>
    }>(`/boss/graph/templates/${templateId}/layout`, {
      method: "PATCH",
      body: { canvas_layout: canvasLayout },
    })
  }

  async updateBossGraphTemplate(templateId: string, payload: {
    name: string
    description?: string
    goal_hint?: string
    nodes: Array<{
      id: string
      agent_id: string
      task_type?: string
      title?: string
      prompt?: string
    }>
    edges: Array<{
      from_node: string
      to_node: string
      handoff_type?: string
    }>
  }) {
    return this.request<{
      ok: boolean
      template: {
        template_id: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
        created_at: string
        updated_at: string
      }
    }>(`/boss/graph/templates/${templateId}`, {
      method: "PUT",
      body: payload,
    })
  }

  async executeBossGraphTemplate(templateId: string, payload: { goal: string; save_to_delivery?: boolean }) {
    return this.request<{
      ok: boolean
      task_id: string
      execution_mode: string
      goal: string
      waves: string[][]
      results: Array<{
        node_id: string
        agent_id: string
        title: string
        ok: boolean
        summary: string
        structured_output: Record<string, unknown>
        error: string | null
        duration_ms: number
        used_handoff: boolean
        handoff_sources: string[]
      }>
      summary: {
        total: number
        succeeded: number
        failed: number
        total_duration_ms: number
      }
      structured_output: Record<string, unknown>
      delivery_task_id?: string
    }>(`/boss/graph/templates/${templateId}/execute`, {
      method: "POST",
      body: payload,
    })
  }

  // ── Graph Template Version History APIs (Phase 6.6) ──────────

  async listBossGraphTemplateVersions(templateId: string) {
    return this.request<{
      ok: boolean
      versions: Array<{
        version_id: string
        template_id: string
        created_at: string
        label: string
        note: string
        pinned: boolean
        name: string
        node_count: number
        edge_count: number
      }>
      total: number
    }>(`/boss/graph/templates/${templateId}/versions`)
  }

  async getBossGraphTemplateVersion(templateId: string, versionId: string) {
    return this.request<{
      ok: boolean
      version: {
        version_id: string
        template_id: string
        created_at: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
      }
    }>(`/boss/graph/templates/${templateId}/versions/${versionId}`)
  }

  async restoreBossGraphTemplateVersion(templateId: string, versionId: string) {
    return this.request<{
      ok: boolean
      template: {
        template_id: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<{
          id: string
          agent_id: string
          task_type: string
          title: string
          prompt: string
        }>
        edges: Array<{
          from_node: string
          to_node: string
          handoff_type: string
        }>
        created_at: string
        updated_at: string
      }
      restored_from_version: string
    }>(`/boss/graph/templates/${templateId}/versions/${versionId}/restore`, {
      method: "POST",
    })
  }

  // ── Phase 6.7: Version Metadata & Compare APIs ────────────

  async updateBossGraphTemplateVersionMetadata(
    templateId: string,
    versionId: string,
    payload: { label?: string; note?: string },
  ) {
    return this.request<{
      ok: boolean
      version: {
        version_id: string
        template_id: string
        created_at: string
        label: string
        note: string
        name: string
        description: string
        goal_hint: string
        nodes: Array<Record<string, unknown>>
        edges: Array<Record<string, unknown>>
      }
    }>(`/boss/graph/templates/${templateId}/versions/${versionId}`, {
      method: "PATCH",
      body: payload,
    })
  }

  async compareBossGraphTemplateVersions(
    templateId: string,
    fromVersion: string,
    toVersion: string,
  ) {
    const params = new URLSearchParams({ from: fromVersion, to: toVersion })
    return this.request<{
      ok: boolean
      diff: {
        from_version: string
        to_version: string
        field_changes: Array<{ field: string; from: string; to: string }>
        nodes: {
          added: Array<Record<string, unknown>>
          removed: Array<Record<string, unknown>>
          modified: Array<{ id: string; from: Record<string, unknown>; to: Record<string, unknown> }>
        }
        edges: {
          added: Array<Record<string, unknown>>
          removed: Array<Record<string, unknown>>
          modified: Array<{ from_node: string; to_node: string; from: Record<string, unknown>; to: Record<string, unknown> }>
        }
      }
    }>(`/boss/graph/templates/${templateId}/versions/compare?${params.toString()}`)
  }

  // ── Phase 6.8: Audit Log & Version Pin APIs ──────────────

  async listBossGraphTemplateAudit(
    templateId: string,
    options?: { eventType?: string; limit?: number },
  ) {
    const params = new URLSearchParams()
    if (options?.eventType) params.set("event_type", options.eventType)
    if (options?.limit) params.set("limit", String(options.limit))
    const qs = params.toString()
    return this.request<{
      ok: boolean
      events: Array<{
        event_id: string
        timestamp: string
        template_id: string
        event_type: string
        summary: string
        details: Record<string, unknown>
      }>
      total: number
      deleted?: boolean
    }>(`/boss/graph/templates/${templateId}/audit${qs ? `?${qs}` : ""}`)
  }

  async pinBossGraphTemplateVersion(templateId: string, versionId: string) {
    return this.request<{
      ok: boolean
      version: Record<string, unknown>
    }>(`/boss/graph/templates/${templateId}/versions/${versionId}/pin`, {
      method: "POST",
    })
  }

  async unpinBossGraphTemplateVersion(templateId: string, versionId: string) {
    return this.request<{
      ok: boolean
      version: Record<string, unknown>
    }>(`/boss/graph/templates/${templateId}/versions/${versionId}/unpin`, {
      method: "POST",
    })
  }

  // ── Phase 6.9: Audit Retention Policy ──────────────────────

  async getBossAuditStorage() {
    return this.request<{
      ok: boolean
      storage: {
        file_count: number
        total_bytes: number
        total_size_human: string
        earliest_event: string | null
        latest_event: string | null
      }
    }>("/boss/graph/audit/storage")
  }

  async cleanupBossAuditLogs(params: { retentionDays: number; dryRun?: boolean }) {
    return this.request<{
      ok: boolean
      cleanup: {
        matched: number
        deleted: number
        skipped: number
        bytes_freed: number
        bytes_freed_human: string
        errors: Array<{ template_id: string; error: string }>
        dry_run: boolean
        retention_days: number
        would_delete: Array<{
          template_id: string
          file_path: string
          size_bytes: number
          event_count: number
          latest_event: string
        }>
      }
    }>("/boss/graph/audit/cleanup", {
      method: "POST",
      body: {
        retention_days: params.retentionDays,
        dry_run: params.dryRun ?? true,
      },
    })
  }
}

interface BrowserVerificationRun {
  run_id: string
  status: "passed" | "failed"
  started_at: string
  finished_at: string
  targets: string[]
  checks: Array<{ id: string; target: string; passed: boolean; message: string }>
  passed_count: number
  total_count: number
}

export const api = new ApiClient()

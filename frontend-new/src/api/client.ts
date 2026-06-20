const API_BASE = ""

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

class ApiClient {
  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {} } = options

    const config: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
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
  async runAgent(agentName: string, task: string) {
    const body: Record<string, string> = { goal: task }
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

  async saveConfig(config: Record<string, unknown>) {
    return this.request<{ success: boolean; message: string }>("/config/save", {
      method: "POST",
      body: config,
    })
  }

  async testConnection(provider: string) {
    return this.request<{ ok: boolean; message: string }>("/config/test", {
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
  async createMission(goal: string, autoRun = false, enabledModules?: string[]) {
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
        mode?: string
        started_at?: string
        finished_at?: string
        duration_ms?: number
        next_actions?: string[]
      }>
    }>("/boss/missions", {
      method: "POST",
      body: { goal, auto_run: autoRun, enabled_modules: enabledModules },
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
      }>
    }>(`/boss/missions/${missionId}`)
  }

  async runMission(missionId: string) {
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
        mode?: string
      }>
    }>(`/boss/missions/${missionId}/run`, { method: "POST" })
  }

  async runMissionModule(missionId: string, moduleId: string) {
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
        mode?: string
      }>
    }>(`/boss/missions/${missionId}/modules/${moduleId}/run`, { method: "POST" })
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

  async exportMission(missionId: string, format: "json" | "markdown" = "json") {
    const response = await fetch(`${API_BASE}/boss/missions/${missionId}/export?format=${format}`)
    if (!response.ok) {
      throw new Error(`Export failed: HTTP ${response.status}`)
    }
    const blob = await response.blob()
    const ext = format === "markdown" ? "md" : "json"
    const filename = `boss-mission-${missionId}.${ext}`
    // 触发浏览器下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
}

export const api = new ApiClient()

import { useEffect, useState, useCallback } from "react"
import { motion } from "framer-motion"
import {
  Cpu,
  RefreshCw,
  CheckCircle2,
  Code,
  Globe,
  Brain,
  MessageSquare,
  Settings,
  ChevronDown,
  ChevronRight,
  Shield,
  Power,
  PowerOff,
  AlertTriangle,
  Clock,
  Wrench,
} from "lucide-react"
import { api } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface DiscoveredAgent {
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
  health: Record<string, any>
  last_error?: string
}

interface DiscoveredSummary {
  agents: DiscoveredAgent[]
  total: number
  enabled_count: number
}

const kindIcons: Record<string, any> = {
  cli: Code,
  http: Globe,
  api: Brain,
  mcp: Settings,
  local: Cpu,
}

const kindLabels: Record<string, string> = {
  cli: "CLI 工具",
  http: "HTTP 服务",
  api: "API 模型",
  mcp: "MCP Server",
  local: "本地 Agent",
}

const riskColors: Record<string, { bg: string; text: string; border: string; label: string }> = {
  low: { bg: "bg-green/10", text: "text-green", border: "border-green/20", label: "低风险" },
  medium: { bg: "bg-yellow/10", text: "text-yellow", border: "border-yellow/20", label: "中风险" },
  high: { bg: "bg-red/10", text: "text-red", border: "border-red/20", label: "高风险" },
}

export default function AgentConsolePage() {
  const [summary, setSummary] = useState<DiscoveredSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [togglingAgent, setTogglingAgent] = useState<string | null>(null)
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set())

  const loadAgents = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await api.getDiscoveredAgents()
      setSummary(response)
    } catch (error) {
      console.error("Failed to load discovered agents:", error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAgents()
  }, [loadAgents])

  const handleToggle = async (agentId: string, currentEnabled: boolean) => {
    setTogglingAgent(agentId)
    try {
      if (currentEnabled) {
        await api.disableAgent(agentId)
      } else {
        await api.enableAgent(agentId)
      }
      await loadAgents()
    } catch (error) {
      console.error(`Failed to ${currentEnabled ? "disable" : "enable"} agent:`, error)
    } finally {
      setTogglingAgent(null)
    }
  }

  const toggleSchema = (agentId: string) => {
    setExpandedSchemas(prev => {
      const next = new Set(prev)
      if (next.has(agentId)) {
        next.delete(agentId)
      } else {
        next.add(agentId)
      }
      return next
    })
  }

  const byKind = (summary?.agents || []).reduce<Record<string, DiscoveredAgent[]>>((acc, agent) => {
    ;(acc[agent.kind] ||= []).push(agent)
    return acc
  }, {})

  /** 路由可用性提示 */
  const getRoutingHints = (agent: DiscoveredAgent): string[] => {
    const hints: string[] = []
    if (!agent.enabled) {
      hints.push("不会参与路由")
    }
    if (agent.capabilities.length === 0) {
      hints.push("无能力标签，无法按 capability 路由")
    }
    if (agent.risk_level === "high") {
      hints.push("建议人工确认或 sandbox")
    }
    return hints
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
            <Cpu className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Agent 控制台</h1>
            <p className="text-sm text-[#8A8A8A]">本地优先的 AI Agent 管理中心</p>
          </div>
        </div>
        <Button variant="outline" onClick={loadAgents} disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          重新扫描
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-[#0B0B0B]" />
            </div>
            <div>
              <p className="text-2xl font-bold">{summary?.total || 0}</p>
              <p className="text-sm text-[#8A8A8A]">总 Agent 数</p>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green/10 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green" />
            </div>
            <div>
              <p className="text-2xl font-bold">{summary?.enabled_count || 0}</p>
              <p className="text-sm text-[#8A8A8A]">已启用</p>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow/10 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-yellow" />
            </div>
            <div>
              <p className="text-2xl font-bold">{Object.keys(byKind).length}</p>
              <p className="text-sm text-[#8A8A8A]">Agent 类型</p>
            </div>
          </div>
        </div>
      </div>

      {/* Agent List */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-4">已发现的 Agent</h3>

        {Object.entries(byKind).map(([kind, agents]) => {
          const Icon = kindIcons[kind] || Cpu
          const label = kindLabels[kind] || kind

          return (
            <div key={kind} className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-4 h-4 text-[#8A8A8A]" />
                <h4 className="font-medium">{label}</h4>
                <Badge variant="outline">{agents.length}</Badge>
              </div>

              <div className="space-y-2">
                {agents.map(agent => {
                  const routingHints = getRoutingHints(agent)
                  const risk = riskColors[agent.risk_level] || riskColors.low

                  return (
                    <motion.div
                      key={agent.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-3 rounded-lg border ${
                        agent.enabled
                          ? agent.status === "available"
                            ? "border-green/20 bg-green/5"
                            : "border-yellow/20 bg-yellow/5"
                          : "border-[#E5E5E5] bg-[#F9F9F9]"
                      }`}
                    >
                      <div
                        className="flex items-center justify-between cursor-pointer"
                        onClick={() => setExpandedAgent(expandedAgent === agent.id ? null : agent.id)}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            agent.enabled ? "bg-green/10" : "bg-muted"
                          }`}>
                            <Icon className={`w-4 h-4 ${
                              agent.enabled ? "text-green" : "text-[#8A8A8A]"
                            }`} />
                          </div>
                          <div>
                            <h5 className="font-medium text-sm">{agent.name}</h5>
                            <p className="text-xs text-[#8A8A8A]">{agent.id}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Risk Level badge */}
                          <Badge variant="outline" className={`text-[10px] ${risk.bg} ${risk.text} ${risk.border}`}>
                            {risk.label}
                          </Badge>

                          {/* Status + Enabled badges */}
                          {agent.status === "unavailable" ? (
                            <Badge variant="secondary" className="text-xs bg-red/10 text-red border-red/20">
                              {agent.last_error || "不可用"}
                            </Badge>
                          ) : agent.enabled ? (
                            <Badge variant="success" className="text-xs">已启用</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">未启用</Badge>
                          )}

                          {agent.requires_confirmation && (
                            <Badge variant="outline" className="text-[10px] gap-0.5">
                              <Shield className="w-3 h-3" />
                              需确认
                            </Badge>
                          )}

                          {/* Enable/Disable button */}
                          <Button
                            variant={agent.enabled ? "destructive" : "outline"}
                            size="sm"
                            className="h-7 px-2 text-xs gap-1"
                            disabled={togglingAgent === agent.id}
                            onClick={(e) => {
                              e.stopPropagation()
                              handleToggle(agent.id, agent.enabled)
                            }}
                          >
                            {togglingAgent === agent.id ? (
                              <RefreshCw className="w-3 h-3 animate-spin" />
                            ) : agent.enabled ? (
                              <PowerOff className="w-3 h-3" />
                            ) : (
                              <Power className="w-3 h-3" />
                            )}
                            {agent.enabled ? "禁用" : "启用"}
                          </Button>

                          {expandedAgent === agent.id ? (
                            <ChevronDown className="w-4 h-4 text-[#8A8A8A]" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-[#8A8A8A]" />
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {expandedAgent === agent.id && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          className="mt-3 pt-3 border-t border-border space-y-3"
                        >
                          {/* Routing availability hints */}
                          {routingHints.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {routingHints.map((hint, i) => (
                                <div key={i} className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-md bg-yellow/10 text-yellow border border-yellow/20">
                                  <AlertTriangle className="w-3 h-3" />
                                  {hint}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Basic metadata */}
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-[#8A8A8A]">来源:</span>
                              <span className="ml-1">{agent.source}</span>
                            </div>
                            <div>
                              <span className="text-[#8A8A8A]">可靠性:</span>
                              <span className="ml-1">{(agent.reliability_score * 100).toFixed(0)}%</span>
                            </div>
                            <div>
                              <span className="text-[#8A8A8A]">优先级:</span>
                              <span className="ml-1">{agent.priority}</span>
                            </div>
                            <div>
                              <span className="text-[#8A8A8A]">成本:</span>
                              <span className="ml-1">{agent.cost_level}</span>
                            </div>
                            <div>
                              <span className="text-[#8A8A8A]">延迟:</span>
                              <span className="ml-1">{agent.latency_level}</span>
                            </div>
                            <div>
                              <span className="text-[#8A8A8A]">需要 API Key:</span>
                              <span className="ml-1">{agent.requires_api_key ? "是" : "否"}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Clock className="w-3 h-3 text-[#8A8A8A]" />
                              <span className="text-[#8A8A8A]">超时:</span>
                              <span className="ml-1">{agent.timeout_seconds}s</span>
                            </div>
                            {agent.endpoint && (
                              <div className="col-span-2">
                                <span className="text-[#8A8A8A]">端点:</span>
                                <span className="ml-1 font-mono text-[11px]">{agent.endpoint}</span>
                              </div>
                            )}
                          </div>

                          {/* Task types */}
                          <div>
                            <span className="text-xs text-[#8A8A8A]">支持任务:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {agent.task_types.map(t => (
                                <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
                              ))}
                            </div>
                          </div>

                          {/* Capabilities */}
                          <div>
                            <span className="text-xs text-[#8A8A8A]">能力:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {agent.capabilities.map(c => (
                                <Badge key={c} variant="outline" className="text-[10px]">{c}</Badge>
                              ))}
                            </div>
                          </div>

                          {/* Tools */}
                          {agent.tools.length > 0 && (
                            <div>
                              <span className="text-xs text-[#8A8A8A] flex items-center gap-1">
                                <Wrench className="w-3 h-3" />
                                工具:
                              </span>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {agent.tools.map(t => (
                                  <Badge key={t} variant="secondary" className="text-[10px]">{t}</Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Input/Output Schema (collapsible) */}
                          {(agent.input_schema || agent.output_schema) && (
                            <div>
                              <button
                                className="flex items-center gap-1 text-xs text-[#8A8A8A] hover:text-[#0B0B0B] transition-colors"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  toggleSchema(agent.id)
                                }}
                              >
                                {expandedSchemas.has(agent.id) ? (
                                  <ChevronDown className="w-3 h-3" />
                                ) : (
                                  <ChevronRight className="w-3 h-3" />
                                )}
                                Schema 定义
                              </button>
                              {expandedSchemas.has(agent.id) && (
                                <div className="mt-2 space-y-2">
                                  {agent.input_schema && (
                                    <div>
                                      <span className="text-[10px] text-[#8A8A8A]">input_schema:</span>
                                      <pre className="mt-1 p-2 rounded bg-muted text-[10px] font-mono overflow-x-auto">
                                        {JSON.stringify(agent.input_schema, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                  {agent.output_schema && (
                                    <div>
                                      <span className="text-[10px] text-[#8A8A8A]">output_schema:</span>
                                      <pre className="mt-1 p-2 rounded bg-muted text-[10px] font-mono overflow-x-auto">
                                        {JSON.stringify(agent.output_schema, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Health errors */}
                          {agent.health?.error && (
                            <div className="text-xs text-red">
                              错误: {String(agent.health.error)}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </motion.div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

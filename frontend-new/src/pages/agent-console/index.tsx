import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Cpu,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Code,
  Globe,
  Brain,
  MessageSquare,
  Settings,
  ChevronDown,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"

interface Agent {
  id: string
  name: string
  kind: string
  status: string
  capabilities: string[]
  task_types: string[]
  reliability_score: number
  health: any
  priority: number
  cost_level: string
  latency_level: string
}

interface AgentSummary {
  total: number
  available: number
  unavailable: number
  by_kind: Record<string, number>
  agents: Agent[]
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

export default function AgentConsolePage() {
  const [summary, setSummary] = useState<AgentSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)

  const loadAgents = async () => {
    setIsLoading(true)
    try {
      const response = await fetch("/agent-console/agents").then(r => r.json())
      setSummary(response)
    } catch (error) {
      console.error("Failed to load agents:", error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAgents()
  }, [])

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
            <p className="text-sm text-muted-foreground">本地优先的 AI Agent 管理中心</p>
          </div>
        </div>
        <Button variant="outline" onClick={loadAgents} disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          重新扫描
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{summary?.total || 0}</p>
              <p className="text-sm text-muted-foreground">总 Agent 数</p>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green/10 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green" />
            </div>
            <div>
              <p className="text-2xl font-bold">{summary?.available || 0}</p>
              <p className="text-sm text-muted-foreground">可用</p>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-red/10 flex items-center justify-center">
              <XCircle className="w-5 h-5 text-red" />
            </div>
            <div>
              <p className="text-2xl font-bold">{summary?.unavailable || 0}</p>
              <p className="text-sm text-muted-foreground">不可用</p>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow/10 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-yellow" />
            </div>
            <div>
              <p className="text-2xl font-bold">{Object.keys(summary?.by_kind || {}).length}</p>
              <p className="text-sm text-muted-foreground">Agent 类型</p>
            </div>
          </div>
        </GlowCard>
      </div>

      {/* Agent List */}
      <GlowCard>
        <h3 className="font-semibold mb-4">已发现的 Agent</h3>

        {/* By Kind */}
        {Object.entries(summary?.by_kind || {}).map(([kind, count]) => {
          const Icon = kindIcons[kind] || Cpu
          const label = kindLabels[kind] || kind

          return (
            <div key={kind} className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-4 h-4 text-muted-foreground" />
                <h4 className="font-medium">{label}</h4>
                <Badge variant="outline">{count}</Badge>
              </div>

              <div className="space-y-2">
                {summary?.agents
                  .filter(a => a.kind === kind)
                  .map(agent => (
                    <motion.div
                      key={agent.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-3 rounded-lg border ${
                        agent.status === "available" ? "border-green/20 bg-green/5" : "border-border"
                      }`}
                    >
                      <div
                        className="flex items-center justify-between cursor-pointer"
                        onClick={() => setExpandedAgent(expandedAgent === agent.id ? null : agent.id)}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                            agent.status === "available" ? "bg-green/10" : "bg-muted"
                          }`}>
                            <Icon className={`w-4 h-4 ${
                              agent.status === "available" ? "text-green" : "text-muted-foreground"
                            }`} />
                          </div>
                          <div>
                            <h5 className="font-medium text-sm">{agent.name}</h5>
                            <p className="text-xs text-muted-foreground">{agent.id}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {agent.status === "available" ? (
                            <Badge variant="success" className="text-xs">可用</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">不可用</Badge>
                          )}
                          {expandedAgent === agent.id ? (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {expandedAgent === agent.id && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          className="mt-3 pt-3 border-t border-border space-y-2"
                        >
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-muted-foreground">可靠性:</span>
                              <span className="ml-1">{(agent.reliability_score * 100).toFixed(0)}%</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">优先级:</span>
                              <span className="ml-1">{agent.priority}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">成本:</span>
                              <span className="ml-1">{agent.cost_level}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">延迟:</span>
                              <span className="ml-1">{agent.latency_level}</span>
                            </div>
                          </div>

                          <div>
                            <span className="text-xs text-muted-foreground">支持任务:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {agent.task_types.map(t => (
                                <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
                              ))}
                            </div>
                          </div>

                          <div>
                            <span className="text-xs text-muted-foreground">能力:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {agent.capabilities.map(c => (
                                <Badge key={c} variant="outline" className="text-[10px]">{c}</Badge>
                              ))}
                            </div>
                          </div>

                          {agent.health?.error && (
                            <div className="text-xs text-red">
                              错误: {agent.health.error}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </motion.div>
                  ))}
              </div>
            </div>
          )
        })}
      </GlowCard>
    </div>
  )
}

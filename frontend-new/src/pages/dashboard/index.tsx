import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Activity,
  Database,
  RefreshCw,
  Brain,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Cpu,
  Globe,
  Code,
  Image,
  MessageSquare,
  Zap,
  Coins,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

interface Capability {
  tool: string
  available: boolean
  installed: boolean
  running: boolean
  version: string
  models: any[]
  error: string
  fix_hint: string
}

interface Capabilities {
  [key: string]: Capability
}

const toolIcons: Record<string, any> = {
  hermes: MessageSquare,
  claude_code: Code,
  comfyui: Image,
  ollama: Brain,
  openclaw: Globe,
  data_tools: Database,
  api_models: Cpu,
}

const toolNames: Record<string, string> = {
  hermes: "Hermes Agent",
  claude_code: "Claude Code",
  comfyui: "ComfyUI",
  ollama: "Ollama",
  openclaw: "OpenClaw",
  data_tools: "数据分析工具",
  api_models: "API 模型",
}

export default function DashboardPage() {
  const [capabilities, setCapabilities] = useState<Capabilities>({})
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof api.getSystemMetrics>> | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [capRes, metRes] = await Promise.all([
        fetch("/capabilities").then(r => r.json()).catch(() => ({})),
        api.getSystemMetrics().catch(() => null),
      ])
      setCapabilities(capRes)
      setMetrics(metRes)
      setLastRefresh(new Date())
    } catch (error) {
      console.error("Failed to load dashboard data:", error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const availableCount = Object.values(capabilities).filter(c => c.available).length
  const totalCount = Object.keys(capabilities).length

  const agentEntries = metrics?.agents ? Object.entries(metrics.agents) : []
  const healthyAgents = agentEntries.filter(([, a]) => a === "ok" || a === "healthy").length
  const dbRows = metrics?.db || {}

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">系统状态</h1>
            <p className="text-sm text-[#8A8A8A]">
              最后刷新: {lastRefresh.toLocaleTimeString()}
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={loadData} disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green/10 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green" />
            </div>
            <div>
              <p className="text-2xl font-bold">{availableCount}</p>
              <p className="text-sm text-[#8A8A8A]">可用工具</p>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow/10 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-yellow" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalCount - availableCount}</p>
              <p className="text-sm text-[#8A8A8A]">不可用</p>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-[#0B0B0B]" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalCount}</p>
              <p className="text-sm text-[#8A8A8A]">总工具数</p>
            </div>
          </div>
        </div>
      </div>

      {/* Capability List */}
      <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
        <h3 className="font-semibold mb-4">本地能力中心</h3>
        <div className="space-y-4">
          {Object.entries(capabilities).map(([key, cap]) => {
            const Icon = toolIcons[key] || Cpu
            const name = toolNames[key] || key

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex items-center justify-between p-4 rounded-lg border ${
                  cap.available ? "border-green/20 bg-green/5" : "border-border"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    cap.available ? "bg-green/10" : "bg-muted"
                  }`}>
                    <Icon className={`w-5 h-5 ${cap.available ? "text-green" : "text-[#8A8A8A]"}`} />
                  </div>
                  <div>
                    <h4 className="font-medium">{name}</h4>
                    {cap.version && (
                      <p className="text-xs text-[#8A8A8A]">{cap.version}</p>
                    )}
                    {cap.error && (
                      <p className="text-xs text-red">{cap.error}</p>
                    )}
                    {cap.fix_hint && !cap.available && (
                      <p className="text-xs text-yellow mt-1">💡 {cap.fix_hint}</p>
                    )}
                    {cap.models && cap.models.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {cap.models.slice(0, 3).map((m: any, i: number) => (
                          <Badge key={i} variant="outline" className="text-[10px]">
                            {typeof m === 'string' ? m : m.provider || m.name || ''}
                          </Badge>
                        ))}
                        {cap.models.length > 3 && (
                          <Badge variant="outline" className="text-[10px]">
                            +{cap.models.length - 3}
                          </Badge>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {cap.running && (
                    <Badge variant="success" className="text-xs">运行中</Badge>
                  )}
                  {cap.available ? (
                    <Badge variant="success">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      可用
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <XCircle className="w-3 h-3 mr-1" />
                      不可用
                    </Badge>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>

      {/* System Info — Real Data */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-4">
            <Coins className="w-5 h-5 text-[#0B0B0B]" />
            <h3 className="font-semibold">AI 用量 (24h)</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-[#8A8A8A]">调用次数</span>
              <span className="font-medium">{metrics?.usage?.["24h_calls"] ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#8A8A8A]">Token 用量</span>
              <span className="font-medium">{(metrics?.usage?.["24h_tokens"] ?? 0).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#8A8A8A]">预估费用</span>
              <span className="font-medium">¥{(metrics?.usage?.cost_yuan ?? 0).toFixed(2)}</span>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-[#0B0B0B]" />
            <h3 className="font-semibold">Agent 健康状态</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-[#8A8A8A]">健康</span>
              <span className="font-medium text-green">{healthyAgents} / {agentEntries.length}</span>
            </div>
            {agentEntries.filter(([, a]) => a !== "ok" && a !== "healthy").slice(0, 3).map(([name]) => (
              <div key={name} className="flex justify-between items-center">
                <span className="text-[#8A8A8A]">{name}</span>
                <Badge variant="destructive" className="text-[10px]">异常</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* DB Row Counts */}
      {Object.keys(dbRows).length > 0 && (
        <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-[#0B0B0B]" />
            <h3 className="font-semibold">数据库统计</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(dbRows).map(([table, count]) => (
              <div key={table} className="text-center">
                <p className="text-xl font-bold">{(count as number).toLocaleString()}</p>
                <p className="text-xs text-[#8A8A8A]">{table}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

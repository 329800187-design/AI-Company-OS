import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Activity,
  Database,
  HardDrive,
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
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlowCard } from "@/components/shared/glow-card"
import { Badge } from "@/components/ui/badge"

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
  const [isLoading, setIsLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const loadCapabilities = async () => {
    setIsLoading(true)
    try {
      const response = await fetch("/capabilities").then(r => r.json())
      setCapabilities(response)
      setLastRefresh(new Date())
    } catch (error) {
      console.error("Failed to load capabilities:", error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadCapabilities()
  }, [])

  const availableCount = Object.values(capabilities).filter(c => c.available).length
  const totalCount = Object.keys(capabilities).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">系统状态</h1>
            <p className="text-sm text-muted-foreground">
              最后刷新: {lastRefresh.toLocaleTimeString()}
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={loadCapabilities} disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green/10 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green" />
            </div>
            <div>
              <p className="text-2xl font-bold">{availableCount}</p>
              <p className="text-sm text-muted-foreground">可用工具</p>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow/10 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-yellow" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalCount - availableCount}</p>
              <p className="text-sm text-muted-foreground">不可用</p>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalCount}</p>
              <p className="text-sm text-muted-foreground">总工具数</p>
            </div>
          </div>
        </GlowCard>
      </div>

      {/* Capability List */}
      <GlowCard>
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
                    <Icon className={`w-5 h-5 ${cap.available ? "text-green" : "text-muted-foreground"}`} />
                  </div>
                  <div>
                    <h4 className="font-medium">{name}</h4>
                    {cap.version && (
                      <p className="text-xs text-muted-foreground">{cap.version}</p>
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
      </GlowCard>

      {/* System Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlowCard>
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">数据库</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">状态</span>
              <Badge variant="success">正常运行</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">模式</span>
              <span>WAL (高性能)</span>
            </div>
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-center gap-2 mb-4">
            <HardDrive className="w-5 h-5 text-primary" />
            <h3 className="font-semibold">服务状态</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">API 服务</span>
              <Badge variant="success">运行中</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">本地优先模式</span>
              <Badge variant="success">已启用</Badge>
            </div>
          </div>
        </GlowCard>
      </div>
    </div>
  )
}

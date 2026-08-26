import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  GitBranch,
  Play,
  ChevronRight,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/api/client"

interface WorkflowSummary {
  name: string
  count: number
}

interface WorkflowDetail {
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
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<WorkflowDetail | null>(null)
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState<{ status: string; workflow: string; results: Record<string, unknown> } | null>(null)

  const loadWorkflows = async () => {
    setLoading(true)
    try {
      const res = await api.listWorkflows()
      setWorkflows(res.workflows || [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadWorkflows()
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [])

  const loadDetail = async (name: string) => {
    try {
      const detail = await api.getWorkflow(name)
      setSelected(detail)
      setRunResult(null)
    } catch (e) {
      console.error("Failed to load workflow:", e)
    }
  }

  const handleRun = async () => {
    if (!selected) return
    setRunning(true)
    setRunResult(null)
    try {
      const result = await api.runWorkflow(selected.name)
      setRunResult(result)
    } catch (e) {
      console.error("Failed to run workflow:", e)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
          <GitBranch className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">工作流</h1>
          <p className="text-sm text-[#8A8A8A]">DAG 工作流编排与执行</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Workflow List */}
        <div className="lg:col-span-1 space-y-3">
          <h3 className="text-xs text-[#8A8A8A] uppercase tracking-wider">可用工作流</h3>
          {loading ? (
            <div className="flex justify-center py-8">
              <RefreshCw className="w-5 h-5 animate-spin text-[#8A8A8A]" />
            </div>
          ) : workflows.length === 0 ? (
            <p className="text-sm text-[#8A8A8A] py-8 text-center">暂无工作流</p>
          ) : (
            workflows.map(wf => (
              <motion.button
                key={wf.name}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                onClick={() => loadDetail(wf.name)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  selected?.name === wf.name
                    ? "border-[#0B0B0B] bg-[#F4F3EF]"
                    : "border-[#E5E5E5] bg-white hover:border-[#B5B5B5]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-sm">{wf.name}</h4>
                    <p className="text-xs text-[#8A8A8A]">{wf.count} 个步骤</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[#D4D4D4]" />
                </div>
              </motion.button>
            ))
          )}
        </div>

        {/* Workflow Detail */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="flex flex-col items-center justify-center py-20 text-[#8A8A8A]">
              <GitBranch className="w-10 h-10 mb-3 text-[#D4D4D4]" />
              <p>选择一个工作流查看详情</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-lg font-bold">{selected.title || selected.name}</h2>
                    <p className="text-sm text-[#8A8A8A]">{selected.description}</p>
                  </div>
                  <Button onClick={handleRun} disabled={running}>
                    {running ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
                    {running ? "运行中..." : "运行"}
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-[#8A8A8A]">
                  <span>版本: {selected.version}</span>
                  {selected.triggers.length > 0 && (
                    <span>触发: {selected.triggers.join(", ")}</span>
                  )}
                </div>
              </div>

              {/* Steps */}
              <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
                <h3 className="font-semibold mb-4">执行步骤 ({selected.steps.length})</h3>
                <div className="space-y-3">
                  {selected.steps.map((step, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-[#F4F3EF]">
                      <div className="w-7 h-7 rounded-full bg-white border border-[#E5E5E5] flex items-center justify-center text-xs font-medium shrink-0">
                        {i + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium">{step.name}</h4>
                        <div className="flex items-center gap-2 text-xs text-[#8A8A8A]">
                          <Badge variant="outline" className="text-[10px]">{step.agent}</Badge>
                          <span>{step.task_type}</span>
                        </div>
                      </div>
                      {step.depends_on.length > 0 && (
                        <span className="text-[10px] text-[#D4D4D4] shrink-0">依赖: {step.depends_on.join(", ")}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Run Result */}
              {runResult && (
                <div className={`p-6 rounded-2xl border ${
                  runResult.status === "ok" ? "border-green/20 bg-green/5" : "border-red/20 bg-red/5"
                }`}>
                  <div className="flex items-center gap-2 mb-3">
                    {runResult.status === "ok" ? (
                      <CheckCircle2 className="w-5 h-5 text-green" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-red" />
                    )}
                    <h3 className="font-semibold">运行结果</h3>
                  </div>
                  <pre className="text-xs text-[#8A8A8A] overflow-x-auto max-h-60 overflow-y-auto">
                    {JSON.stringify(runResult.results, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  ClipboardList,
  Download,
  Eye,
  EyeOff,
  Upload,
  FileText,
  Globe2,
  HardDrive,
  History,
  Loader2,
  Megaphone,
  Play,
  Plus,
  RotateCcw,
  Search,
  Shield,
  ShieldOff,
  SkipForward,
  Sparkles,
  Target,
  Zap,
  BarChart3,
  Palette,
  BookOpen,
  Trash2,
  GitBranch,
  Copy,
  GitCompareArrows,
  Pencil,
  Pin,
  X,
} from "lucide-react"
import { api } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { DagEditor, type GraphTemplateDraft } from "./DagEditor"
import { DagCanvas } from "./DagCanvas"
import { validateDag } from "./dag-validation"

interface ModuleResult {
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
  started_at?: string
  finished_at?: string
  duration_ms?: number
  next_actions?: string[]
  structured_output?: Record<string, unknown>
}

interface Mission {
  mission_id: string
  goal: string
  status: string
  created_at?: string
  updated_at?: string
  modules: ModuleResult[]
  metrics?: MissionMetrics
}

interface MissionSummary {
  mission_id: string
  goal: string
  status: string
  created_at: string
}

interface MissionEvent {
  id: number
  mission_id: string
  type: string
  module_id: string | null
  message: string
  payload: Record<string, unknown>
  created_at: string
}

// Phase 6.19: 通用业务流程模板
interface InputField {
  name: string
  label: string
  type: "text" | "select"
  required: boolean
  placeholder?: string
  options?: string[]
  default?: string
}

interface OutputSection {
  id: string
  title: string
  module: string
}

interface MissionTemplate {
  id: string
  name: string
  description: string
  default_goal: string
  default_modules: string[]
  suggested_inputs: string[]
  expected_outputs: string[]
  // Phase 6.19 新增
  input_fields?: InputField[]
  output_schema?: { sections: OutputSection[] }
  expected_sections?: string[]
  suggested_review_checklist?: string[]
  prompt_overrides?: Record<string, string>
}

interface MissionMetrics {
  total_modules: number
  succeeded_modules: number
  failed_modules: number
  skipped_modules: number
  interrupted_modules?: number
  duration_ms: number
  warning_count: number
  next_action_count: number
  completion_rate: number
}

const MODULE_IDS = ["strategy", "market", "marketing", "landing", "actions"]

const moduleIcons: Record<string, React.ElementType> = {
  strategy: Target,
  market: Search,
  marketing: Megaphone,
  landing: Globe2,
  actions: ClipboardList,
}

const moduleDescriptions: Record<string, string> = {
  strategy: "理解目标，提取核心意图，给出策略判断、机会和风险。",
  market: "围绕目标收集上下文、事实依据、参考案例和数据支撑。",
  marketing: "设计沟通策略、内容方向、触达渠道和具体文案。",
  landing: "设计可交付物的结构、框架和核心内容。",
  actions: "将目标拆解为可执行的行动项，按时间或优先级排列。",
}

// Boss Lite 常用入口（通用业务流程，不绑定具体行业）
const liteTemplates = [
  {
    id: "goal-to-plan",
    label: "目标到计划",
    icon: Target,
    goal: "我有一个业务目标需要拆解成可执行计划，产出策略判断、关键依据和分阶段行动项。",
  },
  {
    id: "research-to-decision",
    label: "调研到决策",
    icon: Search,
    goal: "我需要做一个业务决策，希望先收集充分的上下文信息、分析备选方案、给出推荐建议。",
  },
  {
    id: "deliverable",
    label: "交付物生成",
    icon: FileText,
    goal: "我需要生成一套结构化的交付物，包含内容框架、核心内容、质量检查和交付清单。",
  },
  {
    id: "communication",
    label: "沟通方案",
    icon: Megaphone,
    goal: "我需要设计一套沟通触达方案，包含受众分析、核心信息、渠道策略和内容方案。",
  },
  {
    id: "review",
    label: "流程复盘",
    icon: ClipboardList,
    goal: "我需要对上一阶段的工作进行复盘，总结成果、诊断问题、提炼经验教训、制定改进计划。",
  },
  {
    id: "risk-check",
    label: "风险检查",
    icon: Shield,
    goal: "我需要对当前计划进行风险评估，识别潜在问题、评估影响、给出应对方案和监控指标。",
  },
  {
    id: "execution",
    label: "执行清单",
    icon: Play,
    goal: "我需要将一个复杂任务拆解为详细的执行清单，含步骤、检查项和验收标准。",
  },
  {
    id: "data-insight",
    label: "数据洞察",
    icon: BarChart3,
    goal: "我需要从一组数据或指标中找到关键洞察、发现问题、给出行动建议。",
  },
]

const examples = [
  "帮我分析这个业务方向是否值得投入，给出策略判断和执行计划",
  "设计一套用户增长的沟通触达方案",
  "对上个月的工作做一次复盘，找到问题和改进方向",
  "帮我生成一份项目提案文档",
]

// Boss Lite agent icons
const agentIcons: Record<string, React.ElementType> = {
  research: BookOpen,
  marketing: Megaphone,
  image: Palette,
  data: BarChart3,
  website: Globe2,
}

function valueToText(value: unknown): string {
  if (value == null) return ""
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  if (Array.isArray(value)) return value.map(valueToText).filter(Boolean).join("；")
  if (typeof value === "object") {
    const record = value as Record<string, unknown>
    const name = record.name || record.title || record.metric || record.label
    const description = record.description || record.summary || record.value
    const formula = record.formula
    const parts = [name, description].filter(Boolean).map(String)
    if (formula) parts.push(`公式：${String(formula)}`)
    if (parts.length) return parts.join(" — ")
    return Object.entries(record).slice(0, 4).map(([key, val]) => `${key}: ${valueToText(val)}`).join("；")
  }
  return String(value)
}

function listToText(value: unknown, limit = 3): string {
  if (Array.isArray(value)) return value.slice(0, limit).map(valueToText).filter(Boolean).join("；")
  return valueToText(value)
}

/** 从 structured_output 中提取可读摘要，控制在 80-120 字 */
function formatDuration(ms?: number): string | null {
  if (!ms || ms <= 0) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// ── Graph helpers ──────────────────────────────────────────────

interface GraphNode {
  id: string
  agent_id?: string
  title?: string
  ok?: boolean
  duration_ms?: number
  summary?: string
  used_handoff?: boolean
  handoff_sources?: string[]
}

interface GraphEdge {
  from: string
  to: string
  type?: string
  inferred?: boolean
}

interface NormalizedGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  waves: string[][]
}

function truncateText(text?: string, max = 80): string {
  if (!text) return ""
  return text.length > max ? text.slice(0, max - 3) + "..." : text
}

function getNodeStatus(node: GraphNode): "success" | "failed" | "unknown" {
  if (node.ok === true) return "success"
  if (node.ok === false) return "failed"
  return "unknown"
}

function normalizeGraphResult(result: Record<string, unknown>): NormalizedGraph | null {
  if (!result) return null

  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  let waves: string[][] = []

  // Source 1: result.graph or result.structured_output.graph
  const graphData = (result.graph as Record<string, unknown>) || ((result.structured_output as Record<string, unknown>)?.graph as Record<string, unknown>)
  const wavesData = (result.waves as string[][]) || ((result.structured_output as Record<string, unknown>)?.waves as string[][])

  // Collect results array
  const resultsArr = (result.results as Array<Record<string, unknown>>) || []

  // Build nodes from results
  if (resultsArr.length > 0) {
    for (const r of resultsArr) {
      nodes.push({
        id: (r.node_id as string) || (r.agent_id as string) || "unknown",
        agent_id: r.agent_id as string | undefined,
        title: (r.title as string) || (r.agent_id as string),
        ok: r.ok as boolean | undefined,
        duration_ms: r.duration_ms as number | undefined,
        summary: r.summary as string | undefined,
        used_handoff: r.used_handoff as boolean | undefined,
        handoff_sources: r.handoff_sources as string[] | undefined,
      })
    }
  }

  // Source 2: graph.nodes (override if present)
  if (graphData?.nodes && Array.isArray(graphData.nodes)) {
    const gNodes = graphData.nodes as Array<Record<string, unknown>>
    if (nodes.length === 0) {
      for (const n of gNodes) {
        nodes.push({
          id: (n.id as string) || (n.agent_id as string) || "unknown",
          agent_id: n.agent_id as string | undefined,
          title: (n.title as string) || (n.label as string),
          ok: n.ok as boolean | undefined,
        })
      }
    }
  }

  // Build edges
  if (graphData?.edges && Array.isArray(graphData.edges)) {
    for (const e of graphData.edges as Array<Record<string, unknown>>) {
      edges.push({
        from: (e.from as string) || (e.source as string) || "",
        to: (e.to as string) || (e.target as string) || "",
        type: e.type as string | undefined,
        inferred: e.inferred as boolean | undefined,
      })
    }
  }

  // Fallback: infer edges from handoff_sources
  if (edges.length === 0) {
    // Per-node handoff_sources → inferred edges
    for (const node of nodes) {
      if (node.handoff_sources && node.handoff_sources.length > 0) {
        for (const src of node.handoff_sources) {
          edges.push({ from: src, to: node.id, type: "handoff", inferred: true })
        }
      }
    }
    // Global handoff_sources → handoff_targets
    if (edges.length === 0) {
      const so = (result.structured_output as Record<string, unknown>) || {}
      const hoEnabled = (result.handoff_enabled as boolean) ?? (so.handoff_enabled as boolean)
      if (hoEnabled) {
        const sources = (so.handoff_sources as string[]) || []
        const targets = (so.handoff_targets as string[]) || []
        if (sources.length > 0 && targets.length > 0) {
          for (const src of sources) {
            for (const tgt of targets) {
              edges.push({ from: src, to: tgt, type: "handoff", inferred: true })
            }
          }
        }
      }
    }
  }

  // Build waves
  if (wavesData && Array.isArray(wavesData) && wavesData.length > 0) {
    waves = wavesData
  } else {
    // Infer waves from handoff structure
    const so = (result.structured_output as Record<string, unknown>) || {}
    const hoEnabled = (result.handoff_enabled as boolean) ?? (so.handoff_enabled as boolean)
    if (hoEnabled && edges.length > 0) {
      // Topological wave inference: sources first, targets second
      const sourceIds = new Set(edges.map(e => e.from))
      const targetIds = new Set(edges.map(e => e.to))
      const wave1 = nodes.filter(n => sourceIds.has(n.id) && !targetIds.has(n.id)).map(n => n.id)
      const wave2 = nodes.filter(n => targetIds.has(n.id)).map(n => n.id)
      const wave0 = nodes.filter(n => !sourceIds.has(n.id) && !targetIds.has(n.id)).map(n => n.id)
      if (wave0.length > 0) waves.push(wave0)
      if (wave1.length > 0) waves.push(wave1)
      if (wave2.length > 0) waves.push(wave2)
    }
    if (waves.length === 0) {
      // All nodes in one wave
      waves = [nodes.map(n => n.id)]
    }
  }

  if (nodes.length === 0) return null
  return { nodes, edges, waves }
}

// ── Graph Preview Card ─────────────────────────────────────────

function GraphPreviewCard({ graph }: { graph: NormalizedGraph }) {
  const nodeMap = new Map(graph.nodes.map(n => [n.id, n]))

  return (
    <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
      <div className="flex items-center gap-2 mb-5">
        <BarChart3 className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold text-[#0B0B0B]">协作图 / Collaboration Graph</h3>
        <Badge variant="outline">{graph.nodes.length} 节点</Badge>
        <Badge variant="outline">{graph.edges.length} 边</Badge>
      </div>

      {/* Waves */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-[#8A8A8A] mb-3 uppercase tracking-wider">执行波次 / Waves</h4>
        <div className="flex flex-col gap-3 sm:flex-row">
          {graph.waves.map((wave, wi) => (
            <div key={wi} className="flex-1 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-4">
              <div className="text-xs font-medium text-[#B5B5B5] mb-2">Wave {wi + 1}</div>
              <div className="flex flex-wrap gap-2">
                {wave.map(nodeId => {
                  const node = nodeMap.get(nodeId)
                  const status = getNodeStatus(node || { id: nodeId })
                  return (
                    <span
                      key={nodeId}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
                        status === "success" && "bg-green/10 text-green border border-green/20",
                        status === "failed" && "bg-red-50 text-red-500 border border-red/20",
                        status === "unknown" && "bg-[#F4F3EF] text-[#8A8A8A] border border-[#E5E5E5]"
                      )}
                    >
                      {status === "success" ? "✓" : status === "failed" ? "✗" : "·"} {node?.title || nodeId}
                      {node?.used_handoff && (
                        <span className="ml-1 px-1 py-0.5 rounded text-[10px] bg-primary/10 text-primary border border-primary/20">
                          已接收上游
                        </span>
                      )}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Edges */}
      {graph.edges.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-[#8A8A8A] mb-3 uppercase tracking-wider">依赖关系 / Edges</h4>
          <div className="flex flex-wrap gap-2">
            {graph.edges.map((edge, i) => (
              <span
                key={i}
                className={cn(
                  "inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-mono",
                  edge.inferred
                    ? "bg-yellow-50 text-yellow-700 border border-yellow/20"
                    : "bg-[#F4F3EF] text-[#5A5A5A] border border-[#E5E5E5]"
                )}
              >
                {edge.from}
                <span className="text-[#B5B5B5]">→</span>
                {edge.to}
                {edge.type && (
                  <span className="ml-1 text-[10px] text-[#8A8A8A]">({edge.type})</span>
                )}
                {edge.inferred && (
                  <span className="ml-1 text-[10px] text-yellow-600">推断</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Node Details */}
      <div>
        <h4 className="text-sm font-medium text-[#8A8A8A] mb-3 uppercase tracking-wider">节点详情 / Nodes</h4>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {graph.nodes.map(node => {
            const status = getNodeStatus(node)
            return (
              <div
                key={node.id}
                className={cn(
                  "rounded-xl border p-4",
                  status === "success" && "border-green/20 bg-green/5",
                  status === "failed" && "border-red/20 bg-red/5",
                  status === "unknown" && "border-[#E5E5E5] bg-[#FAFAF8]"
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-[#0B0B0B]">{node.title || node.id}</span>
                  <Badge variant={status === "success" ? "success" : status === "failed" ? "destructive" : "secondary"}>
                    {status === "success" ? "成功" : status === "failed" ? "失败" : "未知"}
                  </Badge>
                </div>
                <div className="space-y-1 text-xs text-[#8A8A8A]">
                  {node.agent_id && node.agent_id !== node.id && (
                    <div>Agent: <span className="font-mono">{node.agent_id}</span></div>
                  )}
                  <div>ID: <span className="font-mono">{node.id}</span></div>
                  {node.duration_ms != null && node.duration_ms > 0 && (
                    <div>耗时: {formatDuration(node.duration_ms)}</div>
                  )}
                  {node.used_handoff && (
                    <div className="flex items-center gap-1 text-primary">
                      <Sparkles className="h-3 w-3" />
                      已接收上游
                    </div>
                  )}
                  {node.handoff_sources && node.handoff_sources.length > 0 && (
                    <div>来源: {node.handoff_sources.join(", ")}</div>
                  )}
                  {node.summary && (
                    <div className="mt-1.5 pt-1.5 border-t border-[#E5E5E5] text-[#6B6B6B]">
                      {truncateText(node.summary, 80)}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── End Graph helpers ──────────────────────────────────────────

function extractAgentSummary(agentId: string, summary: string, so: Record<string, unknown>): string {
  // 优先用 summary
  if (summary && summary.length > 10) return summary.length > 120 ? summary.slice(0, 117) + "..." : summary

  // 按 agent 类型提取关键字段
  switch (agentId) {
    case "research": {
      const parts: string[] = []
      const ms = so.market_summary as string
      if (ms) parts.push(ms)
      const kf = so.key_findings as unknown[]
      if (kf?.length) parts.push(`发现: ${valueToText(kf[0])}`)
      const op = so.opportunities as unknown[]
      if (op?.length) parts.push(`机会: ${valueToText(op[0])}`)
      const rk = so.risks as unknown[]
      if (rk?.length) parts.push(`风险: ${valueToText(rk[0])}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "上下文整理完成"
    }
    case "marketing": {
      const parts: string[] = []
      const hl = so.headline as string
      if (hl) parts.push(hl)
      const sub = so.subheadline as string
      if (sub) parts.push(sub)
      const cta = so.cta as string
      if (cta) parts.push(`CTA: ${cta}`)
      const kw = so.keywords as unknown[]
      if (kw?.length) parts.push(`关键词: ${kw.slice(0, 3).map(valueToText).join("/")}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "沟通表达完成"
    }
    case "image": {
      const parts: string[] = []
      const ip = so.image_prompt as string
      if (ip) parts.push(`提示词: ${ip}`)
      const st = so.style as string
      if (st) parts.push(`风格: ${st}`)
      const cp = so.color_palette
      if (cp) parts.push(`色彩: ${valueToText(cp)}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "素材方向完成"
    }
    case "data": {
      const parts: string[] = []
      const aq = so.analysis_question as string
      if (aq) parts.push(aq)
      const km = so.key_metrics as unknown[]
      if (km?.length) parts.push(`指标: ${valueToText(km[0])}`)
      const fn = so.findings as unknown[]
      if (fn?.length) parts.push(`发现: ${valueToText(fn[0])}`)
      const rc = so.recommendations as unknown[]
      if (rc?.length) parts.push(`建议: ${valueToText(rc[0])}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "数据洞察完成"
    }
    case "website": {
      const parts: string[] = []
      const pg = so.page_goal as string
      if (pg) parts.push(pg)
      const hero = so.hero as Record<string, unknown>
      if (hero?.headline) parts.push(`核心: ${hero.headline}`)
      const sections = so.sections as Array<Record<string, unknown>>
      if (sections?.length) parts.push(`${sections.length} 个板块`)
      const seo = so.seo as Record<string, unknown>
      if (seo?.title) parts.push(`检索展示: ${seo.title}`)
      return parts.map(valueToText).join("；").slice(0, 120) || "交付物结构完成"
    }
    default:
      return summary || "执行完成"
  }
}

/** 从 structured_output 中提取结构化关键字段 */
function extractKeyFields(agentId: string, so: Record<string, unknown>): Array<{ label: string; value: string }> {
  const fields: Array<{ label: string; value: string }> = []
  if (!so || Object.keys(so).length === 0) return fields

  switch (agentId) {
    case "research":
      if (so.market_summary) fields.push({ label: "市场摘要", value: String(so.market_summary).slice(0, 200) })
      if (so.key_findings) fields.push({ label: "关键发现", value: listToText(so.key_findings, 3) })
      if (so.opportunities) fields.push({ label: "机会", value: listToText(so.opportunities, 3) })
      if (so.risks) fields.push({ label: "风险", value: listToText(so.risks, 3) })
      break
    case "marketing":
      if (so.headline) fields.push({ label: "核心文案", value: String(so.headline) })
      if (so.subheadline) fields.push({ label: "副标题", value: String(so.subheadline) })
      if (so.cta) fields.push({ label: "CTA", value: String(so.cta) })
      if (so.selling_points) fields.push({ label: "核心卖点", value: listToText(so.selling_points, 5) })
      if (so.keywords) fields.push({ label: "关键词", value: listToText(so.keywords, 5) })
      break
    case "image":
      if (so.style) fields.push({ label: "视觉风格", value: String(so.style) })
      if (so.image_prompt) fields.push({ label: "图片提示词", value: String(so.image_prompt).slice(0, 200) })
      if (so.color_palette) fields.push({ label: "色彩方案", value: valueToText(so.color_palette) })
      if (so.usage_suggestions) fields.push({ label: "使用建议", value: valueToText(so.usage_suggestions).slice(0, 200) })
      break
    case "data":
      if (so.analysis_question) fields.push({ label: "分析主题", value: String(so.analysis_question) })
      if (so.key_metrics) fields.push({ label: "关键指标", value: listToText(so.key_metrics, 5) })
      if (so.findings) fields.push({ label: "发现", value: listToText(so.findings, 3) })
      if (so.recommendations) fields.push({ label: "建议", value: listToText(so.recommendations, 3) })
      break
    case "website":
      if (so.page_goal) fields.push({ label: "交付目标", value: String(so.page_goal) })
      {
        const hero = so.hero as Record<string, unknown> | undefined
        if (hero?.headline) fields.push({ label: "核心标题", value: String(hero.headline) })
        if (hero?.cta) fields.push({ label: "核心 CTA", value: String(hero.cta) })
      }
      if (so.sections) {
        const secs = so.sections as Array<Record<string, unknown>>
        fields.push({ label: "交付板块", value: secs.slice(0, 5).map(s => s.title || s.name || "板块").join("、") })
      }
      break
  }
  return fields
}

const DRAFT_STORAGE_KEY = "boss_graph_template_draft_v2"
const DRAFT_STORAGE_KEY_V1 = "boss_graph_template_draft_v1"

function validateGraphTemplateDraft(data: unknown): { valid: true; draft: GraphTemplateDraft } | { valid: false; error: string } {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { valid: false, error: "JSON 格式错误：不是对象" }
  }

  const object = data as Record<string, unknown>
  if (typeof object.name !== "string") return { valid: false, error: "缺少 name 字段（字符串）" }
  if (!Array.isArray(object.nodes)) return { valid: false, error: "缺少 nodes 数组" }
  if (!Array.isArray(object.edges)) return { valid: false, error: "缺少 edges 数组" }
  if (object.nodes.length === 0) return { valid: false, error: "nodes 至少需要 1 个节点" }

  const nodeFields = ["id", "agent_id", "task_type", "title", "prompt"] as const
  for (let index = 0; index < object.nodes.length; index++) {
    const node = object.nodes[index]
    if (!node || typeof node !== "object" || Array.isArray(node)) {
      return { valid: false, error: `节点 ${index + 1}: 格式错误` }
    }
    const record = node as Record<string, unknown>
    for (const field of nodeFields) {
      if (typeof record[field] !== "string") {
        return { valid: false, error: `节点 ${index + 1}: ${field} 必须是字符串` }
      }
    }
  }

  const edgeFields = ["from_node", "to_node", "handoff_type"] as const
  for (let index = 0; index < object.edges.length; index++) {
    const edge = object.edges[index]
    if (!edge || typeof edge !== "object" || Array.isArray(edge)) {
      return { valid: false, error: `边 ${index + 1}: 格式错误` }
    }
    const record = edge as Record<string, unknown>
    for (const field of edgeFields) {
      if (typeof record[field] !== "string") {
        return { valid: false, error: `边 ${index + 1}: ${field} 必须是字符串` }
      }
    }
  }

  const draft: GraphTemplateDraft = {
    name: object.name,
    description: typeof object.description === "string" ? object.description : "",
    goal_hint: typeof object.goal_hint === "string" ? object.goal_hint : "",
    nodes: object.nodes as GraphTemplateDraft["nodes"],
    edges: object.edges as GraphTemplateDraft["edges"],
  }
  const dagErrors = validateDag(draft.nodes, draft.edges)
  if (dagErrors.length > 0) {
    return { valid: false, error: dagErrors.map((error) => error.message).join("; ") }
  }

  return { valid: true, draft }
}

export default function BossPage() {
  // Mode: "command-center" or "boss-lite"
  const [mode, setMode] = useState<"command-center" | "boss-lite">("boss-lite")
  const [goal, setGoal] = useState("")
  const [activeModule, setActiveModule] = useState("strategy")
  const [isRunning, setIsRunning] = useState(false)
  const [currentMission, setCurrentMission] = useState<Mission | null>(null)
  const [recentMissions, setRecentMissions] = useState<MissionSummary[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [enabledModules, setEnabledModules] = useState<string[]>([...MODULE_IDS])
  const [events, setEvents] = useState<MissionEvent[]>([])
  const [showEvents, setShowEvents] = useState(false)
  const [templates, setTemplates] = useState<MissionTemplate[]>([])
  const [showTemplates, setShowTemplates] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<MissionTemplate | null>(null)
  const [inputValues, setInputValues] = useState<Record<string, string>>({})
  const [showInputForm, setShowInputForm] = useState(false)
  const [allowBrowserAutomation, setAllowBrowserAutomation] = useState(false)
  const [exportToast, setExportToast] = useState<"json" | "markdown" | null>(null)
  const [missionError, setMissionError] = useState<string | null>(null)

  // 轮询 timer refs（Phase 6.15: 模块级进度轮询）
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollFailCountRef = useRef(0)

  // Boss Lite state
  const [liteResult, setLiteResult] = useState<{
    ok: boolean
    task_id: string
    goal: string
    handoff_enabled?: boolean
    execution_mode?: string
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
      duration_ms?: number
      used_handoff?: boolean
      handoff_sources?: string[]
    }>
    summary: {
      text: string
      succeeded: number
      failed: number
      total: number
      total_duration_ms?: number
    }
    structured_output: Record<string, unknown> & {
      total_duration_ms?: number
      handoff_enabled?: boolean
      handoff_sources?: string[]
      handoff_targets?: string[]
    }
    delivery_task_id?: string
  } | null>(null)
  const [liteActiveAgent, setLiteActiveAgent] = useState<string>("")
  const [liteProgressPhase, setLiteProgressPhase] = useState(0)
  const [copiedHistoryGoalId, setCopiedHistoryGoalId] = useState<string | null>(null)

  // Boss Lite 历史记录 — 分页加载
  const LITE_HISTORY_STEP = 5
  const [liteHistoryLimit, setLiteHistoryLimit] = useState(LITE_HISTORY_STEP)
  const [liteHistoryHasMore, setLiteHistoryHasMore] = useState(false)

  // Boss Lite 历史搜索
  const [liteHistoryQuery, setLiteHistoryQuery] = useState("")

  // Boss Lite 历史排序
  const [liteHistorySort, setLiteHistorySort] = useState<"newest" | "oldest" | "task_id">("newest")

  // Boss Lite 历史记录
  const [liteHistory, setLiteHistory] = useState<Array<{
    task_id: string
    goal: string
    created_at: string
    summary?: string
    artifact_type?: string
    agent_id?: string
    source_page?: string
    // Boss Lite 复盘字段（可选）
    succeeded?: number
    failed?: number
    total?: number
    total_duration_ms?: number
    handoff_enabled?: boolean
    execution_mode?: string
  }>>([])

  // 隐藏任务 ID 管理（localStorage）
  const HIDDEN_KEY = "boss_lite_hidden_task_ids"
  const getHiddenIds = (): string[] => {
    try {
      const raw = localStorage.getItem(HIDDEN_KEY)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  }
  const [hiddenTaskIds, setHiddenTaskIds] = useState<string[]>(getHiddenIds)

  const hideTask = (taskId: string) => {
    const next = [...hiddenTaskIds, taskId]
    setHiddenTaskIds(next)
    try { localStorage.setItem(HIDDEN_KEY, JSON.stringify(next)) } catch { /* ignore */ }
    setLiteHistory((prev) => prev.filter((t) => t.task_id !== taskId))
  }

  const restoreAllHidden = () => {
    setHiddenTaskIds([])
    try { localStorage.removeItem(HIDDEN_KEY) } catch { /* ignore */ }
    loadLiteHistory()
  }

  // ── 任务对比状态 ──────────────────────────────────────────
  const [liteCompareSelected, setLiteCompareSelected] = useState<string[]>([])
  const [liteCompareResult, setLiteCompareResult] = useState<{
    ok: boolean
    tasks: Array<{
      task_id: string
      goal: string | null
      created_at: string
      artifact_type: string | null
      succeeded: number | null
      failed: number | null
      total: number | null
      total_duration_ms: number | null
      handoff_enabled: boolean | null
      execution_mode: string | null
      summary: string | null
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
  } | null>(null)
  const [liteCompareLoading, setLiteCompareLoading] = useState(false)
  const [liteCompareError, setLiteCompareError] = useState<string | null>(null)

  const toggleCompareSelect = (taskId: string) => {
    setLiteCompareSelected((prev) => {
      if (prev.includes(taskId)) {
        const next = prev.filter((id) => id !== taskId)
        if (next.length < 2) setLiteCompareResult(null)
        return next
      }
      if (prev.length >= 2) return prev // 最多 2 个
      const next = [...prev, taskId]
      return next
    })
  }

  const clearCompare = () => {
    setLiteCompareSelected([])
    setLiteCompareResult(null)
    setLiteCompareError(null)
  }

  // 当选中 2 个时自动触发对比
  useEffect(() => {
    if (liteCompareSelected.length !== 2) return
    let cancelled = false
    const run = async () => {
      setLiteCompareLoading(true)
      setLiteCompareError(null)
      try {
        const result = await api.compareMiniDeliveryTasks(liteCompareSelected as [string, string])
        if (!cancelled) setLiteCompareResult(result)
      } catch (err: any) {
        if (!cancelled) setLiteCompareError(err?.message || "对比失败")
      } finally {
        if (!cancelled) setLiteCompareLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [liteCompareSelected])

  // Graph Template state
  interface GraphTemplate {
    template_id: string
    name: string
    description: string
    goal_hint: string
    nodes: Array<{ id: string; agent_id: string; task_type: string; title: string; prompt: string }>
    edges: Array<{ from_node: string; to_node: string; handoff_type: string }>
    created_at: string
    updated_at: string
    canvas_layout?: Record<string, { x: number; y: number }>
  }
  const [graphTemplates, setGraphTemplates] = useState<GraphTemplate[]>([])
  const [graphTemplatesLoading, setGraphTemplatesLoading] = useState(false)
  const [graphTemplatesError, setGraphTemplatesError] = useState<string | null>(null)
  const [graphTemplateExecutingId, setGraphTemplateExecutingId] = useState<string | null>(null)
  const [graphTemplateResult, setGraphTemplateResult] = useState<Record<string, unknown> | null>(null)
  const [expandedPreviewId, setExpandedPreviewId] = useState<string | null>(null)

  // Graph Template 创建表单状态
  const DEFAULT_DRAFT: GraphTemplateDraft = {
    name: "调研到执行协作图",
    description: "research → marketing",
    goal_hint: "围绕一个业务目标进行调研并产出执行方案",
    nodes: [
      { id: "research", agent_id: "research", task_type: "research_brief", title: "上下文整理", prompt: "围绕目标收集相关上下文、事实依据和参考案例" },
      { id: "marketing", agent_id: "marketing", task_type: "copywriting", title: "沟通方案", prompt: "基于上游洞察设计沟通策略和内容方案" },
    ],
    edges: [
      { from_node: "research", to_node: "marketing", handoff_type: "context" },
    ],
  }
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createDraft, setCreateDraft] = useState<GraphTemplateDraft>(DEFAULT_DRAFT)
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createFormError, setCreateFormError] = useState<string | null>(null)
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null)
  const [cloneSourceId, setCloneSourceId] = useState<string | null>(null)

  // ── Phase 6.11: Debounced layout save to backend ────────────
  const layoutSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const editingTemplateIdRef = useRef<string | null>(null)
  // Keep ref in sync with state so debounced callback always reads current ID
  useEffect(() => {
    editingTemplateIdRef.current = editingTemplateId
    // Cancel any pending layout save from previous template
    if (layoutSaveTimerRef.current) {
      clearTimeout(layoutSaveTimerRef.current)
      layoutSaveTimerRef.current = null
    }
  }, [editingTemplateId])

  const handleCanvasLayoutChange = useCallback(
    (layout: Record<string, { x: number; y: number }>) => {
      const templateId = editingTemplateIdRef.current
      if (!templateId) return
      if (layoutSaveTimerRef.current) clearTimeout(layoutSaveTimerRef.current)
      layoutSaveTimerRef.current = setTimeout(async () => {
        try {
          await api.updateBossGraphTemplateLayout(templateId, layout)
        } catch (err) {
          console.warn("Failed to persist canvas layout:", err)
        }
      }, 800)
    },
    [],
  )

  // ── Draft auto-save / restore (localStorage) ────────────────
  const draftSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const suppressDraftSaveRef = useRef(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [pendingRestoreDraft, setPendingRestoreDraft] = useState<GraphTemplateDraft | null>(() => {
    try {
      // Phase 6.24: 清理旧 v1 草稿缓存，避免用户看到旧文案"上下文调研"
      try { localStorage.removeItem(DRAFT_STORAGE_KEY_V1) } catch { /* ignore */ }

      const raw = localStorage.getItem(DRAFT_STORAGE_KEY)
      if (raw) {
        const result = validateGraphTemplateDraft(JSON.parse(raw))
        if (result.valid) return result.draft
        localStorage.removeItem(DRAFT_STORAGE_KEY)
      }
    } catch {
      try { localStorage.removeItem(DRAFT_STORAGE_KEY) } catch { /* ignore */ }
    }
    return null
  })
  const [importError, setImportError] = useState<string | null>(null)

  // ── Phase 6.6: Version History state ──────────────────────
  const [versionListTemplateId, setVersionListTemplateId] = useState<string | null>(null)
  const [versionList, setVersionList] = useState<Array<{
    version_id: string
    template_id: string
    created_at: string
    label: string
    note: string
    pinned: boolean
    name: string
    node_count: number
    edge_count: number
  }> | null>(null)
  const [versionListLoading, setVersionListLoading] = useState(false)
  const [versionDetail, setVersionDetail] = useState<Record<string, unknown> | null>(null)
  const [versionDetailLoading, setVersionDetailLoading] = useState(false)
  const [rollbackConfirmVersionId, setRollbackConfirmVersionId] = useState<string | null>(null)
  const [rollbackLoading, setRollbackLoading] = useState(false)
  const [versionError, setVersionError] = useState<string | null>(null)

  // ── Phase 6.7: Version metadata edit state ────────────────
  const [editingVersionMeta, setEditingVersionMeta] = useState<{
    versionId: string
    label: string
    note: string
  } | null>(null)
  const [versionMetaSaving, setVersionMetaSaving] = useState(false)

  // ── Phase 6.7: Version compare state ──────────────────────
  const [compareMode, setCompareMode] = useState(false)
  const [compareFrom, setCompareFrom] = useState<string | null>(null)
  const [compareTo, setCompareTo] = useState<string | null>(null)
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  // ── Phase 6.8: Audit log state ────────────────────────────
  const [showAuditLog, setShowAuditLog] = useState(false)
  const [auditTemplateId, setAuditTemplateId] = useState<string | null>(null)
  const [auditEvents, setAuditEvents] = useState<Array<{
    event_id: string
    timestamp: string
    template_id: string
    event_type: string
    summary: string
    details: Record<string, unknown>
  }> | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditFilter, setAuditFilter] = useState<string>("")
  const [pinLoading, setPinLoading] = useState<string | null>(null)

  // ── Phase 6.9: Audit storage state ─────────────────────────
  const [auditStorage, setAuditStorage] = useState<{
    file_count: number
    total_bytes: number
    total_size_human: string
    earliest_event: string | null
    latest_event: string | null
  } | null>(null)
  const [auditStorageLoading, setAuditStorageLoading] = useState(false)
  const [cleanupPreview, setCleanupPreview] = useState<{
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
  } | null>(null)
  const [cleanupLoading, setCleanupLoading] = useState(false)

  /** Save current draft to localStorage (debounced) */
  const saveDraftToStorage = useCallback((draft: GraphTemplateDraft) => {
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
    draftSaveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft))
      } catch { /* quota exceeded — silently ignore */ }
    }, 500)
  }, [])

  /** Clear saved draft from localStorage */
  const clearDraftStorage = useCallback(() => {
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
    try { localStorage.removeItem(DRAFT_STORAGE_KEY) } catch { /* ignore */ }
  }, [])

  /** Auto-save draft whenever createDraft changes while form is open */
  useEffect(() => {
    if (showCreateForm && !suppressDraftSaveRef.current) {
      saveDraftToStorage(createDraft)
    }
  }, [createDraft, showCreateForm, saveDraftToStorage])

  /** Restore saved draft */
  const restoreDraft = () => {
    if (pendingRestoreDraft) {
      suppressDraftSaveRef.current = true
      setCreateDraft(pendingRestoreDraft)
      setShowCreateForm(true)
      setEditingTemplateId(null)
      setCreateFormError(null)
      setPendingRestoreDraft(null)
      // Re-enable save after the effect cycle
      requestAnimationFrame(() => { suppressDraftSaveRef.current = false })
    }
  }

  /** Discard saved draft */
  const discardDraft = () => {
    clearDraftStorage()
    setPendingRestoreDraft(null)
  }

  /** Export current draft as JSON file download */
  const exportDraftJson = () => {
    const blob = new Blob([JSON.stringify(createDraft, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `graph-template-${createDraft.name.trim().replace(/[^a-zA-Z0-9一-鿿_-]/g, "_") || "draft"}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  /** Import JSON file via file input */
  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportError(null)
    if (file.size > 1024 * 1024) {
      setImportError("文件过大：JSON 文件不能超过 1 MB")
      e.target.value = ""
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string)
        const result = validateGraphTemplateDraft(data)
        if (!result.valid) {
          setImportError(result.error)
          return
        }
        // Import success — enter "create" mode with imported data (no template_id)
        suppressDraftSaveRef.current = true
        setCreateDraft(result.draft)
        setEditingTemplateId(null)
        setShowCreateForm(true)
        setCreateFormError(null)
        saveDraftToStorage(result.draft)
        requestAnimationFrame(() => { suppressDraftSaveRef.current = false })
      } catch {
        setImportError("JSON 解析失败：文件内容不是合法 JSON")
      } finally {
        // Reset file input so the same file can be re-selected
        if (fileInputRef.current) fileInputRef.current.value = ""
      }
    }
    reader.onerror = () => {
      setImportError("文件读取失败")
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
    reader.readAsText(file)
  }

  // 时间本地化：ISO → 中文本地时间
  const formatLocalTime = (iso: string): string => {
    if (!iso) return "时间未知"
    try {
      const d = new Date(iso)
      if (isNaN(d.getTime())) return "时间未知"
      const y = d.getFullYear()
      const m = d.getMonth() + 1
      const day = d.getDate()
      const h = d.getHours().toString().padStart(2, "0")
      const min = d.getMinutes().toString().padStart(2, "0")
      return `${y}/${m}/${day} ${h}:${min}`
    } catch {
      return "时间未知"
    }
  }

  // 摘要兜底：summary → goal 前 60 字 → "暂无摘要"
  const getSummaryFallback = (task: { summary?: string; goal?: string }): string => {
    if (task.summary?.trim()) return task.summary.trim()
    if (task.goal?.trim()) {
      const t = task.goal.trim()
      return t.length > 60 ? t.slice(0, 60) + "…" : t
    }
    return "暂无摘要"
  }

  // 本地搜索过滤 + 排序（不修改原数组）
  const visibleLiteHistory = (() => {
    const q = liteHistoryQuery.trim().toLowerCase()
    const filtered = q
      ? liteHistory.filter((t) => {
          const fields = [t.task_id, t.goal, t.artifact_type, t.summary, t.source_page, t.agent_id, t.execution_mode].filter(Boolean) as string[]
          return fields.some((f) => f.toLowerCase().includes(q))
        })
      : liteHistory

    const sorted = [...filtered]
    if (liteHistorySort === "newest" || liteHistorySort === "oldest") {
      sorted.sort((a, b) => {
        const da = a.created_at ? new Date(a.created_at).getTime() : NaN
        const db = b.created_at ? new Date(b.created_at).getTime() : NaN
        const aInvalid = isNaN(da)
        const bInvalid = isNaN(db)
        if (aInvalid && bInvalid) return 0
        if (aInvalid) return 1
        if (bInvalid) return -1
        return liteHistorySort === "newest" ? db - da : da - db
      })
    } else if (liteHistorySort === "task_id") {
      sorted.sort((a, b) => (a.task_id || "").localeCompare(b.task_id || ""))
    }

    return sorted
  })()

  const copyHistoryGoal = async (taskId: string, goalText: string) => {
    const text = goalText.trim()
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopiedHistoryGoalId(taskId)
    setTimeout(() => setCopiedHistoryGoalId(null), 1600)
  }
  const [liteHistoryLoading, setLiteHistoryLoading] = useState(false)

  const modules = currentMission?.modules || []
  const activeResult = modules.find((m) => m.module_id === activeModule) || null
  const completedCount = modules.filter((m) => m.status === "done").length
  const failedCount = modules.filter((m) => m.status === "failed").length
  const skippedCount = modules.filter((m) => m.status === "skipped").length

  // 加载历史 missions
  const loadRecentMissions = async () => {
    try {
      const data = await api.listMissions(10)
      setRecentMissions(data.missions || [])
    } catch (error) {
      console.error("Load recent missions failed:", error)
    }
  }

  // 加载 Boss Lite 历史记录
  const loadLiteHistory = async (limitOverride?: number) => {
    const effectiveLimit = limitOverride ?? liteHistoryLimit
    setLiteHistoryLoading(true)
    try {
      const data = await api.listMiniDeliveryTasks({ agent_id: "boss", limit: effectiveLimit })
      const hidden = getHiddenIds()
      setLiteHistory((data.tasks || []).filter((t: { task_id: string }) => !hidden.includes(t.task_id)))
      setLiteHistoryHasMore(data.has_more ?? false)
    } catch (error) {
      console.error("Load lite history failed:", error)
      setLiteHistory([])
      setLiteHistoryHasMore(false)
    } finally {
      setLiteHistoryLoading(false)
    }
  }

  // 加载更多历史记录
  const loadMoreLiteHistory = async () => {
    const nextLimit = liteHistoryLimit + LITE_HISTORY_STEP
    setLiteHistoryLimit(nextLimit)
    await loadLiteHistory(nextLimit)
  }

  // 加载 Graph Templates
  const loadGraphTemplates = async () => {
    setGraphTemplatesLoading(true)
    setGraphTemplatesError(null)
    try {
      const data = await api.listBossGraphTemplates()
      setGraphTemplates(data.templates || [])
    } catch (error) {
      console.error("Load graph templates failed:", error)
      setGraphTemplatesError(error instanceof Error ? error.message : "加载模板失败")
      setGraphTemplates([])
    } finally {
      setGraphTemplatesLoading(false)
    }
  }

  // 按模板执行
  const executeGraphTemplate = async (template: GraphTemplate) => {
    const effectiveGoal = goal.trim() || template.goal_hint.trim()
    if (!effectiveGoal) {
      setMissionError("请输入目标或选择有 goal_hint 的模板")
      return
    }
    if (graphTemplateExecutingId) return

    setMissionError(null)
    setGraphTemplateExecutingId(template.template_id)
    setGraphTemplateResult(null)
    try {
      const result = await api.executeBossGraphTemplate(template.template_id, {
        goal: effectiveGoal,
        save_to_delivery: true,
      })
      setGraphTemplateResult(result as unknown as Record<string, unknown>)
      loadLiteHistory()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "执行失败"
      console.error("Execute graph template failed:", error)
      setMissionError(`按模板执行失败: ${errorMsg}`)
    } finally {
      setGraphTemplateExecutingId(null)
    }
  }

  // 删除 Graph Template
  const deleteGraphTemplate = async (templateId: string) => {
    if (!window.confirm("确定删除此模板？")) return
    try {
      await api.deleteBossGraphTemplate(templateId)
      setGraphTemplates((prev) => prev.filter((t) => t.template_id !== templateId))
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "删除失败"
      console.error("Delete graph template failed:", error)
      setMissionError(`删除模板失败: ${errorMsg}`)
    }
  }

  // ── Phase 6.6: Version History functions ──────────────────

  const loadVersionList = async (templateId: string) => {
    setVersionListTemplateId(templateId)
    setVersionListLoading(true)
    setVersionDetail(null)
    setVersionError(null)
    setEditingVersionMeta(null)
    setCompareMode(false)
    setCompareFrom(null)
    setCompareTo(null)
    setCompareResult(null)
    try {
      const data = await api.listBossGraphTemplateVersions(templateId)
      setVersionList(data.versions || [])
    } catch (error) {
      console.error("Load versions failed:", error)
      setVersionList(null)
      setVersionError(error instanceof Error ? error.message : "版本历史加载失败")
    } finally {
      setVersionListLoading(false)
    }
  }

  const loadVersionDetail = async (templateId: string, versionId: string) => {
    setVersionDetailLoading(true)
    setVersionError(null)
    try {
      const data = await api.getBossGraphTemplateVersion(templateId, versionId)
      setVersionDetail(data.version as unknown as Record<string, unknown>)
    } catch (error) {
      console.error("Load version detail failed:", error)
      setVersionDetail(null)
      setVersionError(error instanceof Error ? error.message : "版本详情加载失败")
    } finally {
      setVersionDetailLoading(false)
    }
  }

  const rollbackToVersion = async () => {
    if (!versionListTemplateId || !rollbackConfirmVersionId || rollbackLoading) return
    setRollbackLoading(true)
    setVersionError(null)
    try {
      const data = await api.restoreBossGraphTemplateVersion(versionListTemplateId, rollbackConfirmVersionId)
      setRollbackConfirmVersionId(null)
      setVersionDetail(null)
      setEditingTemplateId(data.template.template_id)
      setCreateDraft({
        name: data.template.name,
        description: data.template.description,
        goal_hint: data.template.goal_hint,
        nodes: data.template.nodes.map((node) => ({ ...node })),
        edges: data.template.edges.map((edge) => ({ ...edge })),
      })
      setCreateFormError(null)
      setShowCreateForm(true)
      await Promise.all([
        loadVersionList(versionListTemplateId),
        loadGraphTemplates(),
      ])
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "回滚失败"
      console.error("Rollback failed:", error)
      setRollbackConfirmVersionId(null)
      setVersionError(errorMsg)
    } finally {
      setRollbackLoading(false)
    }
  }

  // ── Phase 6.7: Version metadata edit ─────────────────────

  const saveVersionMetadata = async () => {
    if (!versionListTemplateId || !editingVersionMeta || versionMetaSaving) return
    setVersionMetaSaving(true)
    setVersionError(null)
    try {
      await api.updateBossGraphTemplateVersionMetadata(
        versionListTemplateId,
        editingVersionMeta.versionId,
        { label: editingVersionMeta.label, note: editingVersionMeta.note },
      )
      setEditingVersionMeta(null)
      await loadVersionList(versionListTemplateId)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "保存元数据失败"
      console.error("Save version metadata failed:", error)
      setVersionError(errorMsg)
    } finally {
      setVersionMetaSaving(false)
    }
  }

  // ── Phase 6.7: Version compare ───────────────────────────

  const runVersionCompare = async () => {
    if (!versionListTemplateId || !compareFrom || !compareTo || compareLoading) return
    setCompareLoading(true)
    setVersionError(null)
    setCompareResult(null)
    try {
      const data = await api.compareBossGraphTemplateVersions(
        versionListTemplateId,
        compareFrom,
        compareTo,
      )
      setCompareResult(data.diff as unknown as Record<string, unknown>)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "版本对比失败"
      console.error("Version compare failed:", error)
      setVersionError(errorMsg)
    } finally {
      setCompareLoading(false)
    }
  }

  // ── Phase 6.8: Audit log ─────────────────────────────────

  const loadAuditLog = async (templateId: string, eventType?: string) => {
    setAuditTemplateId(templateId)
    setAuditLoading(true)
    setAuditEvents(null)
    setShowAuditLog(true)
    try {
      const data = await api.listBossGraphTemplateAudit(templateId, {
        eventType: eventType || undefined,
        limit: 200,
      })
      setAuditEvents(data.events || [])
    } catch (error) {
      console.error("Load audit log failed:", error)
      setAuditEvents([])
    } finally {
      setAuditLoading(false)
    }
  }

  // ── Phase 6.8: Version pin/unpin ─────────────────────────

  const togglePin = async (templateId: string, versionId: string, currentlyPinned: boolean) => {
    setPinLoading(versionId)
    setVersionError(null)
    try {
      if (currentlyPinned) {
        await api.unpinBossGraphTemplateVersion(templateId, versionId)
      } else {
        await api.pinBossGraphTemplateVersion(templateId, versionId)
      }
      await loadVersionList(templateId)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "操作失败"
      console.error("Pin/unpin failed:", error)
      setVersionError(errorMsg)
    } finally {
      setPinLoading(null)
    }
  }

  // ── Phase 6.9: Audit storage ───────────────────────────────

  const loadAuditStorage = async () => {
    setAuditStorageLoading(true)
    try {
      const data = await api.getBossAuditStorage()
      setAuditStorage(data.storage || null)
    } catch (error) {
      console.error("Load audit storage failed:", error)
      setAuditStorage(null)
    } finally {
      setAuditStorageLoading(false)
    }
  }

  const previewCleanup = async () => {
    setCleanupLoading(true)
    setCleanupPreview(null)
    try {
      const data = await api.cleanupBossAuditLogs({ retentionDays: 30, dryRun: true })
      setCleanupPreview(data.cleanup || null)
    } catch (error) {
      console.error("Preview cleanup failed:", error)
      setCleanupPreview(null)
    } finally {
      setCleanupLoading(false)
    }
  }

  // 创建模板 — 前端校验
  const validateDraft = (draft: GraphTemplateDraft): string[] => {
    const errors: string[] = []
    if (!draft.name.trim() || draft.name.trim().length < 2) errors.push("模板名称不能为空且至少 2 个字符")
    if (draft.nodes.length < 1) errors.push("至少需要 1 个节点")
    errors.push(...validateDag(draft.nodes, draft.edges).map((error) => error.message))
    return errors
  }

  // 创建/更新模板 — 保存
  const saveGraphTemplate = async () => {
    setCreateFormError(null)
    const errors = validateDraft(createDraft)
    if (errors.length > 0) {
      setCreateFormError(errors.join("\n"))
      return
    }
    setCreateSubmitting(true)
    try {
      const payload = {
        name: createDraft.name.trim(),
        description: createDraft.description.trim() || undefined,
        goal_hint: createDraft.goal_hint.trim() || undefined,
        nodes: createDraft.nodes.map((n) => ({
          id: n.id.trim(),
          agent_id: n.agent_id.trim(),
          task_type: n.task_type.trim() || undefined,
          title: n.title.trim() || undefined,
          prompt: n.prompt.trim() || undefined,
        })),
        edges: createDraft.edges.map((e) => ({
          from_node: e.from_node.trim(),
          to_node: e.to_node.trim(),
          handoff_type: e.handoff_type.trim() || undefined,
        })),
      }
      if (editingTemplateId) {
        await api.updateBossGraphTemplate(editingTemplateId, payload)
        setEditingTemplateId(null)
      } else {
        await api.createBossGraphTemplate({
          ...payload,
          source_template_id: cloneSourceId || undefined,
        })
      }
      setShowCreateForm(false)
      setCreateDraft(DEFAULT_DRAFT)
      setCreateFormError(null)
      setCloneSourceId(null)
      clearDraftStorage()
      loadGraphTemplates()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "保存失败"
      console.error("Save graph template failed:", error)
      setCreateFormError(errorMsg)
    } finally {
      setCreateSubmitting(false)
    }
  }

  // 克隆模板：将已有模板内容填入创建表单
  const cloneGraphTemplate = (tpl: GraphTemplate) => {
    setEditingTemplateId(null)
    setCloneSourceId(tpl.template_id)
    setCreateDraft({
      name: `${tpl.name} 副本`,
      description: tpl.description,
      goal_hint: tpl.goal_hint,
      nodes: tpl.nodes.map((n) => ({ ...n })),
      edges: tpl.edges.map((e) => ({ ...e })),
    })
    setCreateFormError(null)
    setShowCreateForm(true)
  }

  // 编辑模板：将已有模板内容填入创建表单，进入编辑模式
  const editGraphTemplate = (tpl: GraphTemplate) => {
    setEditingTemplateId(tpl.template_id)
    setCloneSourceId(null)
    setCreateDraft({
      name: tpl.name,
      description: tpl.description,
      goal_hint: tpl.goal_hint,
      nodes: tpl.nodes.map((n) => ({ ...n })),
      edges: tpl.edges.map((e) => ({ ...e })),
    })
    setCreateFormError(null)
    setShowCreateForm(true)
  }

  useEffect(() => {
    loadRecentMissions()
    loadTemplates()
    loadLiteHistory()
    loadGraphTemplates()

    // Check for mission to load from sessionStorage
    const loadMissionId = sessionStorage.getItem("load_mission_id")
    if (loadMissionId) {
      sessionStorage.removeItem("load_mission_id")
      loadMission(loadMissionId)
    }

    // Check for template to load from sessionStorage
    const tplData = sessionStorage.getItem("boss_selected_template")
    if (tplData) {
      sessionStorage.removeItem("boss_selected_template")
      try {
        const tpl = JSON.parse(tplData)
        setSelectedTemplate(tpl)
        setGoal(tpl.default_goal)
        setEnabledModules(tpl.default_modules)
      } catch {
        // ignore
      }
    }
  }, [])

  const loadTemplates = async () => {
    try {
      const data = await api.getTemplates()
      setTemplates(data.templates || [])
    } catch (error) {
      console.error("Load templates failed:", error)
    }
  }

  // Boss Lite: execute all agents
  const executeBossLite = async () => {
    const trimmed = goal.trim()
    if (!trimmed || isRunning) return

    setIsRunning(true)
    setMissionError(null)
    setLiteResult(null)
    setLiteProgressPhase(0)

    try {
      const result = await api.bossLiteExecute(trimmed)
      setLiteResult(result)
      if (result.results.length > 0) {
        setLiteActiveAgent(result.results[0].agent_id)
      }
      // 执行成功后刷新历史列表
      loadLiteHistory()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "执行失败"
      console.error("Boss Lite execute failed:", error)
      setMissionError(`Boss Lite 执行失败: ${errorMsg}`)
    } finally {
      setIsRunning(false)
    }
  }

  // Boss Lite: reset to start new
  const resetLite = () => {
    setLiteResult(null)
    setLiteActiveAgent("")
    setLiteProgressPhase(0)
    setGoal("")
  }

  // 跳转到 Delivery 页面查看交付物
  const viewDelivery = (taskId: string) => {
    window.location.href = `/app?page=delivery&taskId=${encodeURIComponent(taskId)}`
  }

  // Boss Lite progress phase auto-cycle
  useEffect(() => {
    if (!isRunning || mode !== "boss-lite") return
    const timer = setInterval(() => {
      setLiteProgressPhase((prev) => (prev < 3 ? prev + 1 : prev))
    }, 4000)
    return () => clearInterval(timer)
  }, [isRunning, mode])

  // 加载事件日志
  const loadEvents = async (missionId: string) => {
    try {
      const data = await api.getMissionEvents(missionId)
      setEvents(data.events || [])
    } catch {
      setEvents([])
    }
  }

  // Phase 6.15: 停止轮询
  const stopMissionPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    pollFailCountRef.current = 0
  }, [])

  // Phase 6.15: 启动轮询（每 1.5s 刷新 mission + events）
  const startMissionPolling = useCallback((missionId: string) => {
    stopMissionPolling()
    pollFailCountRef.current = 0
    pollTimerRef.current = setInterval(async () => {
      try {
        const [mission, eventsData] = await Promise.all([
          api.getMission(missionId),
          api.getMissionEvents(missionId),
        ])
        pollFailCountRef.current = 0
        setCurrentMission({ ...mission, modules: mission.modules || [] })
        setEvents(eventsData.events || [])
        // 自动展开运行日志
        if (eventsData.events?.length > 0) {
          setShowEvents(true)
        }
        // 自动跳转到 running 模块
        const runningMod = mission.modules?.find((m: ModuleResult) => m.status === "running")
        if (runningMod) setActiveModule(runningMod.module_id)

        // terminal → 停止轮询
        const terminalStatuses = ["ready_for_review", "partial", "failed", "interrupted", "done"]
        if (terminalStatuses.includes(mission.status)) {
          stopMissionPolling()
          setIsRunning(false)
          loadRecentMissions()
        }
      } catch {
        pollFailCountRef.current += 1
        console.warn(`Poll failed (${pollFailCountRef.current})`)
        if (pollFailCountRef.current >= 5) {
          stopMissionPolling()
          setIsRunning(false)
        }
      }
    }, 1500)
  }, [stopMissionPolling])

  // Phase 6.15: 组件卸载时清理轮询
  useEffect(() => {
    return () => { stopMissionPolling() }
  }, [stopMissionPolling])

  // v2: 两阶段流程 — 阶段1: 只创建计划
  const createPlan = async () => {
    const trimmed = goal.trim()
    if (!trimmed || isRunning) return

    setIsRunning(true)
    setMissionError(null)
    setActiveModule("strategy")

    try {
      let mission
      // Phase 6.19: 有 input_fields 的模板，使用 from-template 端点
      if (selectedTemplate?.input_fields && selectedTemplate.input_fields.length > 0) {
        mission = await api.createMissionFromTemplate(selectedTemplate.id, {
          goal: trimmed,
          enabledModules: enabledModules,
          inputs: inputValues,
          allowBrowserAutomation,
        })
      } else {
        mission = await api.createMission(trimmed, false, enabledModules, allowBrowserAutomation)
      }
      setCurrentMission({
        ...mission,
        modules: mission.modules || [],
      })
      setShowInputForm(false)
      setShowTemplates(false)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "创建计划失败"
      console.error("Create plan failed:", error)
      if (errorMsg.includes("429") || errorMsg.includes("rate")) {
        setMissionError("请求太频繁，请稍后再试。")
      } else if (errorMsg.includes("400")) {
        setMissionError(`参数错误: ${errorMsg}`)
      } else {
        setMissionError(`创建计划失败: ${errorMsg}`)
      }
    } finally {
      setIsRunning(false)
    }
  }

  // v2: 两阶段流程 — 阶段2: 确认执行（Phase 6.15: fire-and-poll 模式）
  const confirmRun = async () => {
    if (!currentMission || isRunning) return

    stopMissionPolling()
    setIsRunning(true)
    setMissionError(null)
    // 立即显示 running 状态
    setCurrentMission(prev => prev ? { ...prev, status: "running" } : prev)

    const missionId = currentMission.mission_id
    startMissionPolling(missionId)

    try {
      await api.runMission(missionId, allowBrowserAutomation)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "执行失败"
      console.error("runMission failed:", err)
      setMissionError(`执行失败: ${errorMsg}`)
    } finally {
      // 最终刷新一次（不覆盖轮询已拿到的较新数据）
      try {
        const [finalMission, finalEvents] = await Promise.all([
          api.getMission(missionId),
          api.getMissionEvents(missionId),
        ])
        setCurrentMission({ ...finalMission, modules: finalMission.modules || [] })
        setEvents(finalEvents.events || [])
      } catch { /* 静默 */ }
      stopMissionPolling()
      setIsRunning(false)
      loadRecentMissions()
    }
  }

  // 用户接受结果
  const acceptMission = async () => {
    if (!currentMission || isRunning) return
    setIsRunning(true)
    try {
      const updated = await api.acceptMission(currentMission.mission_id)
      setCurrentMission({
        ...updated,
        modules: updated.modules || [],
      })
      loadRecentMissions()
    } catch (error) {
      console.error("Accept mission failed:", error)
      setMissionError(`接受结果失败: ${error instanceof Error ? error.message : "未知错误"}`)
    } finally {
      setIsRunning(false)
    }
  }

  // 重跑单个模块
  const rerunModule = async (moduleId: string, forceAllowBrowser = false) => {
    if (!currentMission || isRunning) return

    const shouldAllow = forceAllowBrowser || allowBrowserAutomation
    setIsRunning(true)
    try {
      const updated = await api.runMissionModule(currentMission.mission_id, moduleId, shouldAllow)
      setCurrentMission({
        ...updated,
        modules: updated.modules || [],
      })
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "重跑失败"
      console.error("Module rerun failed:", error)
      setMissionError(`重跑模块失败: ${errorMsg}`)
    } finally {
      setIsRunning(false)
    }
  }

  // 加载历史 mission
  const loadMission = async (missionId: string) => {
    try {
      const mission = await api.getMission(missionId)
      const safeMission = { ...mission, modules: mission.modules || [] }
      setCurrentMission(safeMission)
      setGoal(mission.goal || "")
      loadEvents(missionId)
      // 从 mission 恢复 enabled_modules
      const activeIds = safeMission.modules.filter((m) => m.status !== "skipped").map((m) => m.module_id)
      setEnabledModules(activeIds.length > 0 ? activeIds : [...MODULE_IDS])
      setActiveModule("strategy")
      setShowHistory(false)
    } catch (error) {
      console.error("Load mission failed:", error)
      setMissionError(`加载历史任务失败: ${error instanceof Error ? error.message : "未知错误"}`)
    }
  }

  // 导出
  const handleExport = async (format: "json" | "markdown") => {
    if (!currentMission) return
    try {
      await api.exportMission(currentMission.mission_id, format)
      // 显示成功反馈
      setExportToast(format)
      setTimeout(() => setExportToast(null), 3000)
    } catch (error) {
      console.error("Export failed:", error)
      setMissionError(`导出失败: ${error instanceof Error ? error.message : "未知错误"}`)
    }
  }

  // 模块 checkbox 切换
  const toggleModule = (moduleId: string) => {
    setEnabledModules((prev) => {
      if (prev.includes(moduleId)) {
        return prev.filter((m) => m !== moduleId)
      }
      return [...prev, moduleId]
    })
  }

  const statusBadge = (status: string) => {
    if (status === "running") return <Badge variant="info">执行中</Badge>
    if (status === "done") return <Badge variant="success">已完成</Badge>
    if (status === "ready_for_review") return <Badge variant="success">待审核</Badge>
    if (status === "partial") return <Badge variant="warning">部分结果</Badge>
    if (status === "interrupted") return <Badge variant="warning">已中断</Badge>
    if (status === "pending_review") return <Badge variant="info">待确认</Badge>
    if (status === "failed") return <Badge variant="destructive">需处理</Badge>
    if (status === "blocked") return <Badge variant="warning">需授权</Badge>
    if (status === "skipped") return <Badge variant="secondary">已跳过</Badge>
    return <Badge variant="secondary">待执行</Badge>
  }

  // v2: Mission 状态文案映射
  const missionStatusText = (status: string) => {
    const map: Record<string, string> = {
      pending_review: "计划已生成，等待确认执行",
      pending: "计划已生成，等待确认执行",
      running: "正在执行模块中...",
      ready_for_review: "已生成结果，等待人工审核",
      partial: "部分模块有结果，等待人工处理",
      interrupted: "执行中断，可重跑未完成模块",
      done: "用户已确认完成",
      failed: "无有效结果",
    }
    return map[status] || status
  }

  /** 从历史 task 中提取复盘 badge 列表（只用 API 实际返回的字段） */
  const getTaskOutcomeBadges = (task: {
    artifact_type?: string
    source_page?: string
    agent_id?: string
    succeeded?: number
    failed?: number
    total?: number
    total_duration_ms?: number
    handoff_enabled?: boolean
    execution_mode?: string
  }): Array<{ label: string; variant: "outline" | "secondary" | "success" | "warning" | "info" }> => {
    const badges: Array<{ label: string; variant: "outline" | "secondary" | "success" | "warning" | "info" }> = []
    if (task.artifact_type) {
      badges.push({ label: task.artifact_type, variant: "outline" })
    }
    // Boss Lite 复盘 badge
    if (task.succeeded != null && task.total != null && task.total > 0) {
      badges.push({ label: `${task.succeeded}/${task.total} Agent 成功`, variant: task.failed && task.failed > 0 ? "warning" : "success" })
    }
    if (task.failed != null && task.failed > 0) {
      badges.push({ label: `失败 ${task.failed}`, variant: "warning" })
    }
    if (task.total_duration_ms != null && task.total_duration_ms > 0) {
      const sec = task.total_duration_ms / 1000
      badges.push({ label: `耗时 ${sec < 1 ? `${task.total_duration_ms}ms` : `${sec.toFixed(1)}s`}`, variant: "outline" })
    }
    if (task.handoff_enabled) {
      badges.push({ label: "Handoff", variant: "info" })
    }
    if (task.execution_mode) {
      badges.push({ label: task.execution_mode, variant: "secondary" })
    }
    if (task.source_page) {
      badges.push({ label: `来源: ${task.source_page}`, variant: "secondary" })
    }
    return badges
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="inline-block px-3 py-1 rounded-full border border-[#E5E5E5] text-[11px] text-[#8A8A8A] tracking-wider mb-3">
              Boss Command Center
            </span>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[#0B0B0B]">
              老板运营指挥台
            </h1>
            <p className="text-sm text-[#8A8A8A] mt-2">
              输入一个业务目标，AI 自动拆解为多部门协同执行方案。
            </p>
            {/* Mode Toggle */}
            <div className="flex items-center gap-2 mt-4">
              <button
                type="button"
                onClick={() => setMode("boss-lite")}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  mode === "boss-lite"
                    ? "bg-[#0B0B0B] text-white"
                    : "bg-[#F4F3EF] text-[#8A8A8A] hover:text-[#0B0B0B]"
                )}
              >
                <Zap className="inline-block h-3.5 w-3.5 mr-1.5" />
                Boss Lite
              </button>
              <button
                type="button"
                onClick={() => setMode("command-center")}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  mode === "command-center"
                    ? "bg-[#0B0B0B] text-white"
                    : "bg-[#F4F3EF] text-[#8A8A8A] hover:text-[#0B0B0B]"
                )}
              >
                <Target className="inline-block h-3.5 w-3.5 mr-1.5" />
                指挥台
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {mode === "command-center" && modules.length > 0 && (
              <Badge variant={failedCount > 0 ? "warning" : completedCount === modules.length - skippedCount ? "success" : "secondary"}>
                {completedCount}/{modules.length - skippedCount} 完成
              </Badge>
            )}
            {mode === "command-center" && currentMission && (
              <Button variant="outline" size="sm" onClick={() => handleExport("markdown")} className="gap-1">
                <Download className="h-3.5 w-3.5" />
                导出
              </Button>
            )}

            {/* Boss Lite header actions */}
            {mode === "boss-lite" && liteResult && (
              <>
                {liteResult.delivery_task_id && (
                  <Badge variant="outline">
                    交付物: {liteResult.delivery_task_id}
                  </Badge>
                )}
                <Button variant="outline" size="sm" onClick={resetLite} className="gap-1">
                  <RotateCcw className="h-3.5 w-3.5" />
                  新任务
                </Button>
              </>
            )}

            {/* Metrics 小面板 */}
            {currentMission?.metrics && (currentMission.status !== "pending" && currentMission.status !== "pending_review" && currentMission.status !== "running") && (
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  完成率 {Math.round(currentMission.metrics.completion_rate * 100)}%
                </Badge>
                <Badge variant="outline">
                  {currentMission.metrics.succeeded_modules}/{currentMission.metrics.total_modules} 成功
                </Badge>
                {currentMission.metrics.failed_modules > 0 && (
                  <Badge variant="destructive">{currentMission.metrics.failed_modules} 失败</Badge>
                )}
                {currentMission.metrics.skipped_modules > 0 && (
                  <Badge variant="secondary">{currentMission.metrics.skipped_modules} 跳过</Badge>
                )}
                {currentMission.metrics.warning_count > 0 && (
                  <Badge variant="warning">{currentMission.metrics.warning_count} 警告</Badge>
                )}
                {currentMission.metrics.duration_ms > 0 && (
                  <Badge variant="outline">
                    {currentMission.metrics.duration_ms < 1000
                      ? `${currentMission.metrics.duration_ms}ms`
                      : `${(currentMission.metrics.duration_ms / 1000).toFixed(1)}s`}
                  </Badge>
                )}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowHistory(!showHistory)}
              className="gap-1"
            >
              <History className="h-3.5 w-3.5" />
              历史
            </Button>
          </div>
        </div>
      </motion.div>

      {/* 全局错误横幅 */}
      {missionError && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-2xl border border-red/30 bg-red/5"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
            <div className="flex-1 min-w-0">
              <span className="font-medium text-sm text-red-500">操作失败</span>
              <p className="mt-1 text-sm text-red-500">{missionError}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMissionError(null)}
              className="h-6 px-2 text-xs text-red-500 hover:text-red-700"
            >
              关闭
            </Button>
          </div>
        </motion.div>
      )}

      {/* 历史面板 — only in command-center mode */}
      {mode === "command-center" && showHistory && (
        <div className="p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <h3 className="mb-3 font-medium text-sm text-[#8A8A8A] tracking-wider uppercase">最近的 Mission</h3>
          {recentMissions.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无历史记录</p>
          ) : (
            <div className="space-y-2">
              {recentMissions.map((m) => (
                <button
                  key={m.mission_id}
                  type="button"
                  onClick={() => loadMission(m.mission_id)}
                  className="w-full rounded-lg border border-border p-3 text-left transition hover:border-primary/40 hover:bg-accent/50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm">{m.goal}</span>
                    {statusBadge(m.status)}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{m.created_at}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Goal Input Card */}
      <motion.div
        id="boss-goal-input"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-[#0B0B0B]">
              今天要推进什么业务目标？
            </div>
            <Textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="例如：帮我调研 AI 陪伴产品的市场机会，并生成第一版运营行动包。"
              className="min-h-[120px] text-base bg-[#F4F3EF] border-[#E5E5E5] rounded-xl"
              data-testid="boss-goal-input"
            />
            <div className="flex flex-wrap gap-2">
              {examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setGoal(example)}
                  className="rounded-full border border-[#E5E5E5] px-3 py-1.5 text-xs text-[#8A8A8A] transition hover:border-[#B5B5B5] hover:text-[#0B0B0B]"
                >
                  {example}
                </button>
              ))}
            </div>

            {/* Boss Lite 常用作战模板 */}
            {mode === "boss-lite" && !liteResult && !isRunning && (
              <div className="pt-1">
                <p className="text-xs text-[#B5B5B5] mb-2.5">
                  选择模板会自动填入目标，你也可以继续编辑。
                </p>
                <div className="flex flex-wrap gap-2">
                  {liteTemplates.map((tpl) => {
                    const Icon = tpl.icon
                    return (
                      <button
                        key={tpl.id}
                        type="button"
                        onClick={() => {
                          setGoal(tpl.goal)
                          setLiteResult(null)
                        }}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[#E5E5E5] bg-[#F9F9F7] px-3.5 py-1.5 text-xs font-medium text-[#5A5A5A] transition-all hover:border-[#0B0B0B] hover:text-[#0B0B0B] hover:bg-white"
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {tpl.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 模块选择 + 模板入口 — only in command-center mode */}
            {mode === "command-center" && !currentMission && (
              <div className="space-y-3 pt-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-xs font-medium text-muted-foreground">执行模块：</span>
                  {MODULE_IDS.map((id) => (
                    <label
                      key={id}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={enabledModules.includes(id)}
                        onChange={() => toggleModule(id)}
                        className="h-3.5 w-3.5 rounded border-border accent-primary"
                      />
                      {id === "strategy" ? "策略" : id === "market" ? "上下文" : id === "marketing" ? "沟通" : id === "landing" ? "交付物" : "执行"}
                    </label>
                  ))}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setShowTemplates(!showTemplates)}
                  className="gap-1"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {selectedTemplate ? `已选模板：${selectedTemplate.name}` : "从模板创建"}
                </Button>
              </div>
            )}

            {/* 模板选择面板 */}
            {showTemplates && !currentMission && (
              <div className="grid gap-3 pt-2 sm:grid-cols-2 lg:grid-cols-3">
                {templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => {
                      setSelectedTemplate(tpl)
                      setGoal(tpl.default_goal)
                      setEnabledModules(tpl.default_modules)
                      if (tpl.input_fields && tpl.input_fields.length > 0) {
                        // Phase 6.19: 有 input_fields 的模板，显示表单
                        const defaults: Record<string, string> = {}
                        tpl.input_fields.forEach(f => { if (f.default) defaults[f.name] = f.default })
                        setInputValues(defaults)
                        setShowInputForm(true)
                      } else {
                        setShowInputForm(false)
                        setShowTemplates(false)
                      }
                    }}
                    className={cn(
                      "rounded-lg border p-3 text-left transition-all",
                      selectedTemplate?.id === tpl.id
                        ? "border-primary/50 bg-primary/10"
                        : "border-border hover:border-primary/30 hover:bg-accent/50"
                    )}
                  >
                    <h4 className="text-sm font-medium">{tpl.name}</h4>
                    <p className="mt-1 text-xs text-muted-foreground">{tpl.description}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {tpl.default_modules.map((m) => (
                        <span key={m} className="rounded bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {m}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Phase 6.19: input_fields 表单 */}
            {showInputForm && selectedTemplate?.input_fields && !currentMission && (
              <div className="rounded-xl border border-[#E5E5E5] bg-[#F9F9F8] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-[#0B0B0B]">{selectedTemplate.name} — 填写信息</h4>
                  <button
                    type="button"
                    onClick={() => { setShowInputForm(false); setSelectedTemplate(null) }}
                    className="text-xs text-[#8A8A8A] hover:text-[#0B0B0B]"
                  >
                    取消
                  </button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {selectedTemplate.input_fields.map((field) => (
                    <div key={field.name}>
                      <label className="block text-xs font-medium text-[#0B0B0B] mb-1">
                        {field.label}
                        {field.required && <span className="text-red-500 ml-0.5">*</span>}
                      </label>
                      {field.type === "select" ? (
                        <select
                          value={inputValues[field.name] || ""}
                          onChange={(e) => setInputValues(prev => ({ ...prev, [field.name]: e.target.value }))}
                          className="w-full rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm text-[#0B0B0B] focus:border-[#0B0B0B] focus:outline-none"
                        >
                          <option value="">请选择</option>
                          {(field.options || []).map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={inputValues[field.name] || ""}
                          onChange={(e) => setInputValues(prev => ({ ...prev, [field.name]: e.target.value }))}
                          placeholder={field.placeholder || ""}
                          className="w-full rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm text-[#0B0B0B] placeholder:text-[#B5B5B5] focus:border-[#0B0B0B] focus:outline-none"
                        />
                      )}
                    </div>
                  ))}
                </div>
                {selectedTemplate.expected_sections && selectedTemplate.expected_sections.length > 0 && (
                  <div className="pt-2 border-t border-[#E5E5E5]">
                    <p className="text-xs text-[#8A8A8A] mb-1.5">将生成以下内容：</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedTemplate.expected_sections.map(s => (
                        <span key={s} className="rounded-full bg-[#E5E5E5] px-2.5 py-0.5 text-[11px] text-[#0B0B0B]">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 浏览器自动化授权 — only in command-center mode */}
          {mode === "command-center" && (
            <div className="flex items-center gap-3 rounded-xl border border-[#E5E5E5] bg-[#F4F3EF] px-4 py-2.5">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allowBrowserAutomation}
                  onChange={(e) => setAllowBrowserAutomation(e.target.checked)}
                  className="h-4 w-4 rounded border-[#D4D4D4] accent-[#0B0B0B]"
                />
                {allowBrowserAutomation ? (
                  <Shield className="h-4 w-4 text-[#4A8A5A]" />
                ) : (
                  <ShieldOff className="h-4 w-4 text-[#B5B5B5]" />
                )}
                <span className="text-sm font-medium text-[#0B0B0B]">
                  允许本次打开浏览器采集数据
                </span>
              </label>
              {allowBrowserAutomation && (
                <span className="text-xs text-[#8A8A8A]">
                  （仅本次任务生效，不会永久保存）
                </span>
              )}
            </div>
          )}

          <div className="flex items-end gap-3">
            {mode === "boss-lite" ? (
              /* Boss Lite: single execute button */
              <Button
                onClick={executeBossLite}
                disabled={!goal.trim() || isRunning}
                variant="default"
                size="lg"
                className="w-full lg:w-auto"
              >
                {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                {isRunning ? "执行中，约需1分钟..." : "一键执行"}
              </Button>
            ) : (
              /* Command Center: two-phase flow */
              !currentMission || currentMission.status === "pending_review" || currentMission.status === "pending" ? (
                <>
                  {/* 阶段1: 生成计划 */}
                  <Button
                    onClick={createPlan}
                    disabled={!goal.trim() || isRunning || enabledModules.length === 0}
                    variant="default"
                    size="lg"
                    className="w-full lg:w-auto"
                    data-testid="boss-create-plan-btn"
                  >
                    {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                    生成计划
                  </Button>
                  {/* 阶段2: 确认执行（仅在计划已创建时显示） */}
                  {currentMission && (
                    <Button
                      onClick={confirmRun}
                      disabled={isRunning}
                      variant="default"
                      size="lg"
                      className="w-full lg:w-auto bg-green hover:bg-green/90"
                      data-testid="boss-confirm-run-btn"
                    >
                      {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      确认执行
                    </Button>
                  )}
                </>
              ) : (
                <Button
                  onClick={confirmRun}
                  disabled={isRunning}
                  variant="outline"
                  size="lg"
                  className="w-full lg:w-auto"
                >
                  {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  重新执行
                </Button>
              )
            )}
          </div>
        </div>
      </motion.div>

      {/* Graph Templates — only in boss-lite mode */}
      {mode === "boss-lite" && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">Graph Templates / 协作图模板</h3>
              {graphTemplates.length > 0 && (
                <Badge variant="secondary">{graphTemplates.length}</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="default"
                size="sm"
                onClick={() => {
                  setShowCreateForm(!showCreateForm)
                  setCreateFormError(null)
                  if (!showCreateForm) {
                    setCreateDraft(DEFAULT_DRAFT)
                    setEditingTemplateId(null)
                  } else {
                    clearDraftStorage()
                  }
                }}
                className="gap-1 text-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                创建模板
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="gap-1 text-xs"
              >
                <Upload className="h-3.5 w-3.5" />
                导入 JSON
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,application/json"
                onChange={handleImportFile}
                className="hidden"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={loadGraphTemplates}
                disabled={graphTemplatesLoading}
                className="gap-1 text-[#8A8A8A] hover:text-[#0B0B0B]"
              >
                {graphTemplatesLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="h-3.5 w-3.5" />
                )}
                刷新
              </Button>
            </div>
          </div>

          {graphTemplatesError && (
            <div className="mb-4 rounded-lg border border-red/20 bg-red/5 p-3 text-sm text-red-500">
              {graphTemplatesError}
            </div>
          )}

          {importError && (
            <div className="mb-4 rounded-lg border border-red/20 bg-red/5 p-3 text-sm text-red-500">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertCircle className="h-3.5 w-3.5" />
                <span className="font-medium">导入失败</span>
              </div>
              {importError}
            </div>
          )}

          {/* 创建模板表单 */}
          {showCreateForm && (
            <div className="mb-4 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-medium text-[#0B0B0B]">{editingTemplateId ? "编辑 Graph Template" : "创建 Graph Template"}</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={exportDraftJson}
                  className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                >
                  <Download className="h-3.5 w-3.5" />
                  导出 JSON
                </Button>
              </div>

              {/* 基础字段 */}
              <div className="grid gap-3 sm:grid-cols-3 mb-4">
                <div>
                  <label className="block text-xs text-[#8A8A8A] mb-1">名称 *</label>
                  <input
                    type="text"
                    value={createDraft.name}
                    onChange={(e) => setCreateDraft({ ...createDraft, name: e.target.value })}
                    className="w-full rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                    placeholder="模板名称"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#8A8A8A] mb-1">描述</label>
                  <input
                    type="text"
                    value={createDraft.description}
                    onChange={(e) => setCreateDraft({ ...createDraft, description: e.target.value })}
                    className="w-full rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                    placeholder="模板描述"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#8A8A8A] mb-1">目标提示</label>
                  <input
                    type="text"
                    value={createDraft.goal_hint}
                    onChange={(e) => setCreateDraft({ ...createDraft, goal_hint: e.target.value })}
                    className="w-full rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                    placeholder="goal_hint"
                  />
                </div>
              </div>

              {/* DAG 编辑器 */}
              <DagEditor
                draft={createDraft}
                onChange={(draft) => {
                  setCreateDraft(draft)
                  setCreateFormError(null)
                }}
                errors={createFormError ? createFormError.split("\n") : []}
                disabled={createSubmitting}
                showCanvas
                canvasLayout={editingTemplateId ? graphTemplates.find(t => t.template_id === editingTemplateId)?.canvas_layout : undefined}
                onLayoutChange={handleCanvasLayoutChange}
              />

              {/* 操作按钮 */}
              <div className="flex items-center gap-2">
                <Button
                  variant="default"
                  size="sm"
                  onClick={saveGraphTemplate}
                  disabled={createSubmitting}
                  className="gap-1 text-xs"
                >
                  {createSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                  {createSubmitting ? "保存中..." : editingTemplateId ? "更新模板" : "保存模板"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowCreateForm(false)
                    setCreateDraft(DEFAULT_DRAFT)
                    setCreateFormError(null)
                    setEditingTemplateId(null)
                    setCloneSourceId(null)
                    clearDraftStorage()
                  }}
                  className="gap-1 text-xs"
                >
                  取消
                </Button>
              </div>
            </div>
          )}

          {graphTemplatesLoading ? (
            <div className="flex items-center gap-2 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-4 text-sm text-[#6B6B6B]">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载模板...
            </div>
          ) : graphTemplates.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B]">
              暂无模板，点击上方「创建模板」按钮创建第一个协作图模板。
            </div>
          ) : (
            <div className="space-y-3">
              {graphTemplates.map((tpl) => {
                const isExecuting = graphTemplateExecutingId === tpl.template_id
                return (
                  <div
                    key={tpl.template_id}
                    className="rounded-xl border border-[#E5E5E5] p-4 transition-all hover:border-[#B5B5B5] hover:bg-[#F9F9F7]"
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-[#0B0B0B]">{tpl.name}</span>
                          <span className="text-[10px] font-mono text-[#B5B5B5] bg-[#F4F3EF] px-1.5 py-0.5 rounded">
                            {tpl.template_id}
                          </span>
                        </div>
                        {tpl.description && (
                          <p className="text-xs text-[#8A8A8A] mb-1">{tpl.description}</p>
                        )}
                        {tpl.goal_hint && (
                          <p className="text-xs text-[#6B6B6B] line-clamp-2">
                            <span className="text-[#B5B5B5]">目标提示：</span>{tpl.goal_hint}
                          </p>
                        )}
                      </div>
                      <div className="shrink-0 flex items-center gap-1.5">
                        <Badge variant="outline">{tpl.nodes.length} 节点</Badge>
                        <Badge variant="outline">{tpl.edges.length} 边</Badge>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#F0F0EC]">
                      <span className="text-[11px] text-[#B5B5B5]">
                        {formatLocalTime(tpl.created_at)}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setGoal(tpl.goal_hint)
                            setGraphTemplateResult(null)
                          }}
                          disabled={!tpl.goal_hint.trim()}
                          className="gap-1 text-xs"
                        >
                          使用目标
                        </Button>
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => executeGraphTemplate(tpl)}
                          disabled={!!graphTemplateExecutingId}
                          className="gap-1 text-xs"
                        >
                          {isExecuting ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Play className="h-3 w-3" />
                          )}
                          {isExecuting ? "执行中..." : "按模板执行"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => cloneGraphTemplate(tpl)}
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <Copy className="h-3 w-3" />
                          克隆
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => editGraphTemplate(tpl)}
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <FileText className="h-3 w-3" />
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadVersionList(tpl.template_id)}
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <History className="h-3 w-3" />
                          版本
                        </Button>
                        <Button
                          data-testid="audit-log-btn"
                          variant="ghost"
                          size="sm"
                          onClick={() => loadAuditLog(tpl.template_id)}
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <ClipboardList className="h-3 w-3" />
                          审计
                        </Button>
                        <Button
                          data-testid="preview-canvas-btn"
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setExpandedPreviewId(
                              expandedPreviewId === tpl.template_id ? null : tpl.template_id,
                            )
                          }
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <Eye className="h-3 w-3" />
                          预览图
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteGraphTemplate(tpl.template_id)}
                          className="gap-1 text-xs text-[#B5B5B5] hover:text-red-500"
                        >
                          <Trash2 className="h-3 w-3" />
                          删除
                        </Button>
                      </div>
                    </div>
                    {expandedPreviewId === tpl.template_id && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
                        className="mt-3 pt-3 border-t border-[#F0F0EC] overflow-hidden"
                      >
                        <DagCanvas
                          nodes={tpl.nodes}
                          edges={tpl.edges}
                        />
                      </motion.div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </motion.div>
      )}

      {/* Phase 6.6: Version History Panel */}
      {mode === "boss-lite" && versionListTemplateId && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white mt-4"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">
                版本历史 / {graphTemplates.find((template) => template.template_id === versionListTemplateId)?.name || versionListTemplateId}
              </h3>
              {versionList && (
                <Badge variant="secondary">{versionList.length}</Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setVersionListTemplateId(null)
                setVersionList(null)
                setVersionDetail(null)
                setVersionError(null)
                setCompareMode(false)
                setCompareFrom(null)
                setCompareTo(null)
                setCompareResult(null)
                setEditingVersionMeta(null)
              }}
              className="gap-1 text-xs text-[#8A8A8A] hover:text-[#0B0B0B]"
            >
              <X className="h-3 w-3" />
              关闭
            </Button>
          </div>

          {versionListLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-[#8A8A8A]" />
            </div>
          ) : versionError ? (
            <div className="rounded-xl border border-red/20 bg-red/5 p-4 text-sm text-red-500">
              <div className="mb-1 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 font-medium">
                  <AlertCircle className="h-3.5 w-3.5" />
                  版本操作失败
                </div>
                <Button
                  data-testid="version-error-dismiss"
                  variant="ghost"
                  size="sm"
                  onClick={() => setVersionError(null)}
                  className="h-6 px-2 text-xs text-red-500"
                >
                  关闭提示
                </Button>
              </div>
              <p className="text-xs">{versionError}</p>
            </div>
          ) : versionList && versionList.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B] text-center">
              暂无版本历史。编辑模板后会自动保存历史版本。
            </div>
          ) : versionList && (
            <div className="space-y-2">
              {/* Compare mode toggle */}
              <div className="flex items-center gap-2 mb-2">
                <Button
                  data-testid="version-compare-toggle"
                  variant={compareMode ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setCompareMode(!compareMode)
                    setCompareFrom(null)
                    setCompareTo(null)
                    setCompareResult(null)
                  }}
                  className="gap-1 text-xs"
                >
                  <GitCompareArrows className="h-3 w-3" />
                  {compareMode ? "退出对比" : "版本对比"}
                </Button>
                {compareMode && compareFrom && compareTo && (
                  <Button
                    data-testid="version-compare-run"
                    variant="default"
                    size="sm"
                    onClick={runVersionCompare}
                    disabled={compareLoading}
                    className="gap-1 text-xs"
                  >
                    {compareLoading ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <GitCompareArrows className="h-3 w-3" />
                    )}
                    执行对比
                  </Button>
                )}
                {compareMode && (
                  <span className="text-[11px] text-[#8A8A8A]">
                    选择两个版本，或选一个版本再选「当前模板」
                  </span>
                )}
              </div>

              {versionList.map((v) => (
                <div
                  key={v.version_id}
                  className={cn(
                    "flex items-center justify-between rounded-lg border p-3 hover:bg-[#F9F9F7] transition-all",
                    compareMode && (compareFrom === v.version_id || compareTo === v.version_id)
                      ? "border-primary bg-primary/5"
                      : "border-[#F0F0EC]",
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {compareMode && (
                        <input
                          data-testid={`version-compare-${v.version_id}`}
                          type="checkbox"
                          checked={compareFrom === v.version_id || compareTo === v.version_id}
                          aria-label={`选择版本 ${v.label || v.version_id}`}
                          onChange={() => {
                            setCompareResult(null)
                            if (compareFrom === v.version_id) {
                              setCompareFrom(null)
                            } else if (compareTo === v.version_id) {
                              setCompareTo(null)
                            } else if (!compareFrom) {
                              setCompareFrom(v.version_id)
                            } else if (!compareTo) {
                              setCompareTo(v.version_id)
                            }
                          }}
                          className="h-3.5 w-3.5 rounded border-[#D8D8D2]"
                        />
                      )}
                      <span className="text-[10px] font-mono text-[#B5B5B5] bg-[#F4F3EF] px-1.5 py-0.5 rounded">
                        {v.version_id}
                      </span>
                      {v.pinned && (
                        <span data-testid={`version-pinned-${v.version_id}`} className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                          <Pin className="h-2.5 w-2.5" />
                          固定
                        </span>
                      )}
                      {v.label ? (
                        <span className="text-xs font-medium text-[#0B0B0B]">{v.label}</span>
                      ) : (
                        <span className="text-xs text-[#6B6B6B]">{v.name}</span>
                      )}
                    </div>
                    {v.note && (
                      <p className="text-[11px] text-[#8A8A8A] mb-1 truncate max-w-md">{v.note}</p>
                    )}
                    <div className="flex items-center gap-3 text-[11px] text-[#B5B5B5]">
                      <span>{formatLocalTime(v.created_at)}</span>
                      <span>{v.node_count} 节点</span>
                      <span>{v.edge_count} 边</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!compareMode && (
                      <>
                        <Button
                          data-testid={`version-pin-${v.version_id}`}
                          variant="ghost"
                          size="sm"
                          onClick={() => togglePin(versionListTemplateId, v.version_id, v.pinned)}
                          disabled={pinLoading === v.version_id}
                          aria-label={v.pinned ? "取消固定" : "固定版本"}
                          className={cn(
                            "gap-1 text-xs",
                            v.pinned ? "text-amber-600 hover:text-amber-700" : "text-[#8A8A8A] hover:text-[#0B0B0B]",
                          )}
                        >
                          {pinLoading === v.version_id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Pin className="h-3 w-3" />
                          )}
                          {v.pinned ? "取消固定" : "固定"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingVersionMeta({ versionId: v.version_id, label: v.label || "", note: v.note || "" })}
                          className="gap-1 text-xs text-[#8A8A8A] hover:text-[#0B0B0B]"
                        >
                          <Pencil className="h-3 w-3" />
                          备注
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadVersionDetail(versionListTemplateId, v.version_id)}
                          disabled={versionDetailLoading}
                          className="gap-1 text-xs text-[#6B6B6B] hover:text-[#0B0B0B]"
                        >
                          <Eye className="h-3 w-3" />
                          查看
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setRollbackConfirmVersionId(v.version_id)}
                          className="gap-1 text-xs"
                        >
                          <RotateCcw className="h-3 w-3" />
                          回滚
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}

              {/* Compare with current template option */}
              {compareMode && (
                <button
                  data-testid="version-compare-current"
                  type="button"
                  disabled={!compareFrom}
                  aria-pressed={compareTo === "current"}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg border border-dashed p-3 text-left transition-all hover:bg-[#F9F9F7] disabled:cursor-not-allowed disabled:opacity-50",
                    compareTo === "current" ? "border-primary bg-primary/5" : "border-[#D8D8D2]",
                  )}
                  onClick={() => {
                    setCompareResult(null)
                    if (compareTo === "current") {
                      setCompareTo(null)
                    } else {
                      setCompareTo("current")
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "h-3.5 w-3.5 rounded border border-[#D8D8D2]",
                        compareTo === "current" && "border-primary bg-primary",
                      )}
                    />
                    <span className="text-xs text-[#6B6B6B]">当前模板（最新状态）</span>
                  </div>
                </button>
              )}
            </div>
          )}

          {/* Version metadata edit dialog */}
          {editingVersionMeta && (
            <div data-testid="version-meta-editor" className="mt-4 rounded-lg border border-[#E5E5E5] p-4 bg-[#FAFAF8]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-[#0B0B0B]">
                  编辑版本备注 / {editingVersionMeta.versionId}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditingVersionMeta(null)}
                  aria-label="关闭版本备注编辑"
                  className="h-6 w-6 p-0"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-[11px] text-[#8A8A8A] mb-1 block">标签（可选，最多 100 字符）</label>
                  <input
                    data-testid="version-label-input"
                    type="text"
                    value={editingVersionMeta.label}
                    onChange={(e) => setEditingVersionMeta({ ...editingVersionMeta, label: e.target.value })}
                    maxLength={100}
                    placeholder="如：发布前备份"
                    className="w-full rounded-md border border-[#E5E5E5] px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-[#8A8A8A] mb-1 block">备注（可选，最多 500 字符）</label>
                  <textarea
                    data-testid="version-note-input"
                    value={editingVersionMeta.note}
                    onChange={(e) => setEditingVersionMeta({ ...editingVersionMeta, note: e.target.value })}
                    maxLength={500}
                    rows={3}
                    placeholder="记录这次版本变更的原因或要点"
                    className="w-full rounded-md border border-[#E5E5E5] px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                  />
                </div>
                <div className="flex items-center gap-2 justify-end">
                  <Button
                    data-testid="version-meta-cancel"
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingVersionMeta(null)}
                    className="text-xs"
                  >
                    取消
                  </Button>
                  <Button
                    data-testid="version-meta-save"
                    variant="default"
                    size="sm"
                    onClick={saveVersionMetadata}
                    disabled={versionMetaSaving}
                    className="gap-1 text-xs"
                  >
                    {versionMetaSaving && <Loader2 className="h-3 w-3 animate-spin" />}
                    保存
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Compare result panel */}
          {compareResult && (() => {
            const diff = compareResult as {
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
            const totalChanges = diff.field_changes.length +
              diff.nodes.added.length + diff.nodes.removed.length + diff.nodes.modified.length +
              diff.edges.added.length + diff.edges.removed.length + diff.edges.modified.length
            return (
              <div data-testid="version-compare-result" className="mt-4 rounded-lg border border-[#E5E5E5] p-4 bg-[#FAFAF8]">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-[#0B0B0B]">
                    对比结果: {diff.from_version} → {diff.to_version}
                    <span className="ml-2 text-[#8A8A8A]">共 {totalChanges} 处变化</span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCompareResult(null)}
                    aria-label="关闭版本对比结果"
                    className="h-6 w-6 p-0"
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>

                {totalChanges === 0 ? (
                  <div className="text-xs text-[#8A8A8A] text-center py-4">两个版本完全相同，无差异</div>
                ) : (
                  <div className="space-y-4">
                    {/* Field changes */}
                    {diff.field_changes.length > 0 && (
                      <div>
                        <h5 className="text-[11px] font-medium text-[#6B6B6B] mb-2">基础字段变化</h5>
                        <div className="space-y-1.5">
                          {diff.field_changes.map((c, i) => (
                            <div key={i} className="flex items-start gap-2 text-[11px]">
                              <span className="font-mono text-[#8A8A8A] min-w-[80px]">{c.field}</span>
                              <span className="text-red-500 line-through flex-1">{c.from || "(空)"}</span>
                              <span className="text-green-600 flex-1">{c.to || "(空)"}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Node changes */}
                    {(diff.nodes.added.length > 0 || diff.nodes.removed.length > 0 || diff.nodes.modified.length > 0) && (
                      <div>
                        <h5 className="text-[11px] font-medium text-[#6B6B6B] mb-2">节点变化</h5>
                        <div className="space-y-1">
                          {diff.nodes.added.map((n, i) => (
                            <div key={`add-${i}`} className="flex items-center gap-2 text-[11px]">
                              <span className="text-green-600 font-medium">+ 新增</span>
                              <span className="font-mono">{n.id as string}</span>
                              <span className="text-[#8A8A8A]">{n.title as string || n.agent_id as string}</span>
                            </div>
                          ))}
                          {diff.nodes.removed.map((n, i) => (
                            <div key={`rm-${i}`} className="flex items-center gap-2 text-[11px]">
                              <span className="text-red-500 font-medium">- 删除</span>
                              <span className="font-mono">{n.id as string}</span>
                              <span className="text-[#8A8A8A]">{n.title as string || n.agent_id as string}</span>
                            </div>
                          ))}
                          {diff.nodes.modified.map((m, i) => (
                            <div key={`mod-${i}`} className="text-[11px]">
                              <div className="flex items-center gap-2">
                                <span className="text-amber-600 font-medium">~ 修改</span>
                                <span className="font-mono">{m.id}</span>
                              </div>
                              <div className="ml-6 text-[10px] text-[#8A8A8A]">
                                {Object.keys(m.to).filter(k => JSON.stringify(m.from[k]) !== JSON.stringify(m.to[k])).map(k => (
                                  <div key={k}>{k}: <span className="text-red-500 line-through">{JSON.stringify(m.from[k])}</span> → <span className="text-green-600">{JSON.stringify(m.to[k])}</span></div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Edge changes */}
                    {(diff.edges.added.length > 0 || diff.edges.removed.length > 0 || diff.edges.modified.length > 0) && (
                      <div>
                        <h5 className="text-[11px] font-medium text-[#6B6B6B] mb-2">边变化</h5>
                        <div className="space-y-1">
                          {diff.edges.added.map((e, i) => (
                            <div key={`add-${i}`} className="flex items-center gap-2 text-[11px]">
                              <span className="text-green-600 font-medium">+ 新增</span>
                              <span className="font-mono">{e.from_node as string}→{e.to_node as string}</span>
                            </div>
                          ))}
                          {diff.edges.removed.map((e, i) => (
                            <div key={`rm-${i}`} className="flex items-center gap-2 text-[11px]">
                              <span className="text-red-500 font-medium">- 删除</span>
                              <span className="font-mono">{e.from_node as string}→{e.to_node as string}</span>
                            </div>
                          ))}
                          {diff.edges.modified.map((m, i) => (
                            <div key={`mod-${i}`} className="text-[11px]">
                              <div className="flex items-center gap-2">
                                <span className="text-amber-600 font-medium">~ 修改</span>
                                <span className="font-mono">{m.from_node}→{m.to_node}</span>
                              </div>
                              <div className="ml-6 text-[10px] text-[#8A8A8A]">
                                {Object.keys(m.to).filter(k => JSON.stringify(m.from[k]) !== JSON.stringify(m.to[k])).map(k => (
                                  <div key={k}>{k}: <span className="text-red-500 line-through">{JSON.stringify(m.from[k])}</span> → <span className="text-green-600">{JSON.stringify(m.to[k])}</span></div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })()}

          {/* Version detail preview */}
          {versionDetail && (
            <div className="mt-4 rounded-lg border border-[#E5E5E5] p-4 bg-[#FAFAF8]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-[#0B0B0B]">
                  版本详情: {(versionDetail as Record<string, unknown>).version_id as string}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setVersionDetail(null)}
                  aria-label="关闭版本详情"
                  className="h-6 w-6 p-0"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
              <pre className="text-[11px] text-[#6B6B6B] overflow-auto max-h-60 whitespace-pre-wrap">
                {JSON.stringify(versionDetail, null, 2)}
              </pre>
            </div>
          )}
        </motion.div>
      )}

      {/* Phase 6.8: Audit Log Panel */}
      {mode === "boss-lite" && showAuditLog && auditTemplateId && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white mt-4"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">
                审计日志 / {graphTemplates.find((t) => t.template_id === auditTemplateId)?.name || auditTemplateId}
              </h3>
              {auditEvents && (
                <Badge variant="secondary">{auditEvents.length}</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <select
                data-testid="audit-filter"
                value={auditFilter}
                onChange={(e) => {
                  setAuditFilter(e.target.value)
                  loadAuditLog(auditTemplateId, e.target.value || undefined)
                }}
                className="rounded-md border border-[#E5E5E5] px-2 py-1 text-xs bg-white"
              >
                <option value="">全部事件</option>
                <option value="create">创建</option>
                <option value="clone">克隆</option>
                <option value="update">更新</option>
                <option value="delete">删除</option>
                <option value="execute">执行</option>
                <option value="restore">回滚</option>
                <option value="metadata_update">元数据修改</option>
                <option value="pin">固定</option>
                <option value="unpin">取消固定</option>
              </select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowAuditLog(false)
                  setAuditTemplateId(null)
                  setAuditEvents(null)
                  setAuditFilter("")
                }}
                aria-label="关闭审计日志"
                className="gap-1 text-xs text-[#8A8A8A] hover:text-[#0B0B0B]"
              >
                <X className="h-3 w-3" />
                关闭
              </Button>
            </div>
          </div>

          {auditLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-[#8A8A8A]" />
            </div>
          ) : auditEvents && auditEvents.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B] text-center">
              暂无审计日志。
            </div>
          ) : auditEvents && (
            <div className="space-y-1.5 max-h-96 overflow-y-auto">
              {auditEvents.map((ev) => (
                <div
                  key={ev.event_id}
                  data-testid={`audit-event-${ev.event_type}`}
                  className="flex items-start gap-3 rounded-lg border border-[#F0F0EC] p-2.5 text-[11px] hover:bg-[#F9F9F7] transition-all"
                >
                  <span className="text-[10px] text-[#B5B5B5] min-w-[130px] font-mono shrink-0">
                    {formatLocalTime(ev.timestamp)}
                  </span>
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0",
                    ev.event_type === "create" && "bg-green-50 text-green-700",
                    ev.event_type === "clone" && "bg-emerald-50 text-emerald-700",
                    ev.event_type === "update" && "bg-blue-50 text-blue-700",
                    ev.event_type === "delete" && "bg-red-50 text-red-700",
                    ev.event_type === "execute" && "bg-purple-50 text-purple-700",
                    ev.event_type === "restore" && "bg-amber-50 text-amber-700",
                    ev.event_type === "metadata_update" && "bg-cyan-50 text-cyan-700",
                    ev.event_type === "pin" && "bg-yellow-50 text-yellow-700",
                    ev.event_type === "unpin" && "bg-gray-100 text-gray-600",
                  )}>
                    {ev.event_type}
                  </span>
                  <span className="text-[#0B0B0B] flex-1">{ev.summary}</span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {/* Phase 6.9: Audit Storage Info */}
      {mode === "boss-lite" && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white mt-4"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">Audit Storage / 审计存储</h3>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={previewCleanup}
                disabled={cleanupLoading}
                className="gap-1 text-xs"
              >
                {cleanupLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
                预览清理 30 天前
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={loadAuditStorage}
                disabled={auditStorageLoading}
                className="gap-1 text-[#8A8A8A] hover:text-[#0B0B0B]"
              >
                {auditStorageLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="h-3.5 w-3.5" />
                )}
                刷新
              </Button>
            </div>
          </div>

          {auditStorage ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-xl border border-[#F0F0EC] bg-[#FAFAF8] p-4">
                <div className="text-xs text-[#8A8A8A] mb-1">文件数量</div>
                <div className="text-2xl font-semibold text-[#0B0B0B]">{auditStorage.file_count}</div>
              </div>
              <div className="rounded-xl border border-[#F0F0EC] bg-[#FAFAF8] p-4">
                <div className="text-xs text-[#8A8A8A] mb-1">总大小</div>
                <div className="text-2xl font-semibold text-[#0B0B0B]">{auditStorage.total_size_human}</div>
              </div>
              <div className="rounded-xl border border-[#F0F0EC] bg-[#FAFAF8] p-4">
                <div className="text-xs text-[#8A8A8A] mb-1">最早事件</div>
                <div className="text-sm font-medium text-[#0B0B0B]">
                  {auditStorage.earliest_event ? formatLocalTime(auditStorage.earliest_event) : "—"}
                </div>
              </div>
              <div className="rounded-xl border border-[#F0F0EC] bg-[#FAFAF8] p-4">
                <div className="text-xs text-[#8A8A8A] mb-1">最新事件</div>
                <div className="text-sm font-medium text-[#0B0B0B]">
                  {auditStorage.latest_event ? formatLocalTime(auditStorage.latest_event) : "—"}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B] text-center">
              点击"刷新"加载审计存储信息。
            </div>
          )}

          {/* Cleanup Preview */}
          {cleanupPreview && (
            <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-[#0B0B0B]">清理预览（dry_run）</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCleanupPreview(null)}
                  className="h-6 px-2 text-xs text-[#8A8A8A]"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                <div>
                  <div className="text-xs text-[#8A8A8A]">匹配文件</div>
                  <div className="text-lg font-semibold">{cleanupPreview.matched}</div>
                </div>
                <div>
                  <div className="text-xs text-[#8A8A8A]">跳过文件</div>
                  <div className="text-lg font-semibold">{cleanupPreview.skipped}</div>
                </div>
                <div>
                  <div className="text-xs text-[#8A8A8A]">将释放空间</div>
                  <div className="text-lg font-semibold">{cleanupPreview.bytes_freed_human}</div>
                </div>
                <div>
                  <div className="text-xs text-[#8A8A8A]">错误数</div>
                  <div className="text-lg font-semibold">{cleanupPreview.errors.length}</div>
                </div>
              </div>
              {cleanupPreview.would_delete.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs text-[#8A8A8A] mb-1">将删除的文件：</div>
                  {cleanupPreview.would_delete.map((f) => (
                    <div
                      key={f.template_id}
                      className="flex items-center justify-between rounded-lg border border-[#F0F0EC] p-2 text-[11px]"
                    >
                      <span className="font-mono text-[#0B0B0B]">{f.template_id}</span>
                      <span className="text-[#8A8A8A]">{f.event_count} 事件 · {f.size_bytes} B</span>
                    </div>
                  ))}
                </div>
              )}
              {cleanupPreview.errors.length > 0 && (
                <div className="mt-2 space-y-1">
                  {cleanupPreview.errors.map((e, i) => (
                    <div key={i} className="text-xs text-red-500">
                      {e.template_id}: {e.error}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}

      {/* Graph Template Result */}
      {mode === "boss-lite" && graphTemplateResult && (() => {
        const result = graphTemplateResult
        const ok = result.ok as boolean
        const resultGoal = result.goal as string
        const summary = result.summary as Record<string, unknown> | undefined
        const deliveryTaskId = result.delivery_task_id as string | undefined
        const graph = normalizeGraphResult(result)
        const results = (result.results as Array<Record<string, unknown>>) || []

        return (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Summary Banner */}
            <div className={cn(
              "p-4 rounded-2xl border",
              ok ? "border-green/30 bg-green/5" : "border-red/30 bg-red/5"
            )}>
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  {ok ? (
                    <CheckCircle2 className="h-5 w-5 text-green" />
                  ) : (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <span className="font-medium text-sm">
                      {ok ? "模板执行成功" : "模板执行失败"}
                    </span>
                    {resultGoal && (
                      <span className="ml-3 text-xs text-muted-foreground">{resultGoal}</span>
                    )}
                    {deliveryTaskId && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => viewDelivery(deliveryTaskId)}
                        className="gap-1"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        查看交付物
                      </Button>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {summary && (
                    <>
                      <Badge variant="success">{summary.succeeded as number} 成功</Badge>
                      {(summary.failed as number) > 0 && (
                        <Badge variant="destructive">{summary.failed as number} 失败</Badge>
                      )}
                      {(summary.total_duration_ms as number) > 0 && (
                        <Badge variant="outline">
                          耗时 {((summary.total_duration_ms as number) / 1000).toFixed(1)}s
                        </Badge>
                      )}
                    </>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setGraphTemplateResult(null)}
                    className="gap-1 text-[#B5B5B5] hover:text-[#8A8A8A]"
                  >
                    关闭
                  </Button>
                </div>
              </div>
            </div>

            {/* Collaboration Graph */}
            {graph && <GraphPreviewCard graph={graph} />}

            {/* Node Results Summary */}
            {results.length > 0 && (
              <div className="p-6 rounded-2xl border border-[#E5E5E5] bg-white">
                <h4 className="text-sm font-medium text-[#8A8A8A] mb-3 uppercase tracking-wider">节点结果 / Node Results</h4>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((r, i) => {
                    const nodeOk = r.ok as boolean
                    const nodeTitle = (r.title as string) || (r.agent_id as string) || "unknown"
                    const nodeSummary = r.summary as string
                    const nodeDuration = r.duration_ms as number
                    return (
                      <div
                        key={i}
                        className={cn(
                          "rounded-xl border p-4",
                          nodeOk ? "border-green/20 bg-green/5" : "border-red/20 bg-red/5"
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-[#0B0B0B]">{nodeTitle}</span>
                          <Badge variant={nodeOk ? "success" : "destructive"}>
                            {nodeOk ? "成功" : "失败"}
                          </Badge>
                        </div>
                        <div className="space-y-1 text-xs text-[#8A8A8A]">
                          <div>Agent: <span className="font-mono">{r.agent_id as string}</span></div>
                          {nodeDuration > 0 && <div>耗时: {(nodeDuration / 1000).toFixed(1)}s</div>}
                          {nodeSummary && (
                            <div className="mt-1.5 pt-1.5 border-t border-[#E5E5E5] text-[#6B6B6B]">
                              {truncateText(nodeSummary, 100)}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </motion.div>
        )
      })()}

      {/* Draft restore prompt */}
      {pendingRestoreDraft && (
        <ConfirmDialog
          open
          title="发现未保存草稿"
          description={`检测到上次未完成的模板草稿「${pendingRestoreDraft.name || "未命名"}」（${pendingRestoreDraft.nodes.length} 节点，${pendingRestoreDraft.edges.length} 边）。是否恢复？`}
          confirmLabel="恢复草稿"
          cancelLabel="放弃"
          variant="default"
          onConfirm={restoreDraft}
          onCancel={discardDraft}
          onDismiss={() => setPendingRestoreDraft(null)}
        />
      )}

      {/* Phase 6.6: Rollback confirm dialog */}
      {rollbackConfirmVersionId && (
        <ConfirmDialog
          open
          title="确认回滚"
          description={`将模板恢复到版本 ${rollbackConfirmVersionId} 的状态。\n当前状态会自动保存为新版本，不会丢失数据。`}
          confirmLabel={rollbackLoading ? "回滚中..." : "确认回滚"}
          cancelLabel="取消"
          variant="default"
          onConfirm={rollbackToVersion}
          onCancel={() => {
            if (!rollbackLoading) setRollbackConfirmVersionId(null)
          }}
          onDismiss={() => {
            if (!rollbackLoading) setRollbackConfirmVersionId(null)
          }}
          confirmDisabled={rollbackLoading}
          cancelDisabled={rollbackLoading}
        />
      )}

      {/* Boss Lite Progress — 轻量进度展示 */}
      {mode === "boss-lite" && isRunning && !liteResult && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        >
          <div className="flex items-center gap-3 mb-5">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="font-medium text-[#0B0B0B]">
              正在协调 5 个 Agent 并行工作，通常需要 15–30 秒
            </span>
          </div>
          <div className="space-y-3">
            {[
              "Boss 正在拆解目标",
              "上下文整理 / 沟通表达 / 素材方向 / 数据洞察 / 交付物结构正在协同执行",
              "Boss 正在汇总作战报告",
              "保存到交付中心",
            ].map((label, phase) => (
              <div key={phase} className="flex items-center gap-3">
                {liteProgressPhase > phase ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-green" />
                ) : liteProgressPhase === phase ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                ) : (
                  <div className="h-4 w-4 shrink-0 rounded-full border border-[#D4D4D4]" />
                )}
                <span
                  className={cn(
                    "text-sm",
                    liteProgressPhase > phase
                      ? "text-green"
                      : liteProgressPhase === phase
                        ? "text-[#0B0B0B] font-medium"
                        : "text-[#B5B5B5]"
                  )}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Mission 状态横幅 + 审核按钮 — only in command-center mode */}
      {mode === "command-center" && currentMission && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "p-4 rounded-2xl border",
            currentMission.status === "ready_for_review" ? "border-green/30 bg-green/5" :
            currentMission.status === "partial" ? "border-yellow/30 bg-yellow/5" :
            currentMission.status === "interrupted" ? "border-orange/30 bg-orange/5" :
            currentMission.status === "failed" ? "border-red/30 bg-red/5" :
            currentMission.status === "running" ? "border-blue/30 bg-blue/5" :
            currentMission.status === "done" ? "border-green/20 bg-green/2" :
            "border-[#E5E5E5] bg-white"
          )}
          data-testid="boss-status-banner"
        >
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {currentMission.status === "running" ? (
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              ) : currentMission.status === "ready_for_review" || currentMission.status === "done" ? (
                <CheckCircle2 className="h-5 w-5 text-green" />
              ) : currentMission.status === "partial" || currentMission.status === "interrupted" ? (
                <AlertCircle className="h-5 w-5 text-orange-500" />
              ) : currentMission.status === "failed" ? (
                <AlertCircle className="h-5 w-5 text-red-500" />
              ) : (
                <FileText className="h-5 w-5 text-muted-foreground" />
              )}
              <div>
                <span className="font-medium text-sm">{missionStatusText(currentMission.status)}</span>
                {currentMission.metrics && (
                  <span className="ml-3 text-xs text-muted-foreground">
                    {currentMission.metrics.succeeded_modules}/{currentMission.metrics.total_modules} 模块完成
                    {currentMission.metrics.warning_count > 0 && ` · ${currentMission.metrics.warning_count} 警告`}
                    {currentMission.metrics.failed_modules > 0 && ` · ${currentMission.metrics.failed_modules} 失败`}
                    {(currentMission.metrics.interrupted_modules ?? 0) > 0 && ` · ${currentMission.metrics.interrupted_modules} 中断`}
                  </span>
                )}
                {currentMission.status === "interrupted" && (
                  <p className="text-xs text-orange-600 mt-1">上次执行可能被中断，可重跑未完成模块</p>
                )}
                {/* Phase 6.15: 显示当前正在执行的模块名 */}
                {currentMission.status === "running" && (
                  <p className="text-xs text-blue-600 mt-1">
                    {(() => {
                      const runningMod = currentMission.modules?.find(m => m.status === "running")
                      return runningMod ? `正在执行: ${runningMod.title}` : "正在执行模块中..."
                    })()}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* 接受结果按钮 */}
              {(currentMission.status === "ready_for_review" || currentMission.status === "partial" || currentMission.status === "interrupted") && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={acceptMission}
                  disabled={isRunning}
                  className="gap-1 bg-green hover:bg-green/90"
                  data-testid="boss-accept-btn"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  接受结果
                </Button>
              )}
              {/* 重新执行按钮 */}
              {currentMission.status !== "running" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={confirmRun}
                  disabled={isRunning}
                  className="gap-1"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  重新执行全部
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* Phase 6.19: 审核清单 — 仅在 command-center 审核阶段显示 */}
      {mode === "command-center" && currentMission && selectedTemplate?.suggested_review_checklist && (
        ["ready_for_review", "partial", "interrupted"].includes(currentMission.status) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-[#E5E5E5] bg-[#F9F9F8] p-4"
            data-testid="boss-review-checklist"
          >
            <h4 className="text-sm font-medium text-[#0B0B0B] mb-2">📋 审核清单</h4>
            <ul className="space-y-1.5">
              {selectedTemplate.suggested_review_checklist.map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-[#5A5A5A]">
                  <span className="mt-0.5 h-3.5 w-3.5 rounded border border-[#D4D4D4] bg-white flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </motion.div>
        )
      )}

      {/* Boss Lite Results */}
      {mode === "boss-lite" && liteResult && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          {/* Summary Banner */}
          <div className={cn(
            "p-4 rounded-2xl border",
            liteResult.ok ? "border-green/30 bg-green/5" : "border-red/30 bg-red/5"
          )}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {liteResult.ok ? (
                  <CheckCircle2 className="h-5 w-5 text-green" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-500" />
                )}
                <div>
                  <span className="font-medium text-sm">{liteResult.summary.text}</span>
                  {liteResult.delivery_task_id && (
                    <span className="ml-3 text-xs text-muted-foreground">
                      交付物 ID: {liteResult.delivery_task_id}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success">{liteResult.summary.succeeded} 成功</Badge>
                {liteResult.summary.failed > 0 && (
                  <Badge variant="destructive">{liteResult.summary.failed} 失败</Badge>
                )}
                {liteResult.summary.total_duration_ms != null && liteResult.summary.total_duration_ms > 0 && (
                  <Badge variant="outline">
                    耗时 {(liteResult.summary.total_duration_ms / 1000).toFixed(1)}s
                  </Badge>
                )}
                {/* Handoff 状态 Badge */}
                {(() => {
                  const hoEnabled = liteResult.handoff_enabled ?? liteResult.structured_output?.handoff_enabled
                  if (!hoEnabled) return null
                  const sources = liteResult.structured_output?.handoff_sources
                  const targets = liteResult.structured_output?.handoff_targets
                  if (sources?.length && targets?.length) {
                    return (
                      <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/5 text-primary">
                        {sources.join(" / ")} → {targets.join(" / ")}
                      </Badge>
                    )
                  }
                  return (
                    <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/5 text-primary">
                      部门协作已启用
                    </Badge>
                  )
                })()}
                {liteResult.delivery_task_id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => viewDelivery(liteResult.delivery_task_id!)}
                    className="gap-1"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    查看交付物
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Collaboration Graph */}
          {(() => {
            const graph = normalizeGraphResult(liteResult as unknown as Record<string, unknown>)
            if (!graph) return null
            return <GraphPreviewCard graph={graph} />
          })()}

          {/* Agent Navigation + Results */}
          <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
            <div className="space-y-3">
              {liteResult.results.map((r) => {
                const isActive = liteActiveAgent === r.agent_id

                return (
                  <button
                    key={r.agent_id}
                    type="button"
                    onClick={() => setLiteActiveAgent(r.agent_id)}
                    className={cn(
                      "w-full rounded-xl border p-4 text-left transition-all",
                      isActive
                        ? "border-primary/50 bg-primary/10"
                        : "border-border bg-card/70 hover:border-primary/30 hover:bg-accent/50"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background/70">
                        {r.ok ? (
                          <CheckCircle2 className="h-4 w-4 text-green" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-yellow" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{r.title}</span>
                          <Badge variant={r.ok ? "success" : "destructive"}>
                            {r.ok ? "成功" : "失败"}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {extractAgentSummary(r.agent_id, r.summary, r.structured_output)}
                        </p>
                        {/* Handoff 标记 */}
                        {r.used_handoff && (
                          <div className="mt-1.5 flex items-center gap-1.5">
                            <Badge variant="outline" className="text-[10px] border-primary/30 bg-primary/5 text-primary">
                              已参考上游洞察
                            </Badge>
                            {r.handoff_sources && r.handoff_sources.length > 0 && (
                              <span className="text-[10px] text-[#8A8A8A]">
                                来源：{r.handoff_sources.join(" / ")}
                              </span>
                            )}
                          </div>
                        )}
                        {r.duration_ms != null && r.duration_ms > 0 && (
                          <p className="mt-1 text-xs text-[#8A8A8A]">
                            耗时 {(r.duration_ms / 1000).toFixed(1)}s
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Active Agent Result Detail */}
            {liteResult.results.map((r) => {
              if (r.agent_id !== liteActiveAgent) return null
              const Icon = agentIcons[r.agent_id] || FileText

              return (
                <motion.div
                  key={r.agent_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="min-h-[520px] p-6 rounded-2xl border border-[#E5E5E5] bg-white">
                    <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                          <Icon className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <h2 className="text-xl font-semibold">{r.title}</h2>
                          <p className="text-sm text-muted-foreground">{r.agent_id}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                      <Badge variant={r.ok ? "success" : "destructive"}>
                        {r.ok ? "成功" : "失败"}
                      </Badge>
                      {r.duration_ms != null && r.duration_ms > 0 && (
                        <Badge variant="outline">
                          耗时 {(r.duration_ms / 1000).toFixed(1)}s
                        </Badge>
                      )}
                    </div>
                    </div>

                    {/* Summary — always show extracted summary */}
                    <div className="rounded-lg border border-border bg-background/60 p-4 mb-4">
                      <h4 className="mb-2 text-sm font-medium">摘要</h4>
                      <p className="text-sm text-muted-foreground">
                        {extractAgentSummary(r.agent_id, r.summary, r.structured_output)}
                      </p>
                    </div>

                    {/* Handoff 信息 — 仅在 used_handoff 时显示 */}
                    {r.used_handoff && r.handoff_sources && r.handoff_sources.length > 0 && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 mb-4">
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-primary" />
                          <span className="text-sm text-primary">
                            本部门输出已参考上游洞察：<strong>{r.handoff_sources.join(" / ")}</strong>
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Key Fields — structured readable block */}
                    {r.structured_output && (() => {
                      const keyFields = extractKeyFields(r.agent_id, r.structured_output)
                      if (keyFields.length === 0) return null
                      return (
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 mb-4">
                          <h4 className="mb-3 text-sm font-medium text-primary">关键信息</h4>
                          <div className="space-y-2">
                            {keyFields.map((field, i) => (
                              <div key={i} className="flex gap-2">
                                <span className="shrink-0 text-xs font-medium text-muted-foreground min-w-[80px]">
                                  {field.label}
                                </span>
                                <span className="text-sm">{field.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })()}

                    {/* Structured Output — raw JSON (collapsible) */}
                    {r.structured_output && Object.keys(r.structured_output).length > 0 && (() => {
                      const so = r.structured_output
                      const provider = so.provider as string | undefined
                      return (
                        <div className="space-y-3">
                          {/* Provider info */}
                          {provider && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>Provider:</span>
                              <Badge variant="outline">{provider}</Badge>
                            </div>
                          )}

                          {/* Raw JSON */}
                          <details className="rounded-lg border border-border bg-background/60">
                            <summary className="p-4 cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                              查看原始 JSON 输出
                            </summary>
                            <pre className="px-4 pb-4 whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground max-h-[400px] overflow-y-auto">
                              {JSON.stringify(so, null, 2)}
                            </pre>
                          </details>
                        </div>
                      )
                    })()}

                    {/* Warnings */}
                    {r.warnings.length > 0 && (
                      <div className="mt-4 rounded-lg border border-yellow/20 bg-yellow/10 p-3">
                        {r.warnings.map((w, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm text-yellow">
                            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Errors */}
                    {r.error && (
                      <div className="mt-4 rounded-lg border border-red/20 bg-red/5 p-3">
                        <div className="flex items-start gap-2 text-sm text-red-500">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                          <span>{r.error}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* 模块导航 + 结果 — only in command-center mode */}
      {mode === "command-center" && modules.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="space-y-3">
            {modules.map((module) => {
              const Icon = moduleIcons[module.module_id] || FileText
              const isActive = activeModule === module.module_id

              return (
                <button
                  key={module.module_id}
                  type="button"
                  onClick={() => setActiveModule(module.module_id)}
                  className={cn(
                    "w-full rounded-xl border p-4 text-left transition-all",
                    isActive
                      ? "border-primary/50 bg-primary/10"
                      : "border-border bg-card/70 hover:border-primary/30 hover:bg-accent/50"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background/70">
                      {module.status === "running" ? (
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      ) : module.status === "done" ? (
                        <CheckCircle2 className="h-4 w-4 text-green" />
                      ) : module.status === "failed" && module.mode === "blocked" ? (
                        <ShieldOff className="h-4 w-4 text-orange-500" />
                      ) : module.status === "failed" ? (
                        <AlertCircle className="h-4 w-4 text-yellow" />
                      ) : module.status === "skipped" ? (
                        <SkipForward className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Icon className="h-4 w-4 text-primary" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{module.title}</span>
                        {statusBadge(module.status)}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {moduleDescriptions[module.module_id] || ""}
                      </p>
                      {module.duration_ms != null && module.duration_ms > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          耗时 {formatDuration(module.duration_ms)}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          <motion.div
            key={activeModule}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="min-h-[520px] p-6 rounded-2xl border border-[#E5E5E5] bg-white">
              {activeResult && (
                <>
                  <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        {(() => {
                          const Icon = moduleIcons[activeResult.module_id] || FileText
                          return <Icon className="h-5 w-5 text-primary" />
                        })()}
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold">{activeResult.title}</h2>
                        <p className="text-sm text-muted-foreground">
                          {moduleDescriptions[activeResult.module_id] || ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {statusBadge(activeResult.status)}
                      {activeResult.confidence > 0 && (
                        <Badge variant="outline">置信度 {Math.round(activeResult.confidence * 100)}%</Badge>
                      )}
                      {activeResult.duration_ms != null && activeResult.duration_ms > 0 && (
                        <Badge variant="outline">{formatDuration(activeResult.duration_ms)}</Badge>
                      )}
                      {activeResult.status !== "running" && activeResult.status !== "skipped" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => rerunModule(activeResult.module_id)}
                          disabled={isRunning}
                          className="gap-1"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          重跑
                        </Button>
                      )}
                    </div>
                  </div>

                  {activeResult.status === "pending" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/40 text-center">
                      <FileText className="mb-3 h-10 w-10 text-muted-foreground" />
                      <h3 className="font-medium">模块尚未执行</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        点击上方「确认执行」按钮开始生成结果。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "running" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-primary/20 bg-primary/5 text-center">
                      <Loader2 className="mb-3 h-10 w-10 animate-spin text-primary" />
                      <h3 className="font-medium">正在生成 {activeResult.title}</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        正在调用 AI Company OS 的任务分类、路由和结果验证链路。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "skipped" && (
                    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/40 text-center">
                      <SkipForward className="mb-3 h-10 w-10 text-muted-foreground" />
                      <h3 className="font-medium">模块已跳过</h3>
                      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                        此模块未被选中执行。创建任务时可以选择要执行的模块。
                      </p>
                    </div>
                  )}

                  {activeResult.status === "interrupted" && (
                    <div className="rounded-lg border border-orange-300 bg-orange-50 p-4">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="mt-0.5 h-5 w-5 text-orange-500" />
                        <div>
                          <h3 className="font-medium text-orange-700">执行中断</h3>
                          <p className="mt-1 text-sm text-orange-600">
                            上次执行可能被中断（服务重启、浏览器关闭或模型超时）。已有结果已保留，可重跑该模块。
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeResult.status === "failed" && activeResult.mode === "blocked" && (
                    <div className="rounded-lg border border-orange-300 bg-orange-50 p-4">
                      <div className="flex items-start gap-3">
                        <ShieldOff className="mt-0.5 h-5 w-5 text-orange-500" />
                        <div>
                          <h3 className="font-medium text-orange-700">需要授权浏览器采集</h3>
                          <p className="mt-1 text-sm text-orange-600">
                            {activeResult.error || "此模块需要打开浏览器采集数据，请授权后重试。"}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-3 gap-1"
                            onClick={() => {
                              setAllowBrowserAutomation(true)
                              rerunModule(activeResult.module_id, true)
                            }}
                            disabled={isRunning}
                          >
                            <Shield className="h-3.5 w-3.5" />
                            授权并重试本模块
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeResult.status === "failed" && activeResult.mode !== "blocked" && (
                    <div className="rounded-lg border border-yellow/20 bg-yellow/10 p-4">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="mt-0.5 h-5 w-5 text-yellow" />
                        <div>
                          <h3 className="font-medium">模块未完成</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {activeResult.error || "当前模块执行失败，请稍后重试或检查模型配置。"}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeResult.result && (
                    <div className="space-y-4">
                      <div className="rounded-lg border border-border bg-background/60 p-4">
                        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                          {activeResult.result}
                        </pre>
                      </div>

                      {(activeResult.used_tools || []).length > 0 && (
                        <div className="flex flex-wrap items-center gap-2">
                          {(activeResult.used_tools || []).map((tool) => (
                            <Badge key={tool} variant="outline">
                              {tool}
                            </Badge>
                          ))}
                          {activeResult.mode && (
                            <Badge variant="secondary">mode: {activeResult.mode}</Badge>
                          )}
                          {/* 显示 Provider */}
                          {(() => {
                            const so = activeResult.structured_output as Record<string, unknown>
                            const provider = so?.provider as string
                            return provider ? (
                              <Badge variant="outline" className="gap-1">
                                <span className="text-xs">Provider:</span>
                                {provider}
                              </Badge>
                            ) : null
                          })()}
                        </div>
                      )}

                      {(activeResult.warnings || []).length > 0 && (
                        <div className="rounded-lg border border-yellow/20 bg-yellow/10 p-3">
                          {(activeResult.warnings || []).map((warning) => (
                            <div key={warning} className="flex items-start gap-2 text-sm text-yellow">
                              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                              <span>{warning}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeResult.next_actions && activeResult.next_actions.length > 0 && (
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                          <p className="mb-1 text-sm font-medium">下一步建议</p>
                          {activeResult.next_actions.map((action, i) => (
                            <div key={i} className="text-sm text-muted-foreground">• {action}</div>
                          ))}
                        </div>
                      )}

                      {/* 结构化输出 */}
                      {activeResult.structured_output && Object.keys(activeResult.structured_output).length > 0 && (() => {
                        const so = activeResult.structured_output as Record<string, unknown>
                        const competitors = so.competitors as Array<Record<string, string>> | undefined
                        const pricing = so.pricing as Record<string, unknown> | undefined
                        const evidence = so.evidence as Array<Record<string, string>> | undefined
                        const evidenceFiles = so.evidence_files as string[] | undefined
                        const screenshots = so.screenshots as string[] | undefined
                        const toolCalls = so.tool_calls as Array<Record<string, unknown>> | undefined
                        const imagePlan = so.image_plan as Record<string, unknown> | undefined
                        const provider = so.provider as string | undefined
                        const generatedAt = so.generated_at as string | undefined
                        const summary = so.summary as string | undefined
                        const status = so.status as string | undefined
                        const evidenceGatePassed = so.evidence_gate_passed as boolean | undefined
                        const missingEvidence = so.missing_evidence as string[] | undefined
                        return (
                          <div className="space-y-3">
                            {/* Provider 信息 */}
                            {provider && (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>执行 Provider:</span>
                                <Badge variant="outline">{provider}</Badge>
                                {generatedAt && (
                                  <span>生成时间: {new Date(generatedAt).toLocaleString("zh-CN")}</span>
                                )}
                                {status && (
                                  <Badge variant={status === "success" ? "success" : status === "partial" ? "warning" : "destructive"}>
                                    {status === "success" ? "成功" : status === "partial" ? "证据不足" : "失败"}
                                  </Badge>
                                )}
                              </div>
                            )}

                            {/* 证据门槛状态 */}
                            {evidenceGatePassed !== undefined && (
                              <div className={`rounded-lg border p-3 ${evidenceGatePassed ? "border-green/20 bg-green/5" : "border-yellow/20 bg-yellow/5"}`}>
                                <div className="flex items-center gap-2">
                                  {evidenceGatePassed ? (
                                    <CheckCircle2 className="h-4 w-4 text-green" />
                                  ) : (
                                    <AlertCircle className="h-4 w-4 text-yellow" />
                                  )}
                                  <span className="text-sm font-medium">
                                    {evidenceGatePassed ? "证据门槛已通过" : "证据门槛未通过"}
                                  </span>
                                </div>
                                {!evidenceGatePassed && missingEvidence && missingEvidence.length > 0 && (
                                  <div className="mt-2 text-xs text-muted-foreground">
                                    <p className="font-medium">缺失证据：</p>
                                    {missingEvidence.map((item, i) => (
                                      <p key={i}>• {item}</p>
                                    ))}
                                  </div>
                                )}
                                {!evidenceGatePassed && (
                                  <p className="mt-2 text-xs text-yellow">
                                    ⚠️ 证据不足，不能生成 TOP 推荐结论。请补充更多真实数据后重试。
                                  </p>
                                )}
                              </div>
                            )}

                            {/* 摘要 */}
                            {summary && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">摘要</h4>
                                <p className="text-sm text-muted-foreground">{summary}</p>
                              </div>
                            )}

                            {/* 工具调用记录 */}
                            {Array.isArray(toolCalls) && toolCalls.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  工具调用记录
                                  <Badge variant="secondary" className="ml-2">{toolCalls.length}</Badge>
                                </h4>
                                <div className="space-y-2">
                                  {toolCalls.map((tc, i) => {
                                    const tool = tc.tool as string;
                                    const args = tc.args as Record<string, unknown> | undefined;
                                    const result = tc.result as string | undefined;
                                    return (
                                      <div key={i} className="rounded bg-background/40 p-2 text-xs">
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline">{tool}</Badge>
                                          {args && (
                                            <span className="text-muted-foreground">
                                              args: {JSON.stringify(args).slice(0, 60)}...
                                            </span>
                                          )}
                                        </div>
                                        {result && (
                                          <p className="mt-1 text-muted-foreground">
                                            result: {result.slice(0, 100)}...
                                          </p>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {Array.isArray(competitors) && competitors.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">参考对象分析</h4>
                                <div className="space-y-2">
                                  {competitors.map((c, i) => (
                                    <div key={i} className="rounded bg-background/40 p-2 text-sm">
                                      <span className="font-medium">{c.name || ""}</span>
                                      {c.price && <span className="ml-2 text-muted-foreground">成本/价格: {c.price}</span>}
                                      {c.platform && <span className="ml-2 text-muted-foreground">来源/渠道: {c.platform}</span>}
                                      {c.source_url && (
                                        <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="ml-2 text-primary hover:underline">
                                          来源 ↗
                                        </a>
                                      )}
                                      {c.details && <p className="mt-1 text-muted-foreground">{c.details}</p>}
                                      {c.strengths && <p className="mt-1 text-muted-foreground">优势: {c.strengths}</p>}
                                      {c.weaknesses && <p className="mt-1 text-muted-foreground">劣势: {c.weaknesses}</p>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {pricing && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">定价信息</h4>
                                <pre className="whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground">
                                  {JSON.stringify(pricing, null, 2)}
                                </pre>
                              </div>
                            )}
                            {Array.isArray(evidence) && evidence.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  采集来源
                                  <Badge variant="secondary" className="ml-2">{evidence.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {evidence.map((ev, i) => (
                                    <div key={i} className="flex items-center gap-2 text-xs">
                                      {ev.url ? (
                                        <a href={ev.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                                          {ev.title || ev.url}
                                        </a>
                                      ) : (
                                        <span>{ev.title || "未知来源"}</span>
                                      )}
                                      {ev.type && <Badge variant="outline" className="text-[10px]">{ev.type}</Badge>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {Array.isArray(evidenceFiles) && evidenceFiles.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  证据文件
                                  <Badge variant="secondary" className="ml-2">{evidenceFiles.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {evidenceFiles.map((file, i) => (
                                    <div key={i} className="text-xs text-muted-foreground">📁 {file}</div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {Array.isArray(screenshots) && screenshots.length > 0 && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">
                                  截图
                                  <Badge variant="secondary" className="ml-2">{screenshots.length}</Badge>
                                </h4>
                                <div className="space-y-1">
                                  {screenshots.map((shot, i) => (
                                    <div key={i} className="text-xs text-muted-foreground">🖼️ {shot}</div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {imagePlan && (
                              <div className="rounded-lg border border-border bg-background/60 p-4">
                                <h4 className="mb-2 text-sm font-medium">图片/拍摄建议</h4>
                                <pre className="whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground">
                                  {JSON.stringify(imagePlan, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        )
                      })()}
                      {activeResult.status === "done" && (!activeResult.structured_output || Object.keys(activeResult.structured_output).length === 0) && (
                        <div className="rounded-lg border border-dashed border-border bg-background/40 p-4 text-center text-sm text-muted-foreground">
                          此模块未生成结构化数据。结果已保存在上方文本中。
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </div>
      )}

      {/* 运行日志面板 — only in command-center mode (Phase 6.15: running 时也显示) */}
      {mode === "command-center" && currentMission && (events.length > 0 || currentMission.status === "running") && (
        <div className="p-4 rounded-2xl border border-[#E5E5E5] bg-white">
          <button
            type="button"
            onClick={() => setShowEvents(!showEvents)}
            className="flex w-full items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-[#0B0B0B]">
              <FileText className="h-4 w-4 text-[#8A8A8A]" />
              运行日志
              <Badge variant="secondary" className="ml-1">{events.length}</Badge>
            </div>
            <span className="text-xs text-[#8A8A8A]">{showEvents ? "收起" : "展开"}</span>
          </button>

          {showEvents && (
            <div className="mt-4 space-y-2 max-h-[400px] overflow-y-auto">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className="flex items-start gap-3 rounded-lg border border-border bg-background/40 p-3 text-sm"
                >
                  <div className="shrink-0 text-xs text-muted-foreground w-[70px]">
                    {new Date(evt.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={
                        evt.type.includes("failed") ? "destructive" :
                        evt.type.includes("succeeded") ? "success" :
                        evt.type.includes("started") ? "info" :
                        evt.type.includes("skipped") ? "secondary" :
                        "outline"
                      } className="text-xs">
                        {evt.type}
                      </Badge>
                      {evt.module_id && (
                        <span className="text-xs text-muted-foreground">{evt.module_id}</span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-foreground">{evt.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 空状态（无 mission 时） — only in command-center mode */}
      {mode === "command-center" && !currentMission && !showHistory && (
        <div className="p-6 rounded-2xl border border-dashed border-[#E5E5E5] bg-white">
          <div className="flex min-h-[300px] flex-col items-center justify-center text-center">
            <Briefcase className="mb-3 h-12 w-12 text-[#D4D4D4]" />
            <h3 className="text-lg font-medium text-[#0B0B0B]">输入业务目标开始</h3>
            <p className="mt-2 max-w-md text-sm text-[#8A8A8A]">
              系统会先拆成通用能力模块（目标判断、上下文整理、沟通方案、交付物结构、执行计划）。您确认后逐一执行，并保存结果供人工审核。
            </p>
          </div>
        </div>
      )}

      {/* 最近 Boss 作战记录 — only in boss-lite mode */}
      {mode === "boss-lite" && !isRunning && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="p-6 rounded-2xl border border-[#E5E5E5] bg-white"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-[#8A8A8A]" />
              <h3 className="text-sm font-medium text-[#0B0B0B]">最近 Boss 作战记录</h3>
              {liteHistory.length > 0 && (
                <span className="text-xs text-[#B5B5B5]">
                  已显示 {visibleLiteHistory.length} / {liteHistory.length} 条
                </span>
              )}
              {hiddenTaskIds.length > 0 && (
                <span className="text-xs text-[#B5B5B5]">
                  已隐藏 {hiddenTaskIds.length} 条
                  <button
                    type="button"
                    onClick={restoreAllHidden}
                    className="ml-1.5 underline text-[#8A8A8A] hover:text-[#0B0B0B]"
                  >
                    恢复全部
                  </button>
                </span>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => loadLiteHistory()}
              disabled={liteHistoryLoading}
              className="gap-1 text-[#8A8A8A] hover:text-[#0B0B0B]"
            >
              {liteHistoryLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" />
              )}
              刷新
            </Button>
          </div>
          {/* 对比选择提示 */}
          {liteCompareSelected.length > 0 && (
            <div className="mb-3 flex items-center gap-3 rounded-lg bg-[#F4F3EF] px-4 py-2.5 text-sm">
              <GitCompareArrows className="h-4 w-4 text-[#8A8A8A]" />
              <span className="text-[#6B6B6B]">
                已选 {liteCompareSelected.length} / 2 条
                {liteCompareSelected.length === 1 && "，请再选 1 条"}
                {liteCompareLoading && " — 对比中..."}
              </span>
              {liteCompareError && (
                <span className="text-red-500 text-xs">{liteCompareError}</span>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={clearCompare}
                className="ml-auto gap-1 text-[#8A8A8A] hover:text-[#0B0B0B]"
              >
                <X className="h-3.5 w-3.5" />
                取消
              </Button>
            </div>
          )}
          {/* 对比结果卡片 */}
          {liteCompareResult && liteCompareResult.ok && (
            <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50/50 p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-[#0B0B0B] flex items-center gap-2">
                  <GitCompareArrows className="h-4 w-4 text-blue-500" />
                  任务对比结果
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearCompare}
                  className="h-6 w-6 p-0 text-[#8A8A8A] hover:text-[#0B0B0B]"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
              {/* 并排 task 信息 */}
              <div className="grid grid-cols-2 gap-4 mb-3">
                {liteCompareResult.tasks.map((t, i) => (
                  <div key={t.task_id} className="rounded-lg bg-white p-3 border border-[#E5E5E5]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-[#8A8A8A] bg-[#F4F3EF] px-1.5 py-0.5 rounded">
                        {t.task_id}
                      </span>
                      <span className="text-[10px] text-[#B5B5B5]">
                        {i === 0 ? "A" : "B"}
                      </span>
                    </div>
                    <p className="text-xs text-[#0B0B0B] font-medium truncate">
                      {t.goal?.trim() || "未命名"}
                    </p>
                    <p className="text-[10px] text-[#B5B5B5] mt-0.5">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : "—"}
                    </p>
                  </div>
                ))}
              </div>
              {/* 对比指标表格 */}
              <div className="rounded-lg bg-white border border-[#E5E5E5] overflow-hidden">
                <table className="w-full text-xs">
                  <tbody>
                    {(() => {
                      const d = liteCompareResult.diff
                      const t = liteCompareResult.tasks
                      const rows: Array<{ label: string; a: string; b: string; diff: string; changed: boolean }> = []
                      // 成功率
                      const fmtRate = (task: typeof t[0]) => {
                        if (task.succeeded != null && task.total != null && task.total > 0) {
                          return `${task.succeeded}/${task.total}`
                        }
                        return "—"
                      }
                      rows.push({
                        label: "成功率",
                        a: fmtRate(t[0]),
                        b: fmtRate(t[1]),
                        diff: d.succeeded_diff != null ? (d.succeeded_diff > 0 ? `+${d.succeeded_diff}` : String(d.succeeded_diff)) : "—",
                        changed: d.succeeded_diff != null && d.succeeded_diff !== 0,
                      })
                      // 耗时
                      const fmtDuration = (task: typeof t[0]) => {
                        if (task.total_duration_ms != null && task.total_duration_ms > 0) {
                          const s = task.total_duration_ms / 1000
                          return s < 1 ? `${task.total_duration_ms}ms` : `${s.toFixed(1)}s`
                        }
                        return "—"
                      }
                      rows.push({
                        label: "耗时",
                        a: fmtDuration(t[0]),
                        b: fmtDuration(t[1]),
                        diff: d.total_duration_ms_diff != null ? (() => {
                          const s = d.total_duration_ms_diff / 1000
                          const sign = d.total_duration_ms_diff > 0 ? "+" : ""
                          return s < 1 ? `${sign}${d.total_duration_ms_diff}ms` : `${sign}${s.toFixed(1)}s`
                        })() : "—",
                        changed: d.total_duration_ms_diff != null && d.total_duration_ms_diff !== 0,
                      })
                      // Handoff
                      rows.push({
                        label: "Handoff",
                        a: t[0].handoff_enabled != null ? (t[0].handoff_enabled ? "开" : "关") : "—",
                        b: t[1].handoff_enabled != null ? (t[1].handoff_enabled ? "开" : "关") : "—",
                        diff: "",
                        changed: d.handoff_changed,
                      })
                      // Execution Mode
                      rows.push({
                        label: "执行模式",
                        a: t[0].execution_mode || "—",
                        b: t[1].execution_mode || "—",
                        diff: "",
                        changed: d.execution_mode_changed,
                      })
                      // Goal
                      rows.push({
                        label: "目标",
                        a: t[0].goal ? (t[0].goal.length > 30 ? t[0].goal.slice(0, 30) + "…" : t[0].goal) : "—",
                        b: t[1].goal ? (t[1].goal.length > 30 ? t[1].goal.slice(0, 30) + "…" : t[1].goal) : "—",
                        diff: "",
                        changed: d.goal_changed,
                      })
                      return rows.map((row) => (
                        <tr key={row.label} className={row.changed ? "bg-amber-50" : ""}>
                          <td className="px-3 py-1.5 font-medium text-[#6B6B6B] w-20">{row.label}</td>
                          <td className="px-3 py-1.5 text-[#0B0B0B]">{row.a}</td>
                          <td className="px-3 py-1.5 text-[#0B0B0B]">{row.b}</td>
                          <td className={cn(
                            "px-3 py-1.5 text-right font-mono w-16",
                            row.changed ? "text-amber-600 font-medium" : "text-[#B5B5B5]"
                          )}>
                            {row.diff || (row.changed ? "≠" : "=")}
                          </td>
                        </tr>
                      ))
                    })()}
                  </tbody>
                </table>
              </div>
              {/* Summary diff */}
              {liteCompareResult.diff.summary_changed && (
                <p className="mt-2 text-[10px] text-amber-600">
                  ⚠ 摘要内容不同
                </p>
              )}
            </div>
          )}
          {/* 搜索框 + 排序 */}
          {liteHistory.length > 0 && (
            <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#B5B5B5]" />
                <input
                  type="text"
                  value={liteHistoryQuery}
                  onChange={(e) => setLiteHistoryQuery(e.target.value)}
                  placeholder="搜索 task_id / 目标 / 类型 / 来源"
                  className="w-full rounded-lg border border-[#E5E5E5] bg-[#F9F9F7] pl-9 pr-3 py-2 text-sm text-[#0B0B0B] placeholder:text-[#B5B5B5] focus:outline-none focus:border-[#B5B5B5] transition-colors"
                />
              </div>
              <select
                value={liteHistorySort}
                onChange={(e) => setLiteHistorySort(e.target.value as "newest" | "oldest" | "task_id")}
                className="rounded-lg border border-[#E5E5E5] bg-[#F9F9F7] px-3 py-2 text-sm text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] transition-colors cursor-pointer shrink-0"
              >
                <option value="newest">最新优先</option>
                <option value="oldest">最旧优先</option>
                <option value="task_id">Task ID</option>
              </select>
            </div>
          )}
          {liteHistoryLoading ? (
            <div className="flex items-center gap-2 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-4 text-sm text-[#6B6B6B]">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载历史记录...
            </div>
          ) : liteHistory.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B]">
              暂无 Boss 作战记录。执行一次 Boss Lite 后，作战报告会自动出现在这里。
            </div>
          ) : (
            <div className="space-y-3">
              {visibleLiteHistory.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#D8D8D2] bg-[#FAFAF8] p-5 text-sm text-[#6B6B6B]">
                  没有找到匹配的作战记录
                </div>
              ) : (
                visibleLiteHistory.map((task) => (
                  <div
                    key={task.task_id}
                    className={cn(
                      "flex items-start justify-between gap-3 rounded-xl border p-4 transition-all hover:border-[#B5B5B5] hover:bg-[#F9F9F7]",
                      liteCompareSelected.includes(task.task_id)
                        ? "border-blue-400 bg-blue-50/30"
                        : "border-[#E5E5E5]"
                    )}
                  >
                    {/* 对比 checkbox */}
                    <label className="shrink-0 flex items-center pt-0.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={liteCompareSelected.includes(task.task_id)}
                        onChange={() => toggleCompareSelect(task.task_id)}
                        disabled={
                          !liteCompareSelected.includes(task.task_id) && liteCompareSelected.length >= 2
                        }
                        className="h-4 w-4 rounded border-[#D0D0D0] text-blue-500 focus:ring-blue-400 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                      />
                    </label>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="text-xs font-mono text-[#8A8A8A] bg-[#F4F3EF] px-2 py-0.5 rounded">
                          {task.task_id || "—"}
                        </span>
                        {getTaskOutcomeBadges(task).map((badge, i) => (
                          <span
                            key={i}
                            className={cn(
                              "text-[10px] font-medium px-1.5 py-0.5 rounded",
                              badge.variant === "outline" && "text-[#6B6B6B] bg-[#EEF0E8]",
                              badge.variant === "secondary" && "text-[#8A8A8A] bg-[#F4F3EF]",
                              badge.variant === "info" && "text-blue-600 bg-blue-50",
                              badge.variant === "success" && "text-green bg-green/10",
                              badge.variant === "warning" && "text-yellow-600 bg-yellow-50"
                            )}
                          >
                            {badge.label}
                          </span>
                        ))}
                        <span className="text-xs text-[#B5B5B5]">
                          {formatLocalTime(task.created_at)}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-[#0B0B0B] truncate">
                        {task.goal?.trim() || "未命名作战任务"}
                      </p>
                      <p className="mt-1 text-xs text-[#8A8A8A] line-clamp-2">
                        {getSummaryFallback(task)}
                      </p>
                    </div>
                    <div className="shrink-0 flex items-center gap-2">
                      {task.goal?.trim() && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => copyHistoryGoal(task.task_id, task.goal)}
                            className="gap-1"
                          >
                            <ClipboardList className="h-3.5 w-3.5" />
                            {copiedHistoryGoalId === task.task_id ? "已复制" : "复制目标"}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setGoal(task.goal || "")
                              setLiteResult(null)
                              setLiteActiveAgent("")
                              setLiteProgressPhase(0)
                              setTimeout(() => {
                                document.getElementById("boss-goal-input")?.scrollIntoView({ behavior: "smooth", block: "center" })
                              }, 100)
                            }}
                            className="gap-1"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                            复用目标
                          </Button>
                        </>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => viewDelivery(task.task_id)}
                        className="gap-1"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        查看交付物
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => hideTask(task.task_id)}
                        className="gap-1 text-[#B5B5B5] hover:text-[#8A8A8A]"
                      >
                        <EyeOff className="h-3.5 w-3.5" />
                        隐藏
                      </Button>
                    </div>
                  </div>
                ))
              )}
              {/* 加载更多按钮 */}
              {liteHistoryHasMore && (
                <div className="pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={loadMoreLiteHistory}
                    disabled={liteHistoryLoading}
                    className="w-full gap-1.5 text-[#6B6B6B] hover:text-[#0B0B0B] border-dashed"
                  >
                    {liteHistoryLoading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        加载中...
                      </>
                    ) : (
                      "加载更多"
                    )}
                  </Button>
                </div>
              )}
              {!liteHistoryHasMore && liteHistory.length > 0 && !liteHistoryQuery.trim() && (
                <p className="text-center text-xs text-[#B5B5B5] pt-1">已显示全部</p>
              )}
              {liteHistoryQuery.trim() && !liteHistoryHasMore && visibleLiteHistory.length > 0 && (
                <p className="text-center text-xs text-[#B5B5B5] pt-1">
                  清空搜索查看更多
                </p>
              )}
            </div>
          )}
        </motion.div>
      )}

      {/* Boss Lite 空状态 */}
      {mode === "boss-lite" && !liteResult && !isRunning && (
        <div className="p-6 rounded-2xl border border-dashed border-[#E5E5E5] bg-white">
          <div className="flex min-h-[300px] flex-col items-center justify-center text-center">
            <Zap className="mb-3 h-12 w-12 text-[#D4D4D4]" />
            <h3 className="text-lg font-medium text-[#0B0B0B]">Boss Lite：一句话启动多 Agent 协同</h3>
            <p className="mt-2 max-w-md text-sm text-[#8A8A8A]">
              输入业务目标，系统自动拆解为上下文整理、沟通表达、素材方向、数据洞察、交付物结构 5 类能力，由对应 Agent 依次执行，结果自动保存到交付中心。
            </p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              {["research", "marketing", "image", "data", "website"].map((id) => {
                const Icon = agentIcons[id] || FileText
                return (
                  <div key={id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#E5E5E5] text-xs text-[#8A8A8A]">
                    <Icon className="h-3.5 w-3.5" />
                    {id === "research" ? "上下文整理" : id === "marketing" ? "沟通表达" : id === "image" ? "素材方向" : id === "data" ? "数据洞察" : "交付物结构"}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Export Toast */}
      {exportToast && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-8 right-8 z-50 flex items-center gap-2 px-4 py-3 rounded-xl bg-green text-white shadow-lg"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span className="text-sm font-medium">
            已导出 {exportToast === "markdown" ? "Markdown" : "JSON"} 报告
          </span>
        </motion.div>
      )}
    </div>
  )
}

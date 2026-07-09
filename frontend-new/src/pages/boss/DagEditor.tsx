import { useState, useEffect, useRef } from "react"
import { Plus, Trash2, AlertCircle, ChevronDown, ChevronRight, GitBranch, Pencil, Undo2, Redo2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { validateDag } from "./dag-validation"
import { useDagHistory } from "@/hooks/useDagHistory"

// ── Types (mirrors boss/index.tsx inline interfaces) ──────────

interface GraphNodeDraft {
  id: string
  agent_id: string
  task_type: string
  title: string
  prompt: string
}

interface GraphEdgeDraft {
  from_node: string
  to_node: string
  handoff_type: string
}

export interface GraphTemplateDraft {
  name: string
  description: string
  goal_hint: string
  nodes: GraphNodeDraft[]
  edges: GraphEdgeDraft[]
}

export interface DagEditorProps {
  draft: GraphTemplateDraft
  onChange: (draft: GraphTemplateDraft) => void
  errors: string[]
  disabled?: boolean
}

// ── DAG utilities ─────────────────────────────────────────────

/** Kahn's algorithm — returns wave layers of node IDs */
function computeWaves(nodeIds: string[], edges: GraphEdgeDraft[]): string[][] {
  if (nodeIds.length === 0) return []

  const inDeg = new Map<string, number>()
  const adj = new Map<string, string[]>()
  for (const id of nodeIds) {
    inDeg.set(id, 0)
    adj.set(id, [])
  }
  for (const e of edges) {
    const from = e.from_node.trim()
    const to = e.to_node.trim()
    if (inDeg.has(to) && adj.has(from)) {
      inDeg.set(to, (inDeg.get(to) ?? 0) + 1)
      adj.get(from)!.push(to)
    }
  }

  // seed: nodes with in-degree 0
  let frontier = nodeIds.filter((id) => (inDeg.get(id) ?? 0) === 0)
  const visited = new Set<string>()
  const waves: string[][] = []

  while (frontier.length > 0) {
    waves.push(frontier)
    for (const id of frontier) visited.add(id)
    const next: string[] = []
    for (const id of frontier) {
      for (const neighbor of adj.get(id) ?? []) {
        inDeg.set(neighbor, (inDeg.get(neighbor) ?? 1) - 1)
        if ((inDeg.get(neighbor) ?? 0) === 0 && !visited.has(neighbor)) {
          next.push(neighbor)
        }
      }
    }
    frontier = next
  }

  // catch nodes involved in cycles (not visited)
  const remaining = nodeIds.filter((id) => !visited.has(id))
  if (remaining.length > 0) waves.push(remaining)

  return waves
}

// ── Constants ─────────────────────────────────────────────────

const COMMON_AGENTS = [
  { id: "research", label: "市场调研" },
  { id: "marketing", label: "营销方案" },
  { id: "image", label: "视觉方案" },
  { id: "data", label: "数据分析" },
  { id: "website", label: "落地页" },
]

// ── Component ─────────────────────────────────────────────────

export function DagEditor({ draft, onChange, errors, disabled }: DagEditorProps) {
  const [editingNodeId, setEditingNodeId] = useState<number | null>(null)
  const [editingEdgeIdx, setEditingEdgeIdx] = useState<number | null>(null)
  const renameSessionsRef = useRef(new Map<number, { originId: string; lastSyncedId: string }>())

  // ── Undo/Redo history ──
  const history = useDagHistory<GraphTemplateDraft>(draft, onChange)
  const draftRef = useRef(draft)

  // Sync external draft changes (template switch / clone) into history
  useEffect(() => {
    const curr = JSON.stringify(draft)
    const prev = JSON.stringify(draftRef.current)
    const internal = JSON.stringify(history.state)
    if (curr !== internal && curr !== prev) {
      renameSessionsRef.current.clear()
      history.reset(draft)
    }
    draftRef.current = draft
  }, [draft, history])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (disabled) return
      // Ignore when focus is inside an input/textarea/select
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return

      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault()
        renameSessionsRef.current.clear()
        history.undo()
      } else if (
        (e.ctrlKey || e.metaKey) && e.key === "y" ||
        (e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "Z"
      ) {
        e.preventDefault()
        renameSessionsRef.current.clear()
        history.redo()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [disabled, history])

  // Use history.state as the working draft
  const currentDraft = history.state

  const nodeIds = Array.from(new Set(currentDraft.nodes.map((n) => n.id.trim()).filter(Boolean)))
  const waves = computeWaves(nodeIds, currentDraft.edges.filter((e) => e.from_node.trim() && e.to_node.trim()))
  const dagErrors = validateDag(currentDraft.nodes, currentDraft.edges)
  const errorMessages = Array.from(new Set([...dagErrors.map((error) => error.message), ...errors]))

  // ── Node operations ──

  const updateNode = (index: number, field: keyof GraphNodeDraft, value: string) => {
    const nodes = [...currentDraft.nodes]

    if (field === "id") {
      const oldId = nodes[index].id.trim()
      const newId = value.trim()
      const session = renameSessionsRef.current.get(index) ?? {
        originId: oldId,
        lastSyncedId: oldId,
      }
      renameSessionsRef.current.set(index, session)
      const otherIds = nodes
        .filter((_, i) => i !== index)
        .map((n) => n.id.trim())
        .filter(Boolean)

      const targetId = newId && !otherIds.includes(newId) ? newId : session.originId
      const edges = session.lastSyncedId
        ? currentDraft.edges.map((edge) => ({
            ...edge,
            from_node: edge.from_node.trim() === session.lastSyncedId ? targetId : edge.from_node,
            to_node: edge.to_node.trim() === session.lastSyncedId ? targetId : edge.to_node,
          }))
        : currentDraft.edges
      session.lastSyncedId = targetId
      nodes[index] = { ...nodes[index], [field]: value }
      history.set({ ...currentDraft, nodes, edges })
      return
    }

    nodes[index] = { ...nodes[index], [field]: value }
    history.set({ ...currentDraft, nodes })
  }

  const addNode = () => {
    history.set({
      ...currentDraft,
      nodes: [...currentDraft.nodes, { id: "", agent_id: "", task_type: "", title: "", prompt: "" }],
    })
  }

  const removeNode = (index: number) => {
    const node = currentDraft.nodes[index]
    const nodeId = node.id.trim()
    const linkedEdgeCount = nodeId
      ? currentDraft.edges.filter((e) => e.from_node.trim() === nodeId || e.to_node.trim() === nodeId).length
      : 0

    const label = node.title.trim() || nodeId || `#${index + 1}`
    const msg = linkedEdgeCount > 0
      ? `确认删除节点 ${label}？关联的 ${linkedEdgeCount} 条边也将被移除。`
      : `确认删除节点 ${label}？`

    if (!window.confirm(msg)) return

    const nodes = currentDraft.nodes.filter((_, i) => i !== index)
    const edges = nodeId
      ? currentDraft.edges.filter((e) => e.from_node.trim() !== nodeId && e.to_node.trim() !== nodeId)
      : currentDraft.edges
    history.set({ ...currentDraft, nodes, edges })
    renameSessionsRef.current.clear()
    if (editingNodeId === index) setEditingNodeId(null)
    else if (editingNodeId !== null && editingNodeId > index) setEditingNodeId(editingNodeId - 1)
  }

  // ── Edge operations ──

  const updateEdge = (index: number, field: keyof GraphEdgeDraft, value: string) => {
    const edges = [...currentDraft.edges]
    edges[index] = { ...edges[index], [field]: value }
    history.set({ ...currentDraft, edges })
  }

  const addEdge = () => {
    history.set({
      ...currentDraft,
      edges: [...currentDraft.edges, { from_node: "", to_node: "", handoff_type: "context" }],
    })
  }

  const removeEdge = (index: number) => {
    history.set({ ...currentDraft, edges: currentDraft.edges.filter((_, i) => i !== index) })
    if (editingEdgeIdx === index) setEditingEdgeIdx(null)
    else if (editingEdgeIdx !== null && editingEdgeIdx > index) setEditingEdgeIdx(editingEdgeIdx - 1)
  }

  const undo = () => {
    renameSessionsRef.current.clear()
    history.undo()
  }

  const redo = () => {
    renameSessionsRef.current.clear()
    history.redo()
  }

  // ── Error helpers ──

  const nodeErrorSet = new Set(dagErrors.filter((e) => e.nodeIndex != null).map((e) => e.nodeIndex))
  const edgeErrorSet = new Set(dagErrors.filter((e) => e.edgeIndex != null).map((e) => e.edgeIndex))

  return (
    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] p-5">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="h-4 w-4 text-[#8A8A8A]" />
        <h4 className="text-sm font-medium text-[#0B0B0B]">DAG 编辑器</h4>
        <Badge variant="outline">{currentDraft.nodes.length} 节点</Badge>
        <Badge variant="outline">{currentDraft.edges.length} 边</Badge>
      </div>

      {/* ── Wave Preview ── */}
      {nodeIds.length > 0 && (
        <div className="mb-5">
          <h5 className="text-xs font-medium text-[#8A8A8A] mb-2 uppercase tracking-wider">拓扑预览 / Waves</h5>
          <div className="flex flex-col gap-2 sm:flex-row">
            {waves.map((wave, wi) => (
              <div key={wi} className="flex-1 rounded-lg border border-[#E5E5E5] bg-white p-3">
                <div className="text-[10px] font-medium text-[#B5B5B5] mb-1.5">Wave {wi + 1}</div>
                <div className="flex flex-wrap gap-1.5">
                  {wave.map((nodeId) => {
                    const node = currentDraft.nodes.find((n) => n.id.trim() === nodeId)
                    const hasError = node && currentDraft.nodes.indexOf(node) !== -1 && nodeErrorSet.has(currentDraft.nodes.indexOf(node))
                    return (
                      <span
                        key={nodeId}
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                          hasError
                            ? "bg-red-50 text-red-500 border border-red/20"
                            : "bg-[#F4F3EF] text-[#5A5A5A] border border-[#E5E5E5]"
                        )}
                      >
                        {node?.title || nodeId}
                      </span>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
          {/* Edges in preview */}
          {currentDraft.edges.some((e) => e.from_node.trim() && e.to_node.trim()) && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {currentDraft.edges.map((e, i) => {
                if (!e.from_node.trim() || !e.to_node.trim()) return null
                const hasError = edgeErrorSet.has(i)
                return (
                  <span
                    key={i}
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono",
                      hasError
                        ? "bg-red-50 text-red-500 border border-red/20"
                        : "bg-[#F4F3EF] text-[#6B6B6B] border border-[#E5E5E5]"
                    )}
                  >
                    {e.from_node.trim()}
                    <span className="text-[#B5B5B5]">→</span>
                    {e.to_node.trim()}
                    {e.handoff_type.trim() && e.handoff_type.trim() !== "context" && (
                      <span className="text-[10px] text-[#8A8A8A]">({e.handoff_type.trim()})</span>
                    )}
                  </span>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Action buttons ── */}
      <div className="flex items-center gap-2 mb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={addNode}
          disabled={disabled}
          className="gap-1 text-xs h-7"
        >
          <Plus className="h-3 w-3" />
          添加节点
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={addEdge}
          disabled={disabled}
          className="gap-1 text-xs h-7"
        >
          <Plus className="h-3 w-3" />
          添加边
        </Button>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={undo}
            disabled={disabled || !history.canUndo}
            title="撤销 (Ctrl+Z)"
            data-testid="undo-btn"
            className="h-7 w-7 p-0"
          >
            <Undo2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={redo}
            disabled={disabled || !history.canRedo}
            title="重做 (Ctrl+Y)"
            data-testid="redo-btn"
            className="h-7 w-7 p-0"
          >
            <Redo2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* ── Node list ── */}
      <div className="mb-4">
        <h5 className="text-xs font-medium text-[#8A8A8A] mb-2">节点 / Nodes</h5>
        {currentDraft.nodes.length === 0 ? (
          <p className="text-xs text-[#B5B5B5]">暂无节点，点击「添加节点」开始。</p>
        ) : (
          <div className="space-y-1.5">
            {currentDraft.nodes.map((node, ni) => {
              const isEditing = editingNodeId === ni
              const hasError = nodeErrorSet.has(ni)
              return (
                <div
                  key={ni}
                  data-testid={`node-card-${ni}`}
                  className={cn(
                    "rounded-lg border transition-all",
                    hasError ? "border-red/30 bg-red/5" : "border-[#E5E5E5] bg-white",
                    isEditing && "ring-1 ring-primary/30"
                  )}
                >
                  {/* Header row — always visible */}
                  <div
                    className="flex items-center gap-2 px-3 py-2 cursor-pointer select-none"
                    onClick={() => setEditingNodeId(isEditing ? null : ni)}
                  >
                    {isEditing ? (
                      <ChevronDown className="h-3.5 w-3.5 text-[#8A8A8A] shrink-0" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-[#B5B5B5] shrink-0" />
                    )}
                    <span className="text-xs font-medium text-[#0B0B0B] font-mono">
                      {node.id.trim() || `(空 #${ni + 1})`}
                    </span>
                    {node.title.trim() && (
                      <span className="text-xs text-[#8A8A8A] truncate">{node.title.trim()}</span>
                    )}
                    {node.agent_id.trim() && node.agent_id.trim() !== node.id.trim() && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0">{node.agent_id.trim()}</Badge>
                    )}
                    <div className="ml-auto flex items-center gap-1">
                      {!isEditing && (
                        <Pencil className="h-3 w-3 text-[#B5B5B5]" />
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); removeNode(ni) }}
                        disabled={disabled}
                        data-testid={`delete-node-${ni}`}
                        className="h-6 w-6 p-0 text-[#B5B5B5] hover:text-red-500"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>

                  {/* Expanded edit form */}
                  {isEditing && (
                    <div className="px-3 pb-3 pt-1 border-t border-[#F0F0EC]">
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">id *</label>
                          <input
                            type="text"
                            value={node.id}
                            onChange={(e) => updateNode(ni, "id", e.target.value)}
                            disabled={disabled}
                            data-testid={`node-id-input-${ni}`}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] font-mono"
                            placeholder="node_id"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">agent_id *</label>
                          <input
                            type="text"
                            list="dag-common-agents"
                            value={node.agent_id}
                            onChange={(e) => updateNode(ni, "agent_id", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] font-mono"
                            placeholder="agent_id"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">task_type</label>
                          <input
                            type="text"
                            value={node.task_type}
                            onChange={(e) => updateNode(ni, "task_type", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                            placeholder="general"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">title</label>
                          <input
                            type="text"
                            value={node.title}
                            onChange={(e) => updateNode(ni, "title", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                            placeholder="节点标题"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">prompt</label>
                          <textarea
                            value={node.prompt}
                            onChange={(e) => updateNode(ni, "prompt", e.target.value)}
                            disabled={disabled}
                            rows={2}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] resize-none"
                            placeholder="节点提示词"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Edge list ── */}
      <div className="mb-4">
        <h5 className="text-xs font-medium text-[#8A8A8A] mb-2">边 / Edges</h5>
        {currentDraft.edges.length === 0 ? (
          <p className="text-xs text-[#B5B5B5]">暂无边（节点将并行执行）</p>
        ) : (
          <div className="space-y-1.5">
            {currentDraft.edges.map((edge, ei) => {
              const isEditing = editingEdgeIdx === ei
              const hasError = edgeErrorSet.has(ei)
              const from = edge.from_node.trim()
              const to = edge.to_node.trim()
              return (
                <div
                  key={ei}
                  className={cn(
                    "rounded-lg border transition-all",
                    hasError ? "border-red/30 bg-red/5" : "border-[#E5E5E5] bg-white",
                    isEditing && "ring-1 ring-primary/30"
                  )}
                >
                  {/* Header row */}
                  <div
                    className="flex items-center gap-2 px-3 py-2 cursor-pointer select-none"
                    onClick={() => setEditingEdgeIdx(isEditing ? null : ei)}
                  >
                    {isEditing ? (
                      <ChevronDown className="h-3.5 w-3.5 text-[#8A8A8A] shrink-0" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-[#B5B5B5] shrink-0" />
                    )}
                    <span className="text-xs font-mono text-[#0B0B0B]">
                      {from || "?"}
                      <span className="text-[#B5B5B5] mx-1">→</span>
                      {to || "?"}
                    </span>
                    {edge.handoff_type.trim() && edge.handoff_type.trim() !== "context" && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0">{edge.handoff_type.trim()}</Badge>
                    )}
                    <div className="ml-auto flex items-center gap-1">
                      {!isEditing && (
                        <Pencil className="h-3 w-3 text-[#B5B5B5]" />
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); removeEdge(ei) }}
                        disabled={disabled}
                        className="h-6 w-6 p-0 text-[#B5B5B5] hover:text-red-500"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>

                  {/* Expanded edit form */}
                  {isEditing && (
                    <div className="px-3 pb-3 pt-1 border-t border-[#F0F0EC]">
                      <div className="grid gap-2 sm:grid-cols-3">
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">from_node *</label>
                          <select
                            value={edge.from_node}
                            onChange={(e) => updateEdge(ei, "from_node", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] font-mono"
                          >
                            <option value="">-- 选择节点 --</option>
                            {nodeIds.map((id) => (
                              <option key={id} value={id}>{id}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">to_node *</label>
                          <select
                            value={edge.to_node}
                            onChange={(e) => updateEdge(ei, "to_node", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] font-mono"
                          >
                            <option value="">-- 选择节点 --</option>
                            {nodeIds.map((id) => (
                              <option key={id} value={id}>{id}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] text-[#B5B5B5] mb-0.5">handoff_type</label>
                          <input
                            type="text"
                            value={edge.handoff_type}
                            onChange={(e) => updateEdge(ei, "handoff_type", e.target.value)}
                            disabled={disabled}
                            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
                            placeholder="context"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Validation errors ── */}
      {errorMessages.length > 0 && (
        <div className="rounded-lg border border-red/20 bg-red/5 p-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-red-500" />
            <span className="text-xs font-medium text-red-500">校验错误</span>
          </div>
          <ul className="space-y-0.5">
            {errorMessages.map((message, i) => (
              <li key={i} className="text-xs text-red-500">{message}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Shared datalist for agent_id autocomplete */}
      <datalist id="dag-common-agents">
        {COMMON_AGENTS.map((a) => (
          <option key={a.id} value={a.id}>{a.label}</option>
        ))}
      </datalist>
    </div>
  )
}

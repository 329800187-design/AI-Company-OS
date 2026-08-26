import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  ReactFlowProvider,
  type NodeProps,
  type EdgeProps,
  BaseEdge,
  getBezierPath,
  useReactFlow,
  useOnSelectionChange,
  type Connection,
  type FinalConnectionState,
  type OnConnectStartParams,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "@dagrejs/dagre"
import { GitBranch, Cable, X, Trash2, Plus, LayoutGrid, Search } from "lucide-react"
import { canConnectEdge } from "./dag-validation"

// ── Types ──────────────────────────────────────────────────────

interface DagCanvasNode {
  id: string
  agent_id: string
  title: string
  task_type: string
  prompt: string
}

interface DagCanvasEdge {
  from_node: string
  to_node: string
  handoff_type: string
}

export interface DagCanvasProps {
  nodes: DagCanvasNode[]
  edges: DagCanvasEdge[]
  className?: string
  editable?: boolean
  onChange?: (nodes: DagCanvasNode[], edges: DagCanvasEdge[]) => void
  /** localStorage key for persisting node positions (view-only). Omit to disable persistence. */
  layoutStorageKey?: string
  /** Backend-persisted canvas layout (takes priority over localStorage). */
  canvasLayout?: Record<string, { x: number; y: number }>
  /** Called after a drag-stop layout change (debounced). Used to persist to backend. */
  onLayoutChange?: (layout: Record<string, { x: number; y: number }>) => void
  /** Called when the user batch-deletes selected nodes. */
  onBatchDelete?: (selectedNodeIds: string[]) => void
}

type SelectedInfo =
  | { type: "node"; node: DagCanvasNode; inCount: number; outCount: number }
  | { type: "edge"; edge: DagCanvasEdge }

// ── Dagre layout helper ───────────────────────────────────────

const NODE_WIDTH = 180
const NODE_HEIGHT = 60

/** Compute dagre positions for all nodes (used for initialization and auto-layout) */
function computeDagrePositions(
  rawNodes: DagCanvasNode[],
  rawEdges: DagCanvasEdge[],
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 80 })
  for (const n of rawNodes) g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  const nodeIds = new Set(rawNodes.map((n) => n.id))
  for (const e of rawEdges) {
    if (e.from_node && e.to_node && nodeIds.has(e.from_node) && nodeIds.has(e.to_node)) {
      g.setEdge(e.from_node, e.to_node)
    }
  }
  dagre.layout(g)
  const posMap = new Map<string, { x: number; y: number }>()
  for (const n of rawNodes) {
    const p = g.node(n.id)
    posMap.set(n.id, { x: p.x - NODE_WIDTH / 2, y: p.y - NODE_HEIGHT / 2 })
  }
  return posMap
}

function computeLayout(
  rawNodes: DagCanvasNode[],
  rawEdges: DagCanvasEdge[],
  editable: boolean | undefined,
  positions: Map<string, { x: number; y: number }>,
): { nodes: Node[]; edges: Edge[]; layoutHeight: number } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 80 })

  for (const n of rawNodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  const nodeIds = new Set(rawNodes.map((n) => n.id))
  for (const e of rawEdges) {
    if (e.from_node && e.to_node && nodeIds.has(e.from_node) && nodeIds.has(e.to_node)) {
      g.setEdge(e.from_node, e.to_node)
    }
  }

  dagre.layout(g)

  const graphHeight = g.graph().height ?? 0

  const nodes: Node[] = rawNodes.map((n) => {
    const dagrePos = g.node(n.id)
    const saved = positions.get(n.id)
    const x = saved ? saved.x : dagrePos.x - NODE_WIDTH / 2
    const y = saved ? saved.y : dagrePos.y - NODE_HEIGHT / 2
    return {
      id: n.id,
      position: { x, y },
      data: { label: n.title || n.id, sublabel: n.agent_id || "", editable },
      type: "dagCanvasNode",
      draggable: !!editable,
      selectable: true,
    }
  })

  const edges: Edge[] = rawEdges.map((e, i) => ({
    id: `e-${e.from_node}-${e.to_node}-${i}`,
    source: e.from_node,
    target: e.to_node,
    type: "dagCanvasEdge",
    data: { testid: `edge-${e.from_node}-${e.to_node}`, rawEdge: e },
  }))

  return { nodes, edges, layoutHeight: graphHeight }
}

// ── Custom node component ─────────────────────────────────────

const DagCanvasNodeComponent = (props: NodeProps) => {
  const data = props.data as Record<string, unknown>
  const label = (data.label as string) || ""
  const sublabel = (data.sublabel as string) || ""
  const isEditable = (data.editable as boolean) || false
  const handleStyle = isEditable
    ? { width: 8, height: 8, background: "#B5B5B5", border: "2px solid white", opacity: 0.7 }
    : { visibility: "hidden" as const }
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <div
        className={`rounded-xl border bg-white px-4 py-2.5 shadow-sm min-w-[140px] text-center cursor-pointer transition-shadow ${
          props.selected
            ? "border-[#0B0B0B] ring-2 ring-[#0B0B0B]"
            : "border-[#E5E5E5]"
        }`}
      >
        <div className="text-sm font-medium text-[#0B0B0B] truncate">
          {label}
        </div>
        {sublabel && (
          <div className="text-[10px] font-mono text-[#8A8A8A] mt-0.5 truncate">
            {sublabel}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  )
}

// ── Custom edge component ─────────────────────────────────────

function DagCanvasEdgeComponent(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition } = props
  const [edgePath] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
  const testid = (props.data as Record<string, unknown>)?.testid as string

  return (
    <>
      {/* Invisible wide path for click hit area */}
      <path d={edgePath} fill="none" stroke="rgba(0,0,0,0.001)" strokeWidth={20} data-testid={testid} />
      <BaseEdge {...props} path={edgePath} />
    </>
  )
}

const nodeTypes = { dagCanvasNode: DagCanvasNodeComponent }
const edgeTypes = { dagCanvasEdge: DagCanvasEdgeComponent }

// ── Detail Panel ──────────────────────────────────────────────

function DetailPanel({
  selected,
  onClose,
  editable,
  onNodeFieldChange,
  onEdgeFieldChange,
  onDeleteNode,
  onDeleteEdge,
}: {
  selected: SelectedInfo | null
  onClose: () => void
  editable?: boolean
  onNodeFieldChange?: (nodeId: string, field: keyof DagCanvasNode, value: string) => void
  onEdgeFieldChange?: (from: string, to: string, field: keyof DagCanvasEdge, value: string) => void
  onDeleteNode?: (nodeId: string) => void
  onDeleteEdge?: (from: string, to: string) => void
}) {
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  if (!selected) return null

  return (
    <div
      data-testid="dag-detail-panel"
      className="mt-2 rounded-xl border border-[#E5E5E5] bg-white p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[#0B0B0B]">
          {selected.type === "node" ? "节点属性 / Node" : "边属性 / Edge"}
        </h4>
        <button
          type="button"
          data-testid="detail-panel-close"
          onClick={onClose}
          className="p-1 rounded hover:bg-[#F4F3EF] text-[#8A8A8A] hover:text-[#0B0B0B] transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {selected.type === "node" && editable && (
        <div className="space-y-2 text-sm">
          <EditableDetailRow label="id" value={selected.node.id} mono disabled />
          <EditableDetailRow
            label="agent_id"
            value={selected.node.agent_id}
            mono
            identityKey={`${selected.node.id}-agent_id`}
            onChange={(v) => onNodeFieldChange?.(selected.node.id, "agent_id", v)}
          />
          <EditableDetailRow
            label="title"
            value={selected.node.title}
            identityKey={`${selected.node.id}-title`}
            onChange={(v) => onNodeFieldChange?.(selected.node.id, "title", v)}
          />
          <EditableDetailRow
            label="task_type"
            value={selected.node.task_type}
            mono
            identityKey={`${selected.node.id}-task_type`}
            onChange={(v) => onNodeFieldChange?.(selected.node.id, "task_type", v)}
          />
          <EditableDetailRow
            label="prompt"
            value={selected.node.prompt}
            textarea
            identityKey={`${selected.node.id}-prompt`}
            onChange={(v) => onNodeFieldChange?.(selected.node.id, "prompt", v)}
          />
          <DetailRow label="入边数量" value={String(selected.inCount)} />
          <DetailRow label="出边数量" value={String(selected.outCount)} />
          <div className="pt-2 border-t border-[#F0F0EC]">
            {!deleteConfirm ? (
              <button
                type="button"
                data-testid="canvas-delete-node-btn"
                onClick={() => setDeleteConfirm(true)}
                className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 transition-colors"
              >
                <Trash2 className="h-3 w-3" />
                删除节点
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#8A8A8A]">
                  删除 {selected.node.title || selected.node.id}？关联的 {selected.inCount + selected.outCount} 条边也会移除。
                </span>
                <button
                  type="button"
                  data-testid="canvas-confirm-delete-node"
                  onClick={() => {
                    onDeleteNode?.(selected.node.id)
                    setDeleteConfirm(false)
                    onClose()
                  }}
                  className="text-xs text-red-500 hover:text-red-700 font-medium"
                >
                  确认
                </button>
                <button
                  type="button"
                  data-testid="canvas-cancel-delete-node"
                  onClick={() => setDeleteConfirm(false)}
                  className="text-xs text-[#8A8A8A] hover:text-[#0B0B0B]"
                >
                  取消
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {selected.type === "node" && !editable && (
        <div className="space-y-2 text-sm">
          <DetailRow label="id" value={selected.node.id} mono />
          <DetailRow label="agent_id" value={selected.node.agent_id} mono />
          <DetailRow label="task_type" value={selected.node.task_type} mono />
          <DetailRow label="title" value={selected.node.title} />
          <DetailRow label="prompt" value={selected.node.prompt} />
          <DetailRow label="入边数量" value={String(selected.inCount)} />
          <DetailRow label="出边数量" value={String(selected.outCount)} />
        </div>
      )}

      {selected.type === "edge" && editable && (
        <div className="space-y-2 text-sm">
          <DetailRow label="from_node" value={selected.edge.from_node} mono />
          <DetailRow label="to_node" value={selected.edge.to_node} mono />
          <EditableDetailRow
            label="handoff_type"
            value={selected.edge.handoff_type}
            mono
            identityKey={`${selected.edge.from_node}-${selected.edge.to_node}-handoff_type`}
            onChange={(v) =>
              onEdgeFieldChange?.(selected.edge.from_node, selected.edge.to_node, "handoff_type", v)
            }
          />
          <div className="pt-2 border-t border-[#F0F0EC]">
            <button
              type="button"
              data-testid="canvas-delete-edge-btn"
              onClick={() => {
                onDeleteEdge?.(selected.edge.from_node, selected.edge.to_node)
                onClose()
              }}
              className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 transition-colors"
            >
              <Trash2 className="h-3 w-3" />
              删除边
            </button>
          </div>
        </div>
      )}

      {selected.type === "edge" && !editable && (
        <div className="space-y-2 text-sm">
          <DetailRow label="from_node" value={selected.edge.from_node} mono />
          <DetailRow label="to_node" value={selected.edge.to_node} mono />
          <DetailRow label="handoff_type" value={selected.edge.handoff_type} mono />
        </div>
      )}
    </div>
  )
}

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string
  value?: string
  mono?: boolean
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-0.5 sm:gap-3">
      <span className="shrink-0 text-[#8A8A8A] sm:w-24">{label}</span>
      <span className={mono ? "font-mono text-[#0B0B0B] break-all min-w-0" : "text-[#0B0B0B] break-all min-w-0"}>
        {value || <span className="text-[#B5B5B5]">—</span>}
      </span>
    </div>
  )
}

function EditableDetailRow({
  label,
  value,
  mono,
  textarea,
  disabled,
  identityKey,
  onChange,
}: {
  label: string
  value?: string
  mono?: boolean
  textarea?: boolean
  disabled?: boolean
  identityKey?: string
  onChange?: (value: string) => void
}) {
  const [localValue, setLocalValue] = useState(value ?? "")
  const prevKeyRef = useRef(identityKey)

  // Reset local state when identityKey changes (different node/edge selected)
  useEffect(() => {
    if (identityKey !== prevKeyRef.current) {
      prevKeyRef.current = identityKey
      setLocalValue(value ?? "")
    }
  }, [identityKey, value])

  const commit = () => {
    if (onChange && localValue !== (value ?? "")) {
      onChange(localValue)
    }
  }

  if (disabled || !onChange) {
    return (
      <div className="flex flex-col sm:flex-row sm:items-start gap-0.5 sm:gap-3">
        <span className="shrink-0 text-[#8A8A8A] sm:w-24">{label}</span>
        <span className={mono ? "font-mono text-[#0B0B0B] break-all min-w-0" : "text-[#0B0B0B] break-all min-w-0"}>
          {value || <span className="text-[#B5B5B5]">—</span>}
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-0.5 sm:gap-3">
      <span className="shrink-0 text-[#8A8A8A] sm:w-24 pt-0 sm:pt-1">{label}</span>
      {textarea ? (
        <textarea
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={commit}
          rows={3}
          data-testid={`canvas-edit-${label}`}
          className="flex-1 min-w-0 rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5] resize-none"
        />
      ) : (
        <input
          type="text"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={commit}
          data-testid={`canvas-edit-${label}`}
          className={
            mono
              ? "flex-1 min-w-0 rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs font-mono text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
              : "flex-1 min-w-0 rounded border border-[#E5E5E5] bg-white px-2 py-1 text-xs text-[#0B0B0B] focus:outline-none focus:border-[#B5B5B5]"
          }
        />
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────

function DagCanvasInner({ nodes, edges, className, editable, onChange, layoutStorageKey, canvasLayout, onLayoutChange }: DagCanvasProps) {
  const [selected, setSelected] = useState<SelectedInfo | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectionStartRef = useRef<OnConnectStartParams | null>(null)
  const { fitView, setCenter } = useReactFlow()

  // ── Node position state (view-only, not saved to draft) ──
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(new Map())
  const [layoutCounter, setLayoutCounter] = useState(0)
  const wasDraggedRef = useRef(false)
  const dragStartPosRef = useRef<{ x: number; y: number } | null>(null)
  const dragClickSuppressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const locateSkipFitRef = useRef(false)

  // ── Multi-select state (for batch operations) ──
  const flowSelectedNodeIdsRef = useRef<string[]>([])
  const [flowSelectedNodeIds, setFlowSelectedNodeIds] = useState<string[]>([])

  const showError = useCallback((msg: string) => {
    setConnectionError(msg)
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setConnectionError(null), 3000)
  }, [])

  useEffect(() => {
    return () => {
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current)
      if (dragClickSuppressTimerRef.current) clearTimeout(dragClickSuppressTimerRef.current)
    }
  }, [])

  // Initialize/reset positions when graph structure changes
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      if (nodes.length === 0) {
        setPositions(new Map())
        return
      }

      const dagrePos = computeDagrePositions(nodes, edges)
      setPositions((prev) => {
        const next = new Map<string, { x: number; y: number }>()
        for (const n of nodes) {
          const existing = prev.get(n.id)
          const dagre = dagrePos.get(n.id)
          next.set(n.id, existing ?? dagre ?? { x: 0, y: 0 })
        }
        return next
      })
    }, 0)

    return () => window.clearTimeout(timeoutId)
  }, [nodes, edges])

  // Restore saved positions: backend layout (priority) → localStorage (fallback)
  const storageKeyRef = useRef(layoutStorageKey)
  const prevCanvasLayoutJsonRef = useRef(canvasLayout ? JSON.stringify(canvasLayout) : null)
  useEffect(() => {
    storageKeyRef.current = layoutStorageKey
  }, [layoutStorageKey])

  // Apply backend canvasLayout when it changes (highest priority)
  // Uses JSON deep-equal to avoid re-applying after PATCH returns same values in new object
  useEffect(() => {
    if (!canvasLayout || Object.keys(canvasLayout).length === 0) return
    const json = JSON.stringify(canvasLayout)
    if (prevCanvasLayoutJsonRef.current === json) return
    prevCanvasLayoutJsonRef.current = json
    const nodeIds = new Set(nodes.map((n) => n.id))
    setPositions((prev) => {
      const next = new Map(prev)
      for (const [id, pos] of Object.entries(canvasLayout)) {
        if (nodeIds.has(id) && typeof pos?.x === "number" && typeof pos?.y === "number") {
          next.set(id, pos)
        }
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvasLayout, nodes.length])

  // On mount / key change: apply backend layout first, then localStorage fallback
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const nodeIds = new Set(nodes.map((n) => n.id))
      // Priority 1: backend layout
      if (canvasLayout && Object.keys(canvasLayout).length > 0) {
        setPositions((prev) => {
          const next = new Map(prev)
          for (const [id, pos] of Object.entries(canvasLayout)) {
            if (nodeIds.has(id) && typeof pos?.x === "number" && typeof pos?.y === "number") {
              next.set(id, pos)
            }
          }
          return next
        })
        return
      }

      // Priority 2: localStorage fallback
      if (!layoutStorageKey) return
      try {
        const raw = localStorage.getItem(layoutStorageKey)
        if (!raw) return
        const saved = JSON.parse(raw) as Record<string, { x: number; y: number }>
        setPositions((prev) => {
          const next = new Map(prev)
          for (const [id, pos] of Object.entries(saved)) {
            if (nodeIds.has(id) && typeof pos?.x === "number" && typeof pos?.y === "number") {
              next.set(id, pos)
            }
          }
          return next
        })
      } catch {
        // Corrupt entry: keep Dagre's defaults.
      }
    }, 0)

    return () => window.clearTimeout(timeoutId)
    // Run once on mount / when key or node set changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutStorageKey, nodes.length])

  const { flowNodes, flowEdges, canvasHeight } = useMemo(() => {
    if (nodes.length === 0) return { flowNodes: [], flowEdges: [], canvasHeight: 256 }
    const result = computeLayout(nodes, edges, editable, positions)
    const height = Math.max(256, Math.min(600, result.layoutHeight + 120))
    const selectedNodeId = selected?.type === "node" ? selected.node.id : null
    const selectedEdge = selected?.type === "edge" ? selected.edge : null
    // Preserve React Flow's internal multi-selection (set via onSelectionChange)
    // while also highlighting the detail-panel-selected node/edge
    const styledNodes = result.nodes.map((node) => ({
      ...node,
      selected: node.selected || node.id === selectedNodeId,
    }))
    const styledEdges = result.edges.map((edge) => {
      const raw = edge.data?.rawEdge as DagCanvasEdge | undefined
      return {
        ...edge,
        selected: edge.selected || (!!selectedEdge && raw?.from_node === selectedEdge.from_node && raw?.to_node === selectedEdge.to_node),
      }
    })
    return { flowNodes: styledNodes, flowEdges: styledEdges, canvasHeight: height }
    // layoutCounter forces recompute when auto-layout is triggered
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, editable, positions, layoutCounter, selected])

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  // ── Node drag handlers (position saved locally, no undo/redo) ──

  const handleNodeDragStart = useCallback(
    (_event: globalThis.MouseEvent | globalThis.TouchEvent, node: Node) => {
      const pos = positions.get(node.id)
      dragStartPosRef.current = pos ? { ...pos } : { ...node.position }
      wasDraggedRef.current = false
    },
    [positions],
  )

  const handleNodeDragStop = useCallback(
    (_event: globalThis.MouseEvent | globalThis.TouchEvent, node: Node) => {
      const startPos = dragStartPosRef.current
      dragStartPosRef.current = null
      if (!startPos) return
      const dx = Math.abs(node.position.x - startPos.x)
      const dy = Math.abs(node.position.y - startPos.y)
      if (dx < 3 && dy < 3) return // not a real drag
      wasDraggedRef.current = true
      if (dragClickSuppressTimerRef.current) clearTimeout(dragClickSuppressTimerRef.current)
      dragClickSuppressTimerRef.current = setTimeout(() => {
        wasDraggedRef.current = false
      }, 150)
      setPositions((prev) => {
        const next = new Map(prev)
        next.set(node.id, { ...node.position })
        // Persist to localStorage (view-only, no undo/redo history)
        const key = storageKeyRef.current
        if (key) {
          try {
            const obj: Record<string, { x: number; y: number }> = {}
            for (const [id, pos] of next) obj[id] = pos
            localStorage.setItem(key, JSON.stringify(obj))
          } catch { /* quota exceeded — ignore */ }
        }
        // Notify parent for backend persistence
        if (onLayoutChange) {
          const layoutObj: Record<string, { x: number; y: number }> = {}
          for (const [id, pos] of next) layoutObj[id] = pos
          onLayoutChange(layoutObj)
        }
        return next
      })
    },
    [onLayoutChange],
  )

  // ── Auto-layout (reset all positions to dagre, clear saved layout) ──

  const handleAutoLayout = useCallback(() => {
    const dagrePos = computeDagrePositions(nodes, edges)
    setPositions(dagrePos)
    setLayoutCounter((c) => c + 1)
    // Clear saved layout so future opens use dagre defaults
    const key = storageKeyRef.current
    if (key) {
      try { localStorage.removeItem(key) } catch { /* ignore */ }
    }
    // Notify parent: clear backend layout (empty object = use dagre defaults)
    if (onLayoutChange) {
      onLayoutChange({})
    }
  }, [nodes, edges, onLayoutChange])

  // ── Node locate (center + select from dropdown) ──

  const handleLocateNodeSelect = useCallback(
    (nodeId: string) => {
      if (!nodeId) return
      const rfNode = flowNodes.find((n) => n.id === nodeId)
      if (!rfNode) return
      const cx = rfNode.position.x + NODE_WIDTH / 2
      const cy = rfNode.position.y + NODE_HEIGHT / 2
      setCenter(cx, cy, { zoom: 1.5, duration: 400 })
      locateSkipFitRef.current = true
      const raw = nodeMap.get(nodeId)
      if (!raw) return
      const inCount = edges.filter((e) => e.to_node === nodeId).length
      const outCount = edges.filter((e) => e.from_node === nodeId).length
      setSelected({ type: "node", node: raw, inCount, outCount })
    },
    [flowNodes, nodeMap, edges, setCenter],
  )

  useEffect(() => {
    if (nodes.length === 0) return
    if (locateSkipFitRef.current) { locateSkipFitRef.current = false; return }
    const frame = requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 0 })
    })
    return () => cancelAnimationFrame(frame)
  }, [nodes, edges, fitView])

  const handleNodeClick = useCallback(
    (_event: MouseEvent, node: Node) => {
      if (wasDraggedRef.current) {
        wasDraggedRef.current = false
        return
      }
      const raw = nodeMap.get(node.id)
      if (!raw) return
      const inCount = edges.filter((e) => e.to_node === node.id).length
      const outCount = edges.filter((e) => e.from_node === node.id).length
      setSelected({ type: "node", node: raw, inCount, outCount })
    },
    [edges, nodeMap],
  )

  // ── Multi-select change handler ──

  useOnSelectionChange({
    onChange: ({ nodes: selNodes }) => {
      const ids = selNodes.map((n) => n.id)
      flowSelectedNodeIdsRef.current = ids
      setFlowSelectedNodeIds([...ids])
    },
  })

  // ── Batch delete handler ──

  const handleBatchDelete = useCallback(() => {
    const ids = flowSelectedNodeIdsRef.current
    if (ids.length <= 1 || !onChange) return
    const idSet = new Set(ids)
    const newNodes = nodes.filter((n) => !idSet.has(n.id))
    const newEdges = edges.filter((e) => !idSet.has(e.from_node) && !idSet.has(e.to_node))
    onChange(newNodes, newEdges)
    flowSelectedNodeIdsRef.current = []
    setFlowSelectedNodeIds([])
    setSelected(null)
  }, [onChange, nodes, edges])

  const handleEdgeClick = useCallback(
    (_event: MouseEvent, edge: Edge) => {
      // Read from stored raw edge data instead of parsing the ID
      const raw = (edge.data as Record<string, unknown>)?.rawEdge as DagCanvasEdge | undefined
      if (raw) {
        setSelected({ type: "edge", edge: raw })
        return
      }
      // Fallback: use edge.source / edge.target (works with any node ID)
      const found = edges.find((e) => e.from_node === edge.source && e.to_node === edge.target)
      if (found) {
        setSelected({ type: "edge", edge: found })
      }
    },
    [edges],
  )

  const handlePaneClick = useCallback(() => {
    setSelected(null)
    flowSelectedNodeIdsRef.current = []
    setFlowSelectedNodeIds([])
  }, [])

  const handleClose = useCallback(() => {
    setSelected(null)
  }, [])

  // ── Connect handler (drag-to-create edge) ──

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!onChange || !editable) return
      const source = connection.source
      const target = connection.target
      if (!source || !target) return
      const nodeIds = nodes.map((n) => n.id)
      const err = canConnectEdge(source, target, edges, nodeIds)
      if (err) {
        showError(err)
        return
      }
      const newEdge: DagCanvasEdge = {
        from_node: source,
        to_node: target,
        handoff_type: "context",
      }
      onChange(nodes, [...edges, newEdge])
    },
    [onChange, editable, nodes, edges, showError],
  )

  const showConnectionError = useCallback(
    (source: string, target: string) => {
      const nodeIds = nodes.map((n) => n.id)
      const err = canConnectEdge(source, target, edges, nodeIds)
      if (err) showError(err)
      return err
    },
    [nodes, edges, showError],
  )

  const handleConnectStart = useCallback(
    (_event: globalThis.MouseEvent | globalThis.TouchEvent, params: OnConnectStartParams) => {
      if (!editable) return
      connectionStartRef.current = params
    },
    [editable],
  )

  const handleIsValidConnection = useCallback(
    (connection: Connection | Edge) => {
      if (!editable) return false
      const source = connection.source
      const target = connection.target
      if (!source || !target) return false
      const nodeIds = nodes.map((n) => n.id)
      const err = canConnectEdge(source, target, edges, nodeIds)
      if (err) {
        showError(err)
        return false
      }
      return true
    },
    [editable, nodes, edges, showError],
  )

  const handleConnectEnd = useCallback(
    (_event: globalThis.MouseEvent | globalThis.TouchEvent, connectionState: FinalConnectionState) => {
      if (!editable || connectionState.isValid !== false) return
      const fromHandle = connectionState.fromHandle
      const toHandle = connectionState.toHandle
      if (!fromHandle || !toHandle) return

      const source = fromHandle.type === "source" ? fromHandle.nodeId : toHandle.nodeId
      const target = fromHandle.type === "source" ? toHandle.nodeId : fromHandle.nodeId
      showConnectionError(source, target)
    },
    [editable, showConnectionError],
  )

  const handleCanvasMouseUpCapture = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (!editable) return
      const start = connectionStartRef.current
      connectionStartRef.current = null
      if (!start?.nodeId) return

      const target = event.target as HTMLElement | null
      const handle = target?.closest(".react-flow__handle") as HTMLElement | null
      const targetNodeId = handle?.dataset.nodeid
      if (!targetNodeId) return

      const startIsSource = start.handleType === "source"
      const source = startIsSource ? start.nodeId : targetNodeId
      const to = startIsSource ? targetNodeId : start.nodeId
      showConnectionError(source, to)
    },
    [editable, showConnectionError],
  )

  // ── Add node handler ──

  const handleAddCanvasNode = useCallback(() => {
    if (!onChange) return
    const existingIds = new Set(nodes.map((n) => n.id))
    let n = nodes.length + 1
    while (existingIds.has(`node_${n}`)) n++
    const newNode: DagCanvasNode = {
      id: `node_${n}`,
      agent_id: "",
      task_type: "",
      title: "新节点",
      prompt: "",
    }
    onChange([...nodes, newNode], edges)
  }, [onChange, nodes, edges])

  // ── Edit handlers ──

  const handleNodeFieldChange = useCallback(
    (nodeId: string, field: keyof DagCanvasNode, value: string) => {
      if (!onChange) return
      const updated = nodes.map((n) =>
        n.id === nodeId ? { ...n, [field]: value } : n,
      )
      onChange(updated, edges)
      // Update selected state to reflect the change
      setSelected((prev) => {
        if (prev?.type === "node" && prev.node.id === nodeId) {
          return { ...prev, node: { ...prev.node, [field]: value } }
        }
        return prev
      })
    },
    [nodes, edges, onChange],
  )

  const handleEdgeFieldChange = useCallback(
    (from: string, to: string, field: keyof DagCanvasEdge, value: string) => {
      if (!onChange) return
      const updated = edges.map((e) =>
        e.from_node === from && e.to_node === to ? { ...e, [field]: value } : e,
      )
      onChange(nodes, updated)
      setSelected((prev) => {
        if (prev?.type === "edge" && prev.edge.from_node === from && prev.edge.to_node === to) {
          return { ...prev, edge: { ...prev.edge, [field]: value } }
        }
        return prev
      })
    },
    [nodes, edges, onChange],
  )

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      if (!onChange) return
      const newNodes = nodes.filter((n) => n.id !== nodeId)
      const newEdges = edges.filter((e) => e.from_node !== nodeId && e.to_node !== nodeId)
      onChange(newNodes, newEdges)
      setSelected(null)
    },
    [nodes, edges, onChange],
  )

  const handleDeleteEdge = useCallback(
    (from: string, to: string) => {
      if (!onChange) return
      const newEdges = edges.filter((e) => !(e.from_node === from && e.to_node === to))
      onChange(nodes, newEdges)
      setSelected(null)
    },
    [nodes, edges, onChange],
  )

  // Keyboard Delete/Backspace to delete selected element
  useEffect(() => {
    if (!editable || !onChange) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return
      // Ignore when focus is in an input/textarea
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return
      if (!selected) return

      if (selected.type === "node") {
        handleDeleteNode(selected.node.id)
      } else if (selected.type === "edge") {
        handleDeleteEdge(selected.edge.from_node, selected.edge.to_node)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [editable, onChange, selected, handleDeleteNode, handleDeleteEdge])

  // Empty state: no nodes
  if (nodes.length === 0) {
    return (
      <div
        data-testid="dag-canvas"
        className={
          className ||
          "h-64 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] flex items-center justify-center relative"
        }
      >
        <div className="flex flex-col items-center gap-2 text-[#B5B5B5]">
          <GitBranch className="h-8 w-8" />
          <span className="text-sm">暂无节点</span>
        </div>
        {editable && onChange && (
          <button
            type="button"
            data-testid="canvas-add-node-btn"
            onClick={handleAddCanvasNode}
            className="absolute top-2 left-3 flex items-center gap-1 rounded-md border border-[#E5E5E5] bg-white px-2 py-1 text-[11px] text-[#5A5A5A] shadow-sm hover:bg-[#F4F3EF] transition-colors"
          >
            <Plus className="h-3 w-3" />
            添加节点
          </button>
        )}
      </div>
    )
  }

  // Nodes but no edges
  const showEdgeHint = nodes.length > 0 && edges.length === 0

  return (
    <div className="flex flex-col">
      <div
        data-testid="dag-canvas"
        className={
          className ||
          "rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] relative"
        }
        style={className ? undefined : { height: canvasHeight }}
        onMouseUpCapture={handleCanvasMouseUpCapture}
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          nodesDraggable={!!editable}
          nodesConnectable={!!editable}
          elementsSelectable={true}
          onNodeClick={handleNodeClick}
          onNodeDragStart={handleNodeDragStart}
          onNodeDragStop={handleNodeDragStop}
          onEdgeClick={handleEdgeClick}
          onPaneClick={handlePaneClick}
          onConnectStart={handleConnectStart}
          onConnect={handleConnect}
          onConnectEnd={handleConnectEnd}
          isValidConnection={handleIsValidConnection}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#E5E5E5" gap={24} size={1} />
          <Controls
            showInteractive={false}
            position="bottom-right"
            style={{ borderRadius: 8, border: "1px solid #E5E5E5" }}
          />
          <MiniMap
            position="bottom-left"
            style={{ borderRadius: 8, border: "1px solid #E5E5E5", width: 140, height: 100 }}
            pannable
            zoomable
          />
        </ReactFlow>
        {showEdgeHint && (
          <div className="absolute top-2 right-3 flex items-center gap-1 text-[10px] text-[#B5B5B5]">
            <Cable className="h-3 w-3" />
            <span>无连线</span>
          </div>
        )}
        {editable && onChange && (
          <div className="absolute top-2 left-3 flex flex-wrap items-center gap-1.5 max-w-[calc(100%-80px)]">
            <button
              type="button"
              data-testid="canvas-add-node-btn"
              onClick={handleAddCanvasNode}
              className="flex items-center gap-1 rounded-md border border-[#E5E5E5] bg-white px-2 py-1 text-[11px] text-[#5A5A5A] shadow-sm hover:bg-[#F4F3EF] transition-colors whitespace-nowrap"
            >
              <Plus className="h-3 w-3" />
              添加节点
            </button>
            <button
              type="button"
              data-testid="canvas-auto-layout-btn"
              onClick={handleAutoLayout}
              className="flex items-center gap-1 rounded-md border border-[#E5E5E5] bg-white px-2 py-1 text-[11px] text-[#5A5A5A] shadow-sm hover:bg-[#F4F3EF] transition-colors whitespace-nowrap"
            >
              <LayoutGrid className="h-3 w-3" />
              自动布局
            </button>
            {nodes.length > 0 && (
              <div className="relative flex items-center">
                <Search className="absolute left-1.5 h-3 w-3 text-[#B5B5B5] pointer-events-none" />
                <select
                  data-testid="canvas-locate-node-select"
                  value=""
                  onChange={(e) => handleLocateNodeSelect(e.target.value)}
                  className="rounded-md border border-[#E5E5E5] bg-white pl-6 pr-2 py-1 text-[11px] text-[#5A5A5A] shadow-sm hover:bg-[#F4F3EF] transition-colors appearance-none cursor-pointer max-w-[140px] truncate"
                >
                  <option value="" disabled>定位节点…</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>{n.title || n.id}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
        {connectionError && (
          <div
            data-testid="canvas-connection-error"
            className="absolute bottom-14 left-1/2 -translate-x-1/2 z-10 rounded-md bg-red-50 border border-red/20 px-3 py-1.5 text-xs text-red-500 shadow-sm max-w-[80%] text-center"
          >
            {connectionError}
          </div>
        )}
        {editable && onChange && flowSelectedNodeIds.length > 1 && (
          <div
            data-testid="canvas-batch-toolbar"
            className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-3 py-1.5 shadow-sm"
          >
            <span className="text-[11px] text-[#5A5A5A]" data-testid="canvas-batch-count">
              已选中 {flowSelectedNodeIds.length} 个节点
            </span>
            <span className="text-[#E5E5E5]">|</span>
            <button
              type="button"
              data-testid="canvas-batch-delete-btn"
              onClick={handleBatchDelete}
              className="flex items-center gap-1 text-[11px] text-red-500 hover:text-red-700 transition-colors"
            >
              <Trash2 className="h-3 w-3" />
              批量删除
            </button>
          </div>
        )}
      </div>

      <DetailPanel
        selected={selected}
        onClose={handleClose}
        editable={editable}
        onNodeFieldChange={handleNodeFieldChange}
        onEdgeFieldChange={handleEdgeFieldChange}
        onDeleteNode={handleDeleteNode}
        onDeleteEdge={handleDeleteEdge}
      />
    </div>
  )
}

export function DagCanvas(props: DagCanvasProps) {
  return (
    <ReactFlowProvider>
      <DagCanvasInner {...props} />
    </ReactFlowProvider>
  )
}

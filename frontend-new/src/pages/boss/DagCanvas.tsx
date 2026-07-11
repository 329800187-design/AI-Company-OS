import { useCallback, useMemo, useState, type MouseEvent } from "react"
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
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "@dagrejs/dagre"
import { GitBranch, Cable, X } from "lucide-react"

// ── Types ──────────────────────────────────────────────────────

interface DagCanvasNode {
  id: string
  agent_id?: string
  title?: string
  task_type?: string
  prompt?: string
}

interface DagCanvasEdge {
  from_node: string
  to_node: string
  handoff_type?: string
}

export interface DagCanvasProps {
  nodes: DagCanvasNode[]
  edges: DagCanvasEdge[]
  className?: string
}

type SelectedInfo =
  | { type: "node"; node: DagCanvasNode; inCount: number; outCount: number }
  | { type: "edge"; edge: DagCanvasEdge }

// ── Dagre layout helper ───────────────────────────────────────

const NODE_WIDTH = 180
const NODE_HEIGHT = 60

function computeLayout(
  rawNodes: DagCanvasNode[],
  rawEdges: DagCanvasEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 80 })

  for (const n of rawNodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const e of rawEdges) {
    g.setEdge(e.from_node, e.to_node)
  }

  dagre.layout(g)

  const nodes: Node[] = rawNodes.map((n) => {
    const pos = g.node(n.id)
    return {
      id: n.id,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: { label: n.title || n.id, sublabel: n.agent_id || "" },
      type: "dagCanvasNode",
      draggable: false,
      selectable: true,
    }
  })

  const edges: Edge[] = rawEdges.map((e, i) => ({
    id: `e-${e.from_node}-${e.to_node}-${i}`,
    source: e.from_node,
    target: e.to_node,
  }))

  return { nodes, edges }
}

// ── Custom node component ─────────────────────────────────────

const DagCanvasNodeComponent = (props: NodeProps) => {
  const data = props.data as Record<string, unknown>
  const label = (data.label as string) || ""
  const sublabel = (data.sublabel as string) || ""
  return (
    <>
      <Handle type="target" position={Position.Left} style={{ visibility: "hidden" }} />
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
      <Handle type="source" position={Position.Right} style={{ visibility: "hidden" }} />
    </>
  )
}

const nodeTypes = { dagCanvasNode: DagCanvasNodeComponent }

// ── Detail Panel ──────────────────────────────────────────────

function DetailPanel({
  selected,
  onClose,
}: {
  selected: SelectedInfo | null
  onClose: () => void
}) {
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

      {selected.type === "node" && (
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

      {selected.type === "edge" && (
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
    <div className="flex items-start gap-3">
      <span className="shrink-0 text-[#8A8A8A] w-24">{label}</span>
      <span className={mono ? "font-mono text-[#0B0B0B] break-all" : "text-[#0B0B0B] break-all"}>
        {value || <span className="text-[#B5B5B5]">—</span>}
      </span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────

function DagCanvasInner({ nodes, edges, className }: DagCanvasProps) {
  const [selected, setSelected] = useState<SelectedInfo | null>(null)

  const { flowNodes, flowEdges } = useMemo(() => {
    if (nodes.length === 0) return { flowNodes: [], flowEdges: [] }
    const result = computeLayout(nodes, edges)
    return { flowNodes: result.nodes, flowEdges: result.edges }
  }, [nodes, edges])

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const handleNodeClick = useCallback(
    (_event: MouseEvent, node: Node) => {
      const raw = nodeMap.get(node.id)
      if (!raw) return
      const inCount = edges.filter((e) => e.to_node === node.id).length
      const outCount = edges.filter((e) => e.from_node === node.id).length
      setSelected({ type: "node", node: raw, inCount, outCount })
    },
    [edges, nodeMap],
  )

  const handleEdgeClick = useCallback(
    (_event: MouseEvent, edge: Edge) => {
      // Parse edge id: `e-${from}-${to}-${index}`
      const parts = edge.id.split("-")
      const from = parts[1]
      const to = parts[2]
      const raw = edges.find((e) => e.from_node === from && e.to_node === to)
      if (raw) {
        setSelected({ type: "edge", edge: raw })
      }
    },
    [edges],
  )

  const handlePaneClick = useCallback(() => {
    setSelected(null)
  }, [])

  const handleClose = useCallback(() => {
    setSelected(null)
  }, [])

  // Empty state: no nodes
  if (nodes.length === 0) {
    return (
      <div
        data-testid="dag-canvas"
        className={
          className ||
          "h-64 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] flex items-center justify-center"
        }
      >
        <div className="flex flex-col items-center gap-2 text-[#B5B5B5]">
          <GitBranch className="h-8 w-8" />
          <span className="text-sm">暂无节点</span>
        </div>
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
          "h-64 rounded-xl border border-[#E5E5E5] bg-[#FAFAF8] relative"
        }
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={true}
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          onPaneClick={handlePaneClick}
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
      </div>

      <DetailPanel selected={selected} onClose={handleClose} />
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

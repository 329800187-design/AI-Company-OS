import { useMemo } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  ReactFlowProvider,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "@dagrejs/dagre"
import { GitBranch, Cable } from "lucide-react"

// ── Types ──────────────────────────────────────────────────────

interface DagCanvasNode {
  id: string
  agent_id?: string
  title?: string
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
      selectable: false,
    }
  })

  const edges: Edge[] = rawEdges.map((e, i) => ({
    id: `e-${e.from_node}-${e.to_node}-${i}`,
    source: e.from_node,
    target: e.to_node,
    animated: true,
    style: { stroke: "#B5B5B5", strokeWidth: 1.5 },
    label: e.handoff_type || undefined,
    labelStyle: { fill: "#8A8A8A", fontSize: 10 },
    labelBgStyle: { fill: "#FAFAF8", fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 4,
  }))

  return { nodes, edges }
}

// ── Custom node component ─────────────────────────────────────

function DagCanvasNodeComponent({
  data,
}: {
  data: { label: string; sublabel: string }
}) {
  return (
    <div className="rounded-xl border border-[#E5E5E5] bg-white px-4 py-2.5 shadow-sm min-w-[140px] text-center">
      <div className="text-sm font-medium text-[#0B0B0B] truncate">
        {data.label}
      </div>
      {data.sublabel && (
        <div className="text-[10px] font-mono text-[#8A8A8A] mt-0.5 truncate">
          {data.sublabel}
        </div>
      )}
    </div>
  )
}

const nodeTypes = { dagCanvasNode: DagCanvasNodeComponent }

// ── Main component ────────────────────────────────────────────

function DagCanvasInner({ nodes, edges, className }: DagCanvasProps) {
  const { flowNodes, flowEdges } = useMemo(() => {
    if (nodes.length === 0) return { flowNodes: [], flowEdges: [] }
    const result = computeLayout(nodes, edges)
    return { flowNodes: result.nodes, flowEdges: result.edges }
  }, [nodes, edges])

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
        elementsSelectable={false}
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
      </ReactFlow>
      {showEdgeHint && (
        <div className="absolute top-2 right-3 flex items-center gap-1 text-[10px] text-[#B5B5B5]">
          <Cable className="h-3 w-3" />
          <span>无连线</span>
        </div>
      )}
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

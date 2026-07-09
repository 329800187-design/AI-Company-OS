export interface DagNode {
  id: string
  agent_id: string
}

export interface DagEdge {
  from_node: string
  to_node: string
}

export interface DagValidationError {
  type: "cycle" | "self_loop" | "missing_node" | "duplicate_id" | "empty_id" | "empty_edge"
  message: string
  edgeIndex?: number
  nodeIndex?: number
}

function detectCycle(nodeIds: string[], edges: DagEdge[]): string[] | null {
  const adjacency = new Map<string, string[]>()
  for (const id of nodeIds) adjacency.set(id, [])
  for (const edge of edges) {
    const from = edge.from_node.trim()
    const to = edge.to_node.trim()
    if (adjacency.has(from)) adjacency.get(from)!.push(to)
  }

  const white = 0
  const gray = 1
  const black = 2
  const color = new Map<string, number>()
  const parent = new Map<string, string | null>()
  for (const id of nodeIds) color.set(id, white)

  for (const id of nodeIds) {
    if (color.get(id) !== white) continue

    const stack: Array<[string, Iterator<string>]> = []
    color.set(id, gray)
    parent.set(id, null)
    stack.push([id, (adjacency.get(id) ?? []).values()])

    while (stack.length > 0) {
      const [current, iterator] = stack[stack.length - 1]
      const { value: neighbor, done } = iterator.next()
      if (done) {
        stack.pop()
        color.set(current, black)
      } else if (color.get(neighbor) === gray) {
        const cycle: string[] = [neighbor]
        let cursor: string | null = current
        while (cursor !== neighbor && cursor != null) {
          cycle.unshift(cursor)
          cursor = parent.get(cursor) ?? null
        }
        cycle.unshift(neighbor)
        return cycle
      } else if (color.get(neighbor) === white) {
        color.set(neighbor, gray)
        parent.set(neighbor, current)
        stack.push([neighbor, (adjacency.get(neighbor) ?? []).values()])
      }
    }
  }

  return null
}

export function validateDag(nodes: DagNode[], edges: DagEdge[]): DagValidationError[] {
  const errors: DagValidationError[] = []
  const nodeIds = nodes.map((node) => node.id.trim())
  const nodeIdSet = new Set(nodeIds)

  nodes.forEach((node, index) => {
    if (!node.id.trim()) errors.push({ type: "empty_id", message: `节点 ${index + 1}: id 不能为空`, nodeIndex: index })
    if (!node.agent_id.trim()) errors.push({ type: "empty_id", message: `节点 ${index + 1}: agent_id 不能为空`, nodeIndex: index })
  })

  const seen = new Set<string>()
  nodes.forEach((node, index) => {
    const id = node.id.trim()
    if (id && seen.has(id)) errors.push({ type: "duplicate_id", message: `节点 id "${id}" 重复`, nodeIndex: index })
    if (id) seen.add(id)
  })

  edges.forEach((edge, index) => {
    const from = edge.from_node.trim()
    const to = edge.to_node.trim()
    if (!from) errors.push({ type: "empty_edge", message: `边 ${index + 1}: from_node 不能为空`, edgeIndex: index })
    if (!to) errors.push({ type: "empty_edge", message: `边 ${index + 1}: to_node 不能为空`, edgeIndex: index })
    if (from && to && from === to) errors.push({ type: "self_loop", message: `边 ${index + 1}: 自环 (${from} → ${to})`, edgeIndex: index })
    if (from && !nodeIdSet.has(from)) errors.push({ type: "missing_node", message: `边 ${index + 1}: from_node "${from}" 不存在`, edgeIndex: index })
    if (to && !nodeIdSet.has(to)) errors.push({ type: "missing_node", message: `边 ${index + 1}: to_node "${to}" 不存在`, edgeIndex: index })
  })

  const hasEdgeErrors = errors.some((error) => error.type === "self_loop" || error.type === "missing_node")
  if (!hasEdgeErrors && nodeIds.length > 0) {
    const cycle = detectCycle(nodeIds, edges)
    if (cycle) errors.push({ type: "cycle", message: `存在循环: ${cycle.join(" → ")}` })
  }

  return errors
}

/**
 * Pipeline Runner — pure async topological execution of the Generation Canvas DAG.
 * Advances nodes idle → running → done|error via a per-node executor.
 * On executor error, sets node status='error' + error message and skips
 * descendants reachable only through the errored node.
 */

import type { PipelineState, CanvasNode } from "@/components/workspace/canvas/graphModel";

// ─── Types ───────────────────────────────────────────────────────────────────

/**
 * A node executor receives a CanvasNode and returns the output string on success.
 * It should throw an Error on failure.
 */
export type NodeExecutor = (node: CanvasNode) => Promise<string>;

// ─── Topological Run Logic ───────────────────────────────────────────────────

/**
 * Runs the pipeline by topologically traversing the DAG and executing each node.
 * Does NOT mutate the input state — builds up a new nodes array.
 *
 * Algorithm:
 * 1. Compute topological order via Kahn's algorithm (BFS with in-degree tracking)
 * 2. Process nodes in topological order
 * 3. For each node: set status to 'running', call executor, then set to 'done'
 *    with output OR 'error' with error message
 * 4. On error: mark the failing node as 'error', then skip all descendants
 *    reachable ONLY through that node (nodes whose ALL ancestor paths pass
 *    through at least one errored node)
 * 5. Return the final state with all node statuses updated
 */
export async function runPipeline(
  state: PipelineState,
  executor: NodeExecutor
): Promise<PipelineState> {
  const { nodes, edges } = state;

  // Build adjacency structures
  const children = new Map<string, string[]>();
  const parents = new Map<string, string[]>();
  const inDegree = new Map<string, number>();

  for (const node of nodes) {
    children.set(node.id, []);
    parents.set(node.id, []);
    inDegree.set(node.id, 0);
  }

  for (const edge of edges) {
    // Only process edges where both nodes exist
    if (children.has(edge.from) && parents.has(edge.to)) {
      children.get(edge.from)!.push(edge.to);
      parents.get(edge.to)!.push(edge.from);
      inDegree.set(edge.to, (inDegree.get(edge.to) ?? 0) + 1);
    }
  }

  // Kahn's algorithm: compute topological order
  const topoOrder: string[] = [];
  const queue: string[] = [];

  for (const node of nodes) {
    if (inDegree.get(node.id) === 0) {
      queue.push(node.id);
    }
  }

  while (queue.length > 0) {
    const current = queue.shift()!;
    topoOrder.push(current);

    for (const child of children.get(current) ?? []) {
      const newDegree = (inDegree.get(child) ?? 1) - 1;
      inDegree.set(child, newDegree);
      if (newDegree === 0) {
        queue.push(child);
      }
    }
  }

  // Track node statuses and results in a mutable map during execution
  const nodeStatus = new Map<string, { status: "idle" | "running" | "done" | "error"; output: string | null; error: string | null }>();
  for (const node of nodes) {
    nodeStatus.set(node.id, { status: node.status, output: node.output, error: node.error });
  }

  // Track which nodes have errored
  const erroredNodes = new Set<string>();

  // Process nodes in topological order
  for (const nodeId of topoOrder) {
    // Check if this node should be skipped:
    // A node is skipped if ALL of its parents are either errored or skipped
    // (i.e., there is no path to this node that doesn't go through an errored node)
    if (shouldSkipNode(nodeId, parents, erroredNodes)) {
      // Mark as skipped by leaving it in its current state or marking error
      // Per the design: "skip descendants reachable only through it"
      // Skipped nodes don't execute — they stay idle (or could be marked error)
      erroredNodes.add(nodeId);
      continue;
    }

    const node = nodes.find((n) => n.id === nodeId);
    if (!node) continue;

    // Set status to 'running'
    nodeStatus.set(nodeId, { status: "running", output: null, error: null });

    try {
      // Execute the node
      const output = await executor(node);
      // Set status to 'done' with output
      nodeStatus.set(nodeId, { status: "done", output, error: null });
    } catch (err: unknown) {
      // Set status to 'error' with error message
      const errorMessage = err instanceof Error ? err.message : String(err);
      nodeStatus.set(nodeId, { status: "error", output: null, error: errorMessage });
      erroredNodes.add(nodeId);
    }
  }

  // Build the final state without mutating the input
  const updatedNodes: CanvasNode[] = nodes.map((node) => {
    const result = nodeStatus.get(node.id);
    if (result) {
      return {
        ...node,
        status: result.status,
        output: result.output,
        error: result.error,
      };
    }
    return { ...node };
  });

  return {
    ...state,
    nodes: updatedNodes,
  };
}

/**
 * Determines if a node should be skipped during pipeline execution.
 * A node is skipped if it has parents and ALL of its parents are in the
 * errored set (meaning every path to this node passes through an errored node).
 */
function shouldSkipNode(
  nodeId: string,
  parents: Map<string, string[]>,
  erroredNodes: Set<string>
): boolean {
  const nodeParents = parents.get(nodeId) ?? [];

  // Root nodes (no parents) are never skipped
  if (nodeParents.length === 0) {
    return false;
  }

  // A node is skipped if ALL of its parents are errored or were skipped
  // (i.e., there is no successful path to reach this node)
  return nodeParents.every((parentId) => erroredNodes.has(parentId));
}

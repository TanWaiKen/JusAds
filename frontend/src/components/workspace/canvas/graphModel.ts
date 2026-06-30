/**
 * Canvas Graph Model — pure types and functions for the Generation Canvas.
 * No React dependencies; this module is the primary property-based-test surface.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export type NodeType =
  | "orchestrator"
  | "text"
  | "image"
  | "audio"
  | "video"
  | "critic"
  | "input"
  | "output";

export type NodeStatus = "idle" | "running" | "done" | "error";

export interface CanvasNode {
  id: string;
  type: NodeType;
  x: number;
  y: number;
  label: string;
  props: Record<string, string>;
  status: NodeStatus;
  output: string | null;
  error: string | null;
}

export interface CanvasEdge {
  id: string;
  from: string;
  to: string;
}

export interface Viewport {
  panX: number;
  panY: number;
  zoom: number;
}

export interface PipelineState {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  viewport: Viewport;
}

export interface Point {
  x: number;
  y: number;
}

// ─── Coordinate Transforms ───────────────────────────────────────────────────

/**
 * Converts a screen-space point to canvas-space using the current viewport.
 * Inverse of `canvasToScreen`.
 */
export function screenToCanvas(p: Point, v: Viewport): Point {
  return {
    x: (p.x - v.panX) / v.zoom,
    y: (p.y - v.panY) / v.zoom,
  };
}

/**
 * Converts a canvas-space point to screen-space using the current viewport.
 * Inverse of `screenToCanvas`.
 */
export function canvasToScreen(p: Point, v: Viewport): Point {
  return {
    x: p.x * v.zoom + v.panX,
    y: p.y * v.zoom + v.panY,
  };
}

// ─── Serialization ───────────────────────────────────────────────────────────

/**
 * Serializes a PipelineState into a JSON-ready structure for persistence.
 */
export function serializePipeline(state: PipelineState): unknown {
  return {
    nodes: state.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      x: node.x,
      y: node.y,
      label: node.label,
      props: { ...node.props },
      status: node.status,
      output: node.output,
      error: node.error,
    })),
    edges: state.edges.map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
    })),
    viewport: {
      panX: state.viewport.panX,
      panY: state.viewport.panY,
      zoom: state.viewport.zoom,
    },
  };
}

/**
 * Deserializes a raw JSON value back into a typed PipelineState.
 * Provides safe defaults for missing/malformed fields.
 */
export function deserializePipeline(raw: unknown): PipelineState {
  const data = raw as Record<string, unknown>;

  const rawNodes = Array.isArray(data.nodes) ? data.nodes : [];
  const rawEdges = Array.isArray(data.edges) ? data.edges : [];
  const rawViewport = (data.viewport ?? {}) as Record<string, unknown>;

  const nodes: CanvasNode[] = rawNodes.map((n: unknown) => {
    const node = n as Record<string, unknown>;
    return {
      id: String(node.id ?? ""),
      type: parseNodeType(node.type),
      x: Number(node.x ?? 0),
      y: Number(node.y ?? 0),
      label: String(node.label ?? ""),
      props: parseProps(node.props),
      status: parseNodeStatus(node.status),
      output: node.output != null ? String(node.output) : null,
      error: node.error != null ? String(node.error) : null,
    };
  });

  const edges: CanvasEdge[] = rawEdges.map((e: unknown) => {
    const edge = e as Record<string, unknown>;
    return {
      id: String(edge.id ?? ""),
      from: String(edge.from ?? ""),
      to: String(edge.to ?? ""),
    };
  });

  const viewport: Viewport = {
    panX: Number(rawViewport.panX ?? 0),
    panY: Number(rawViewport.panY ?? 0),
    zoom: Number(rawViewport.zoom ?? 1),
  };

  return { nodes, edges, viewport };
}

// ─── Node Mutations ──────────────────────────────────────────────────────────

/** Default labels for each node type when instantiated on the canvas. */
const DEFAULT_LABELS: Record<NodeType, string> = {
  orchestrator: "Orchestrator",
  text: "Text Agent",
  image: "Image Agent",
  audio: "Audio Agent",
  video: "Video Agent",
  critic: "Critic",
  input: "Input",
  output: "Output",
};

/** Simple counter-based unique ID generator (avoids crypto dependency in tests). */
let nodeIdCounter = 0;
function generateNodeId(): string {
  nodeIdCounter += 1;
  return `node-${Date.now()}-${nodeIdCounter}`;
}

/**
 * Returns a new state with one additional node at the given position.
 * The new node has default label based on type, empty props, idle status, and null output/error.
 */
export function addNode(
  state: PipelineState,
  type: NodeType,
  x: number,
  y: number
): PipelineState {
  const newNode: CanvasNode = {
    id: generateNodeId(),
    type,
    x,
    y,
    label: DEFAULT_LABELS[type],
    props: {},
    status: "idle",
    output: null,
    error: null,
  };

  return {
    ...state,
    nodes: [...state.nodes, newNode],
  };
}

/**
 * Returns a new state with the specified node's position updated to (x, y).
 * All other nodes, edges, and viewport remain unchanged.
 * If nodeId is not found, returns the state unchanged.
 */
export function moveNode(
  state: PipelineState,
  nodeId: string,
  x: number,
  y: number
): PipelineState {
  const nodeExists = state.nodes.some((n) => n.id === nodeId);
  if (!nodeExists) {
    return state;
  }

  return {
    ...state,
    nodes: state.nodes.map((node) =>
      node.id === nodeId ? { ...node, x, y } : node
    ),
  };
}

/**
 * Returns a new state with the specified node removed and all edges
 * incident to that node (where from === nodeId or to === nodeId) also removed.
 * If nodeId is not found, returns the state unchanged.
 */
export function deleteNode(
  state: PipelineState,
  nodeId: string
): PipelineState {
  const nodeExists = state.nodes.some((n) => n.id === nodeId);
  if (!nodeExists) {
    return state;
  }

  return {
    ...state,
    nodes: state.nodes.filter((node) => node.id !== nodeId),
    edges: state.edges.filter(
      (edge) => edge.from !== nodeId && edge.to !== nodeId
    ),
  };
}

// ─── Edge Connection ─────────────────────────────────────────────────────────

/**
 * Determines whether a directed edge from `from` to `to` can be added
 * without violating DAG invariants.
 *
 * Returns true only if:
 * 1. Both `from` and `to` nodes exist in state.nodes
 * 2. `from !== to` (no self-loops)
 * 3. No existing edge with the same `from` and `to` (no duplicates)
 * 4. Adding the edge would NOT create a cycle (graph remains a DAG)
 */
export function canConnect(
  state: PipelineState,
  from: string,
  to: string
): boolean {
  // Rule 1: both nodes must exist
  const fromExists = state.nodes.some((n) => n.id === from);
  const toExists = state.nodes.some((n) => n.id === to);
  if (!fromExists || !toExists) return false;

  // Rule 2: no self-loops
  if (from === to) return false;

  // Rule 3: no duplicate edges
  const duplicate = state.edges.some((e) => e.from === from && e.to === to);
  if (duplicate) return false;

  // Rule 4: adding from->to must not create a cycle
  // If we can reach `from` starting from `to` following existing edges,
  // then adding from->to would create a cycle.
  if (wouldCreateCycle(state.edges, from, to)) return false;

  return true;
}

/**
 * Adds a directed edge from `from` to `to` if `canConnect` permits it.
 * Returns the state unchanged if the connection is invalid.
 */
export function addEdge(
  state: PipelineState,
  from: string,
  to: string
): PipelineState {
  if (!canConnect(state, from, to)) return state;

  const newEdge: CanvasEdge = {
    id: crypto.randomUUID(),
    from,
    to,
  };
  return { ...state, edges: [...state.edges, newEdge] };
}

/**
 * Checks if adding an edge from->to would create a cycle.
 * Uses BFS from `to` following existing edges to see if `from` is reachable.
 */
function wouldCreateCycle(
  edges: readonly CanvasEdge[],
  from: string,
  to: string
): boolean {
  // Build adjacency list for existing edges
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const neighbors = adjacency.get(edge.from);
    if (neighbors) {
      neighbors.push(edge.to);
    } else {
      adjacency.set(edge.from, [edge.to]);
    }
  }

  // BFS from `to` — if we can reach `from`, adding from->to creates a cycle
  const visited = new Set<string>();
  const queue: string[] = [to];
  visited.add(to);

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === from) return true;

    const neighbors = adjacency.get(current);
    if (neighbors) {
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }
  }

  return false;
}

// ─── Internal Helpers ────────────────────────────────────────────────────────

const VALID_NODE_TYPES: ReadonlySet<string> = new Set<NodeType>([
  "orchestrator",
  "text",
  "image",
  "audio",
  "video",
  "critic",
  "input",
  "output",
]);

const VALID_NODE_STATUSES: ReadonlySet<string> = new Set<NodeStatus>([
  "idle",
  "running",
  "done",
  "error",
]);

function parseNodeType(value: unknown): NodeType {
  const str = String(value ?? "");
  return VALID_NODE_TYPES.has(str) ? (str as NodeType) : "input";
}

function parseNodeStatus(value: unknown): NodeStatus {
  const str = String(value ?? "");
  return VALID_NODE_STATUSES.has(str) ? (str as NodeStatus) : "idle";
}

function parseProps(value: unknown): Record<string, string> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const result: Record<string, string> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      result[k] = String(v ?? "");
    }
    return result;
  }
  return {};
}

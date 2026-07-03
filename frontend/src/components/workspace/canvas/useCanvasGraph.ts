/**
 * useCanvasGraph — reducer hook for the Generation Canvas state.
 * Wraps useReducer over PipelineState plus UI-only selectedNodeId.
 * All graph mutations delegate to graphModel.ts pure functions.
 */

import { useReducer } from "react";
import type { PipelineState, NodeType, Viewport } from "@/components/workspace/canvas/graphModel";
import {
  addNode,
  moveNode,
  deleteNode,
  addEdge,
  updateNodeProps,
  resizeNode,
} from "@/components/workspace/canvas/graphModel";

// ─── State ───────────────────────────────────────────────────────────────────

export interface CanvasGraphState {
  pipeline: PipelineState;
  selectedNodeId: string | null;
}

// ─── Actions ─────────────────────────────────────────────────────────────────

interface AddNodeAction {
  type: "ADD_NODE";
  nodeType: NodeType;
  x: number;
  y: number;
}

interface MoveNodeAction {
  type: "MOVE_NODE";
  nodeId: string;
  x: number;
  y: number;
}

interface DeleteNodeAction {
  type: "DELETE_NODE";
  nodeId: string;
}

interface AddEdgeAction {
  type: "ADD_EDGE";
  from: string;
  to: string;
}

interface CancelConnectionAction {
  type: "CANCEL_CONNECTION";
}

interface SelectNodeAction {
  type: "SELECT_NODE";
  nodeId: string | null;
}

interface UpdateNodePropsAction {
  type: "UPDATE_NODE_PROPS";
  nodeId: string;
  label?: string;
  props?: Record<string, string>;
}

interface PanAction {
  type: "PAN";
  panX: number;
  panY: number;
}

interface ZoomAction {
  type: "ZOOM";
  zoom: number;
  panX: number;
  panY: number;
}

interface SetPipelineAction {
  type: "SET_PIPELINE";
  pipeline: PipelineState;
}

interface ResizeNodeAction {
  type: "RESIZE_NODE";
  nodeId: string;
  width: number;
  height: number;
}

export type CanvasAction =
  | AddNodeAction
  | MoveNodeAction
  | DeleteNodeAction
  | AddEdgeAction
  | CancelConnectionAction
  | SelectNodeAction
  | UpdateNodePropsAction
  | PanAction
  | ZoomAction
  | SetPipelineAction
  | ResizeNodeAction;

// ─── Reducer ─────────────────────────────────────────────────────────────────

function canvasReducer(state: CanvasGraphState, action: CanvasAction): CanvasGraphState {
  switch (action.type) {
    case "ADD_NODE": {
      const pipeline = addNode(state.pipeline, action.nodeType, action.x, action.y);
      const newNode = pipeline.nodes[pipeline.nodes.length - 1];
      return { pipeline, selectedNodeId: newNode.id };
    }

    case "MOVE_NODE":
      return {
        ...state,
        pipeline: moveNode(state.pipeline, action.nodeId, action.x, action.y),
      };

    case "DELETE_NODE": {
      const pipeline = deleteNode(state.pipeline, action.nodeId);
      const selectedNodeId =
        state.selectedNodeId === action.nodeId ? null : state.selectedNodeId;
      return { pipeline, selectedNodeId };
    }

    case "ADD_EDGE":
      return {
        ...state,
        pipeline: addEdge(state.pipeline, action.from, action.to),
      };

    case "CANCEL_CONNECTION":
      return state;

    case "SELECT_NODE":
      return { ...state, selectedNodeId: action.nodeId };

    case "UPDATE_NODE_PROPS":
      return {
        ...state,
        pipeline: updateNodeProps(state.pipeline, action.nodeId, {
          label: action.label,
          props: action.props,
        }),
      };

    case "PAN": {
      const viewport: Viewport = {
        ...state.pipeline.viewport,
        panX: action.panX,
        panY: action.panY,
      };
      return {
        ...state,
        pipeline: { ...state.pipeline, viewport },
      };
    }

    case "ZOOM": {
      const viewport: Viewport = {
        panX: action.panX,
        panY: action.panY,
        zoom: action.zoom,
      };
      return {
        ...state,
        pipeline: { ...state.pipeline, viewport },
      };
    }

    case "SET_PIPELINE":
      return { pipeline: action.pipeline, selectedNodeId: null };

    case "RESIZE_NODE":
      return {
        ...state,
        pipeline: resizeNode(state.pipeline, action.nodeId, action.width, action.height),
      };

    default:
      return state;
  }
}

// ─── Hook ────────────────────────────────────────────────────────────────────

const EMPTY_PIPELINE: PipelineState = {
  nodes: [],
  edges: [],
  viewport: { panX: 0, panY: 0, zoom: 1 },
};

export function useCanvasGraph(initial?: PipelineState) {
  const [state, dispatch] = useReducer(canvasReducer, {
    pipeline: initial ?? EMPTY_PIPELINE,
    selectedNodeId: null,
  });

  return { state, dispatch };
}
